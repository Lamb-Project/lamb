"""C22 tests — removing the attached document, and the DB helpers behind it.

Two things regressed together:

* ``clear_assistant_rag_collections`` referenced an ``assistants.metadata``
  column that does not exist (``Assistant.metadata`` is the ``api_callback``
  JSON), so the retention tests — which mock the database — passed while the
  real statement failed with ``no such column: metadata``. These tests run the
  helpers against a real SQLite file.
* "Remove" in step 2 only cleared the browser, so the session still held the
  old document and every later upload answered 429.
"""

import json
import sqlite3
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from lamb.database_manager import LambDatabaseManager
from lamb.lamb_classes import Assistant
from lamb.modules.workshop import routers


class _FakeDb:
    """Duck-typed db_manager: methods are called unbound with this as self."""

    table_prefix = ""

    def __init__(self, path):
        self._path = path

    def get_connection(self):
        return sqlite3.connect(self._path)


def _init_db(path, api_callback):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE assistants (
            id INTEGER PRIMARY KEY,
            name TEXT,
            api_callback TEXT,
            RAG_collections TEXT,
            updated_at INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE lti_workshop_sessions (
            id TEXT PRIMARY KEY,
            activity_id INTEGER NOT NULL,
            saved_chat TEXT,
            reflection TEXT,
            build_state TEXT,
            kb_id TEXT,
            document_file_id TEXT,
            document_name TEXT,
            document_status TEXT,
            updated_at INTEGER
        )
    """)
    conn.execute(
        "INSERT INTO assistants VALUES (7, 'A', ?, 'kb-1', 1)", (api_callback,))
    conn.execute(
        "INSERT INTO lti_workshop_sessions VALUES "
        "('ws-1', 1, '[{\"role\":\"user\"}]', 'my reflection', '{\"step\":3}', "
        "'kb-1', 'file-1', 'notes.md', 'completed', 1)")
    conn.commit()
    conn.close()


def _row(path, sql, *args):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql, args).fetchone()
    finally:
        conn.close()


class TestClearAssistantRagCollections:
    def test_drops_the_binding_and_the_rag_processor_marker(self, tmp_path):
        db = str(tmp_path / "a.db")
        _init_db(db, json.dumps({
            "connector": "ollama", "llm": "qwen", "rag_processor": "simple_rag"}))

        assert LambDatabaseManager.clear_assistant_rag_collections(
            _FakeDb(db), 7) is True

        collections, callback = _row(
            db, "SELECT RAG_collections, api_callback FROM assistants WHERE id=7")
        assert collections == ""
        # Only the RAG marker goes; the model wiring must survive.
        assert json.loads(callback) == {"connector": "ollama", "llm": "qwen"}

    def test_non_json_api_callback_is_left_alone_but_binding_is_cleared(
            self, tmp_path):
        db = str(tmp_path / "b.db")
        _init_db(db, "not json")

        assert LambDatabaseManager.clear_assistant_rag_collections(
            _FakeDb(db), 7) is True

        collections, callback = _row(
            db, "SELECT RAG_collections, api_callback FROM assistants WHERE id=7")
        assert collections == ""
        assert callback == "not json"

    def test_empty_api_callback_becomes_an_empty_object(self, tmp_path):
        db = str(tmp_path / "c.db")
        _init_db(db, "")

        assert LambDatabaseManager.clear_assistant_rag_collections(
            _FakeDb(db), 7) is True
        (callback,) = _row(db, "SELECT api_callback FROM assistants WHERE id=7")
        assert json.loads(callback) == {}

    def test_unknown_assistant_is_false(self, tmp_path):
        db = str(tmp_path / "d.db")
        _init_db(db, "{}")
        assert LambDatabaseManager.clear_assistant_rag_collections(
            _FakeDb(db), 999) is False


class TestClearWorkshopSessionDocument:
    def test_clears_only_the_document_binding(self, tmp_path):
        db = str(tmp_path / "s.db")
        _init_db(db, "{}")

        assert LambDatabaseManager.clear_workshop_session_document(
            _FakeDb(db), "ws-1") is True

        kb_id, file_id, name, status = _row(
            db,
            "SELECT kb_id, document_file_id, document_name, document_status "
            "FROM lti_workshop_sessions WHERE id='ws-1'")
        assert (kb_id, file_id, name, status) == (None, None, None, None)

        chat, reflection, build = _row(
            db,
            "SELECT saved_chat, reflection, build_state "
            "FROM lti_workshop_sessions WHERE id='ws-1'")
        # Removing a document must not cost the student their work (C18/C22).
        assert chat and reflection == "my reflection" and build == '{"step":3}'

    def test_unknown_session_is_false(self, tmp_path):
        db = str(tmp_path / "t.db")
        _init_db(db, "{}")
        assert LambDatabaseManager.clear_workshop_session_document(
            _FakeDb(db), "nope") is False


def _token_payload(**overrides):
    payload = {
        "scope": "workshop_student",
        "session_id": "ws-1",
        "activity_id": 1,
        "email": "student-a@lamb-lti.local",
        "organization_id": 10,
    }
    payload.update(overrides)
    return payload


def _session(**overrides):
    session = {
        "id": "ws-1", "activity_id": 1, "activity_user_id": 5,
        "assistant_id": 7, "kb_id": "kb-mine",
    }
    session.update(overrides)
    return session


def _assistant(**overrides):
    opts = dict(
        id=7, name="A", description="", owner="student-a@lamb-lti.local",
        api_callback="{}", system_prompt="S", prompt_template="T",
        organization_id=10, RAG_Top_k=3, RAG_collections="kb-mine",
        pre_retrieval_endpoint="", post_retrieval_endpoint="", RAG_endpoint="",
    )
    opts.update(overrides)
    return Assistant(**opts)


class TestRemoveDocumentRoute:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_deletes_the_kb_then_clears_the_binding(
            self, mock_db, mock_decode, mock_delete):
        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_db.get_workshop_session_by_id.return_value = _session()
        mock_db.get_lti_activity_by_id.return_value = {"id": 1}
        mock_delete.return_value = {"deleted": True, "detail": "ok"}

        result = await routers.remove_workshop_document(
            session_id="ws-1", assistant_id=7, token="tok")

        assert result == {"success": True, "removed": True}
        # The id comes from the session row, never from the client (S1).
        assert mock_delete.await_args[0][1] == "kb-mine"
        mock_db.clear_workshop_session_document.assert_called_once_with("ws-1")
        mock_db.clear_assistant_rag_collections.assert_called_once_with(7)

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_kb_failure_leaves_local_state_untouched(
            self, mock_db, mock_decode, mock_delete):
        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_db.get_workshop_session_by_id.return_value = _session()
        mock_db.get_lti_activity_by_id.return_value = {"id": 1}
        mock_delete.side_effect = RuntimeError("KB server unreachable")

        with pytest.raises(HTTPException) as exc:
            await routers.remove_workshop_document(
                session_id="ws-1", assistant_id=7, token="tok")

        assert exc.value.status_code == 502
        mock_db.clear_workshop_session_document.assert_not_called()
        mock_db.clear_assistant_rag_collections.assert_not_called()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_without_a_document_it_is_a_harmless_no_op(
            self, mock_db, mock_decode, mock_delete):
        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_db.get_workshop_session_by_id.return_value = _session(kb_id=None)

        result = await routers.remove_workshop_document(
            session_id="ws-1", assistant_id=7, token="tok")

        assert result == {"success": True, "removed": False}
        mock_delete.assert_not_awaited()
        mock_db.clear_workshop_session_document.assert_called_once_with("ws-1")

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.delete_session_kb", new_callable=AsyncMock)
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_someone_elses_assistant_is_403(
            self, mock_db, mock_decode, mock_delete):
        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _assistant(
            owner="student-b@lamb-lti.local")

        with pytest.raises(HTTPException) as exc:
            await routers.remove_workshop_document(
                session_id="ws-1", assistant_id=7, token="tok")

        assert exc.value.status_code == 403
        mock_delete.assert_not_awaited()
        mock_db.clear_workshop_session_document.assert_not_called()
