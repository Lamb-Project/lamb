"""
Tests for the workshop KB helper (real KB server wiring).

All KB HTTP is mocked — these tests assert the wiring contract: collection
naming, reuse, ingestion job ids, query mapping, and assistant RAG linking.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lamb.lamb_classes import Assistant
from lamb.modules.workshop import kb


class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


def _client_returning(resp):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(return_value=resp)
    client.get = AsyncMock(return_value=resp)
    return client


def _assistant(**overrides):
    opts = dict(
        id=7, name="A", description="", owner="student@lamb-lti.local",
        api_callback=json.dumps({"connector": "ollama", "llm": "qwen"}),
        system_prompt="S", prompt_template="{user_input}\n{context}",
        organization_id=10, RAG_Top_k=3, RAG_collections="",
        pre_retrieval_endpoint="", post_retrieval_endpoint="", RAG_endpoint="",
    )
    opts.update(overrides)
    return Assistant(**opts)


class TestSessionKbName:
    def test_name_is_session_scoped(self):
        assert kb._session_kb_name(1, 5) == "ws-1-5"


class TestEnsureSessionKb:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb._db")
    @patch("lamb.modules.workshop.kb._resolve_kb_config")
    async def test_creates_once(self, mock_resolve, mock_db):
        manager = MagicMock()
        manager.create_knowledge_base = AsyncMock(return_value={"id": "kb-1"})
        mock_resolve.return_value = {
            "manager": manager,
            "creator_user": {"id": 1, "email": "t@t", "organization_id": 10},
            "config": {"url": "http://kb:9090", "token": "tok"},
        }
        session = {"id": "ws-1", "activity_user_id": 5}

        kb_id = await kb.ensure_session_kb({"id": 1, "owner_email": "t@t"}, session)

        assert kb_id == "kb-1"
        manager.create_knowledge_base.assert_awaited_once()
        mock_db.return_value.update_workshop_session_kb.assert_called_once_with(
            "ws-1", kb_id="kb-1")

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb._resolve_kb_config")
    async def test_reuses_existing(self, mock_resolve):
        session = {"id": "ws-1", "activity_user_id": 5, "kb_id": "kb-existing"}

        kb_id = await kb.ensure_session_kb({"id": 1}, session)

        assert kb_id == "kb-existing"
        mock_resolve.assert_not_called()


class TestIngestDocument:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.httpx.AsyncClient")
    @patch("lamb.modules.workshop.kb._resolve_kb_config")
    async def test_returns_job_id(self, mock_resolve, mock_client):
        mock_resolve.return_value = {
            "config": {"url": "http://kb:9090", "token": "tok"}}
        resp = _Resp(200, {"file_registry_id": 42, "status": "processing",
                           "original_filename": "doc.txt"})
        mock_client.return_value = _client_returning(resp)

        result = await kb.ingest_document(
            "kb-1", "doc.txt", b"hello", {"id": 1})

        assert result["file_registry_id"] == "42"
        assert result["status"] == "processing"


class TestIngestionStatus:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.httpx.AsyncClient")
    @patch("lamb.modules.workshop.kb._resolve_kb_config")
    async def test_maps_fields(self, mock_resolve, mock_client):
        mock_resolve.return_value = {
            "config": {"url": "http://kb:9090", "token": "tok"}}
        resp = _Resp(200, {
            "status": "completed",
            "progress": {"percentage": 100},
            "document_count": 3,
            "error_message": None,
        })
        mock_client.return_value = _client_returning(resp)

        result = await kb.get_ingestion_status("kb-1", "42", {"id": 1})

        assert result["status"] == "completed"
        assert result["document_count"] == 3


class TestQueryKbCollection:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.kb.httpx.AsyncClient")
    async def test_returns_results(self, mock_client):
        resp = _Resp(200, {"results": [
            {"similarity": 0.8, "data": "chunk", "metadata": {"page": 1}}]})
        mock_client.return_value = _client_returning(resp)

        result = await kb.query_kb_collection(
            {"url": "http://kb:9090", "token": "tok"}, "kb-1", "q", 3)

        assert result["count"] == 1
        assert result["results"][0]["data"] == "chunk"


class TestLinkKbToAssistant:
    @patch("lamb.modules.workshop.kb._db")
    def test_sets_comma_separated_and_processor(self, mock_db):
        mock_db.return_value.get_assistant_by_id.return_value = _assistant()
        mock_db.return_value.update_assistant.return_value = True

        ok = kb.link_kb_to_assistant(7, "kb-1")

        assert ok is True
        updated = mock_db.return_value.update_assistant.call_args[0][1]
        assert updated.RAG_collections == "kb-1"
        metadata = json.loads(updated.metadata)
        assert metadata["rag_processor"] == "simple_rag"
        # Existing connector/llm preserved.
        assert metadata["connector"] == "ollama"
        assert metadata["llm"] == "qwen"

    @patch("lamb.modules.workshop.kb._db")
    def test_missing_assistant(self, mock_db):
        mock_db.return_value.get_assistant_by_id.return_value = None
        assert kb.link_kb_to_assistant(7, "kb-1") is False


class TestConfigForOwner:
    @patch("creator_interface.kb_server_manager.KBServerManager")
    def test_delegates_to_manager(self, mock_manager_cls):
        mock_manager_cls.return_value._get_kb_config_for_user.return_value = {
            "url": "http://kb:9090", "token": "tok"}

        config = kb.config_for_owner("a@b.com")

        assert config["url"] == "http://kb:9090"
        mock_manager_cls.return_value._get_kb_config_for_user.assert_called_once_with(
            {"email": "a@b.com"})


def _token_payload(**overrides):
    p = {
        "scope": "workshop_student",
        "session_id": "ws-1",
        "activity_id": 1,
        "email": "student@lamb-lti.local",
        "organization_id": 10,
    }
    p.update(overrides)
    return p


def _own_assistant(**overrides):
    return _assistant(owner="student@lamb-lti.local", **overrides)


class TestApplyRagDefaults:
    def test_json_array_becomes_comma_separated(self):
        from lamb.modules.workshop import routers

        api_callback, collections = routers._apply_rag_defaults(
            json.dumps({"connector": "ollama"}), '["kb-1"]')

        assert collections == "kb-1"
        assert json.loads(api_callback)["rag_processor"] == "simple_rag"
        assert json.loads(api_callback)["connector"] == "ollama"

    def test_empty_keeps_processor_unset(self):
        from lamb.modules.workshop import routers

        api_callback, collections = routers._apply_rag_defaults("{}", "[]")

        assert collections == ""
        assert "rag_processor" not in json.loads(api_callback)


class TestDocumentRoute:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers.workshop_kb")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_attach_ingests_and_links(
            self, mock_db, mock_decode, mock_kb):
        from lamb.modules.workshop import routers

        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _own_assistant()
        mock_db.get_workshop_session_by_id.return_value = {
            "id": "ws-1", "activity_id": 1, "activity_user_id": 5,
            "kb_id": None, "document_file_id": None, "document_status": None,
        }
        mock_db.get_lti_activity_by_id.return_value = {"id": 1, "owner_email": "t@t"}
        mock_kb.ensure_session_kb = AsyncMock(return_value="kb-1")
        mock_kb.ingest_document = AsyncMock(return_value={
            "file_registry_id": "42", "status": "processing",
            "original_filename": "doc.txt"})
        mock_kb.link_kb_to_assistant = MagicMock(return_value=True)

        file = MagicMock(filename="doc.txt", content_type="text/plain")
        file.read = AsyncMock(return_value=b"hello")

        result = await routers.attach_workshop_document(
            session_id="ws-1", assistant_id=7, file=file, token="tok")

        assert result["success"] is True
        assert result["kb_id"] == "kb-1"
        assert result["file_registry_id"] == "42"
        mock_kb.link_kb_to_assistant.assert_called_once_with(7, "kb-1")
        mock_db.update_workshop_session_kb.assert_called_once()

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers.workshop_kb")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_quota_second_document_rejected(
            self, mock_db, mock_decode, mock_kb):
        from fastapi import HTTPException
        from lamb.modules.workshop import routers

        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _own_assistant()
        mock_db.get_workshop_session_by_id.return_value = {
            "id": "ws-1", "activity_id": 1,
            "document_file_id": "1", "document_status": "completed",
        }
        file = MagicMock(filename="doc.txt", content_type="text/plain")
        file.read = AsyncMock(return_value=b"hello")

        with pytest.raises(HTTPException) as exc:
            await routers.attach_workshop_document(
                session_id="ws-1", assistant_id=7, file=file, token="tok")
        assert exc.value.status_code == 429


class TestKbRoutes:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers.workshop_kb")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_connect_returns_probe_results(
            self, mock_db, mock_decode, mock_kb):
        from lamb.modules.workshop import routers

        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _own_assistant()
        mock_db.get_workshop_session_by_id.return_value = {
            "id": "ws-1", "activity_id": 1, "kb_id": "kb-1"}
        mock_db.get_lti_activity_by_id.return_value = {"id": 1}
        mock_kb.query_session_kb = AsyncMock(return_value={
            "results": [{"similarity": 0.9, "data": "hit"}], "count": 1})
        mock_kb.link_kb_to_assistant = MagicMock(return_value=True)

        result = await routers.connect_workshop_kb(
            session_id="ws-1", assistant_id=7,
            body={"query": "fractions"}, token="tok")

        assert result["success"] is True
        assert result["kb_id"] == "kb-1"
        assert result["results"][0]["data"] == "hit"
        mock_kb.link_kb_to_assistant.assert_called_once_with(7, "kb-1")

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers.workshop_kb")
    @patch("lamb.auth.decode_token")
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_kb_query_without_kb_rejected(
            self, mock_db, mock_decode, mock_kb):
        from fastapi import HTTPException
        from lamb.modules.workshop import routers

        mock_decode.return_value = _token_payload()
        mock_db.get_assistant_by_id.return_value = _own_assistant()
        mock_db.get_workshop_session_by_id.return_value = {
            "id": "ws-1", "activity_id": 1, "kb_id": None}

        with pytest.raises(HTTPException) as exc:
            await routers.query_workshop_kb(
                session_id="ws-1", assistant_id=7,
                body={"query": "q"}, token="tok")
        assert exc.value.status_code == 400

