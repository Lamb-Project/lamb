"""S1 regression tests — workshop KB ownership (kb_id is an assertion).

The workshop wizard used to let the client pick ``kb_id`` and
``rag_collections``. A crafted request could therefore point a student's
assistant at another student's collection, both for the immediate probe and —
worse — persistently, because the id was written to the assistant's
``RAG_collections`` and every later RAG turn / ``kb_query`` call re-read it.

These tests pin the four injection points (connect, query, create, patch), the
two-tier error semantics (403 = foreign value, 400 = no KB yet), and the
defense-in-depth narrowing applied by the retrieval paths.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lamb.lamb_classes import Assistant
from lamb.modules.workshop import kb, routers


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
        "id": "ws-1",
        "activity_id": 1,
        "activity_user_id": 5,
        "assistant_id": 7,
        "kb_id": "kb-mine",
        "build_state": "{}",
    }
    session.update(overrides)
    return session


def _assistant(**overrides):
    opts = dict(
        id=7, name="A", description="", owner="student-a@lamb-lti.local",
        api_callback=json.dumps({"connector": "ollama", "llm": "qwen"}),
        system_prompt="S", prompt_template="{user_input}\n{context}",
        organization_id=10, RAG_Top_k=3, RAG_collections="kb-mine",
        pre_retrieval_endpoint="", post_retrieval_endpoint="", RAG_endpoint="",
    )
    opts.update(overrides)
    return Assistant(**opts)


class TestResolveSessionKbId:
    """Decision C1: assert, never trust, a client-supplied kb_id."""

    def test_absent_value_uses_session_kb(self):
        assert routers._resolve_session_kb_id(_session(), None) == "kb-mine"

    def test_matching_value_is_accepted(self):
        assert routers._resolve_session_kb_id(_session(), "kb-mine") == "kb-mine"

    def test_foreign_value_is_403(self):
        with pytest.raises(HTTPException) as exc:
            routers._resolve_session_kb_id(_session(), "kb-someone-else")
        assert exc.value.status_code == 403

    def test_value_without_session_kb_is_400_not_403(self):
        """A missing session KB is a state anomaly, not an attack (C1)."""
        with pytest.raises(HTTPException) as exc:
            routers._resolve_session_kb_id(_session(kb_id=None), "kb-other")
        assert exc.value.status_code == 400

    def test_blank_value_falls_back_to_session(self):
        assert routers._resolve_session_kb_id(_session(), "  ") == "kb-mine"
        assert routers._resolve_session_kb_id(_session(), "null") == "kb-mine"


class TestAssertRagCollectionsAllowed:
    def test_empty_is_allowed(self):
        assert routers._assert_rag_collections_allowed(_session(), "") == ""
        assert routers._assert_rag_collections_allowed(_session(), None) == ""
        assert routers._assert_rag_collections_allowed(_session(), []) == ""

    def test_own_collection_is_allowed(self):
        assert routers._assert_rag_collections_allowed(
            _session(), "kb-mine") == "kb-mine"

    def test_json_array_of_own_collection_is_allowed(self):
        assert routers._assert_rag_collections_allowed(
            _session(), '["kb-mine"]') == "kb-mine"

    def test_foreign_collection_is_403(self):
        with pytest.raises(HTTPException) as exc:
            routers._assert_rag_collections_allowed(_session(), "kb-other")
        assert exc.value.status_code == 403

    def test_own_plus_foreign_is_403(self):
        with pytest.raises(HTTPException) as exc:
            routers._assert_rag_collections_allowed(
                _session(), "kb-mine,kb-other")
        assert exc.value.status_code == 403

    def test_collection_without_session_kb_is_400(self):
        with pytest.raises(HTTPException) as exc:
            routers._assert_rag_collections_allowed(
                _session(kb_id=None), "kb-other")
        assert exc.value.status_code == 400


class TestSanitizeStoredCollections:
    """Unrelated edits on a dirty legacy row must not hard-fail."""

    def test_dirty_stored_value_is_repaired(self):
        assert routers._sanitize_stored_collections(
            _session(), "kb-other") == "kb-mine"

    def test_dirty_stored_value_without_session_kb_is_cleared(self):
        assert routers._sanitize_stored_collections(
            _session(kb_id=None), "kb-other") == ""

    def test_clean_stored_value_is_kept(self):
        assert routers._sanitize_stored_collections(
            _session(), "kb-mine") == "kb-mine"


class TestInjectionPoints:
    """The four routes that used to accept a client-chosen collection."""

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_connect_rejects_foreign_kb_id(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_db.get_workshop_session_by_id.return_value = _session()

        with pytest.raises(HTTPException) as exc:
            await routers.connect_workshop_kb(
                session_id="ws-1", assistant_id=7,
                body={"kb_id": "kb-victim"}, token="tok")
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.query_session_kb", new_callable=AsyncMock)
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_connect_accepts_own_kb_id(
            self, mock_db, mock_decode, mock_query):
        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_db.get_workshop_session_by_id.return_value = _session()
        mock_query.return_value = {"results": [], "count": 0}

        result = await routers.connect_workshop_kb(
            session_id="ws-1", assistant_id=7,
            body={"kb_id": "kb-mine", "query": "hi"}, token="tok")
        assert result["kb_id"] == "kb-mine"
        assert mock_query.call_args[0][0] == "kb-mine"

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_query_rejects_foreign_kb_id(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_db.get_workshop_session_by_id.return_value = _session()

        with pytest.raises(HTTPException) as exc:
            await routers.query_workshop_kb(
                session_id="ws-1", assistant_id=7,
                body={"kb_id": "kb-victim", "query": "secret"}, token="tok")
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_create_rejects_foreign_rag_collections(
            self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload()
        mock_db.get_workshop_session_by_id.return_value = _session(
            assistant_id=None)

        with pytest.raises(HTTPException) as exc:
            await routers.create_workshop_assistant(
                session_id="ws-1",
                body={"name": "A", "rag_collections": "kb-victim"},
                token="tok")
        assert exc.value.status_code == 403
        mock_db.add_assistant.assert_not_called()

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_create_allows_own_collection(self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload()
        mock_db.get_workshop_session_by_id.return_value = _session(
            assistant_id=None)
        mock_db.add_assistant.return_value = 7

        result = await routers.create_workshop_assistant(
            session_id="ws-1",
            body={"name": "A", "rag_collections": "kb-mine"},
            token="tok")
        assert result["assistant_id"] == 7
        created = mock_db.add_assistant.call_args[0][0]
        assert created.RAG_collections == "kb-mine"

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_patch_rejects_foreign_rag_collections(
            self, mock_db, mock_decode):
        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_db.get_workshop_session_by_id.return_value = _session()

        with pytest.raises(HTTPException) as exc:
            await routers.update_workshop_assistant(
                session_id="ws-1", assistant_id=7,
                body={"rag_collections": "kb-victim"}, token="tok")
        assert exc.value.status_code == 403
        mock_db.update_assistant.assert_not_called()

    @pytest.mark.asyncio
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_patch_repairs_dirty_stored_collections(
            self, mock_db, mock_decode):
        """A legacy row with a foreign id is repaired by an unrelated edit."""
        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _assistant(
            RAG_collections="kb-victim")
        mock_db.get_workshop_session_by_id.return_value = _session()
        mock_db.update_assistant.return_value = True

        await routers.update_workshop_assistant(
            session_id="ws-1", assistant_id=7,
            body={"system_prompt": "new"}, token="tok")

        updated = mock_db.update_assistant.call_args[0][1]
        assert updated.RAG_collections == "kb-mine"
        assert updated.system_prompt == "new"


class TestRestrictCollectionsForAssistant:
    """Defense in depth on the retrieval paths (kb_query + simple_rag)."""

    @patch("lamb.modules.workshop.kb._db")
    def test_non_workshop_assistant_untouched(self, mock_db):
        assistant = _assistant(owner="teacher@school.edu",
                               RAG_collections="kb-1,kb-2")
        assert kb.restrict_collections_for_assistant(
            assistant, ["kb-1", "kb-2"]) == ["kb-1", "kb-2"]
        # Domain gate short-circuits: no DB query for ordinary assistants.
        mock_db.return_value.get_workshop_session_by_assistant.assert_not_called()

    @patch("lamb.modules.workshop.kb._db")
    def test_foreign_collection_dropped(self, mock_db):
        mock_db.return_value.get_workshop_session_by_assistant.return_value = (
            _session())
        assistant = _assistant(RAG_collections="kb-victim")
        assert kb.restrict_collections_for_assistant(
            assistant, ["kb-victim"]) == []

    @patch("lamb.modules.workshop.kb._db")
    def test_own_collection_kept(self, mock_db):
        mock_db.return_value.get_workshop_session_by_assistant.return_value = (
            _session())
        assistant = _assistant(RAG_collections="kb-mine")
        assert kb.restrict_collections_for_assistant(
            assistant, ["kb-mine"]) == ["kb-mine"]

    @patch("lamb.modules.workshop.kb._db")
    def test_mixed_list_keeps_only_own(self, mock_db):
        mock_db.return_value.get_workshop_session_by_assistant.return_value = (
            _session())
        assistant = _assistant(RAG_collections="kb-victim,kb-mine")
        assert kb.restrict_collections_for_assistant(
            assistant, ["kb-victim", "kb-mine"]) == ["kb-mine"]

    @patch("lamb.modules.workshop.kb._db")
    def test_student_domain_without_session_is_untouched(self, mock_db):
        """Student-domain assistant with no workshop session row: not ours."""
        mock_db.return_value.get_workshop_session_by_assistant.return_value = None
        assistant = _assistant(RAG_collections="kb-1")
        assert kb.restrict_collections_for_assistant(
            assistant, ["kb-1"]) == ["kb-1"]


class TestKbQueryToolRestriction:
    """The tool must not retrieve another session's chunks."""

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.query_kb_collection", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.kb.config_for_owner")
    @patch("lamb.modules.workshop.kb._db")
    async def test_foreign_collection_not_queried(
            self, mock_db, mock_config, mock_query):
        from lamb.completions.tools.implementations.kb_query import run_kb_query

        mock_db.return_value.get_workshop_session_by_assistant.return_value = (
            _session())
        mock_config.return_value = {"url": "http://kb", "token": "t"}

        result = await run_kb_query(
            {"query": "secrets"}, assistant=_assistant(RAG_collections="kb-victim"))

        assert result["success"] is True
        assert result["results"] == []
        mock_query.assert_not_called()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.query_kb_collection", new_callable=AsyncMock)
    @patch("lamb.modules.workshop.kb.config_for_owner")
    @patch("lamb.modules.workshop.kb._db")
    async def test_own_collection_still_queried(
            self, mock_db, mock_config, mock_query):
        from lamb.completions.tools.implementations.kb_query import run_kb_query

        mock_db.return_value.get_workshop_session_by_assistant.return_value = (
            _session())
        mock_config.return_value = {"url": "http://kb", "token": "t"}
        mock_query.return_value = {
            "results": [{"data": "chunk", "similarity": 0.9, "metadata": {}}],
            "count": 1,
        }

        result = await run_kb_query(
            {"query": "hi"}, assistant=_assistant(RAG_collections="kb-mine"))

        assert result["count"] == 1
        assert mock_query.call_args[0][1] == "kb-mine"

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb._db")
    async def test_non_workshop_assistant_unchanged(self, mock_db):
        """Regression: the shared tool path for ordinary assistants is intact."""
        from lamb.completions.tools.implementations.kb_query import run_kb_query

        with patch("lamb.modules.workshop.kb.config_for_owner",
                   side_effect=RuntimeError("no kb")), \
             patch("lamb.modules.workshop.kb.query_kb_collection",
                   new_callable=AsyncMock):
            result = await run_kb_query(
                {"query": "hi"},
                assistant=_assistant(owner="teacher@school.edu",
                                     RAG_collections="kb-1"))

        assert result["success"] is False
        assert "KB not configured" in result["error"]


class TestSimpleRagRestriction:
    """simple_rag is the everyday retrieval channel — same narrowing."""

    def test_foreign_collection_aborts_retrieval(self):
        from lamb.completions.rag import simple_rag

        with patch("lamb.modules.workshop.kb._db") as mock_db:
            mock_db.return_value.get_workshop_session_by_assistant.return_value = (
                _session())
            result = simple_rag.rag_processor(
                messages=[{"role": "user", "content": "hi"}],
                assistant=_assistant(RAG_collections="kb-victim"),
            )

        assert result["sources"] == []
        assert "No accessible knowledge base" in result["context"]
