"""D3 tests — the A/B experiment plumbing.

"Turn the knowledge base off" must be a *per-request* switch that also removes
the retrieval tool (otherwise the model simply fetches the same material and
the comparison shows nothing), and it must never reach the assistant's saved
configuration — that is exactly how the original S1 bug leaked into every later
turn.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from lamb.lamb_classes import Assistant
from lamb.modules.workshop import routers


def _token_payload(**overrides):
    payload = {
        "scope": "workshop_student",
        "session_id": "ws-1",
        "activity_id": 1,
        "email": "student@lamb-lti.local",
        "organization_id": 10,
    }
    payload.update(overrides)
    return payload


def _assistant(**overrides):
    opts = dict(
        id=7, name="A", description="", owner="student@lamb-lti.local",
        api_callback="{}", system_prompt="S", prompt_template="T",
        organization_id=10, RAG_Top_k=3, RAG_collections="kb-1",
        pre_retrieval_endpoint="", post_retrieval_endpoint="", RAG_endpoint="",
    )
    opts.update(overrides)
    return Assistant(**opts)


TOOLS = [
    {"type": "function", "function": {"name": "calculator"}},
    {"type": "function", "function": {"name": "kb_query"}},
]


async def _chat(body, mock_db, mock_run):
    """Invoke the workshop chat route with the standard mocks."""
    with patch("lamb.auth.decode_token",
               return_value=_token_payload()), \
         patch.object(routers, "_db_manager", mock_db), \
         patch("lamb.completions.main.run_lamb_assistant", mock_run):
        return await routers.chat_with_workshop_assistant(
            session_id="ws-1", assistant_id=7, body=body, token="tok")


class TestRagModeSwitch:
    @pytest.mark.asyncio
    async def test_default_is_on_and_keeps_every_tool(self):
        mock_db = MagicMock()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_run = AsyncMock(return_value=StreamingResponse(iter([])))

        await _chat(
            {"messages": [{"role": "user", "content": "hi"}], "tools": TOOLS},
            mock_db, mock_run)

        request = mock_run.call_args.kwargs["request"]
        assert "_workshop_disable_rag" not in request
        names = [t["function"]["name"] for t in request["tools"]]
        assert names == ["calculator", "kb_query"]

    @pytest.mark.asyncio
    async def test_off_sets_the_private_key_and_drops_kb_query(self):
        mock_db = MagicMock()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_run = AsyncMock(return_value=StreamingResponse(iter([])))

        await _chat(
            {"messages": [{"role": "user", "content": "hi"}],
             "tools": TOOLS, "rag_mode": "off"},
            mock_db, mock_run)

        request = mock_run.call_args.kwargs["request"]
        assert request["_workshop_disable_rag"] is True
        names = [t["function"]["name"] for t in request["tools"]]
        assert names == ["calculator"]

    @pytest.mark.asyncio
    async def test_off_with_no_other_tools_passes_none(self):
        mock_db = MagicMock()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_run = AsyncMock(return_value=StreamingResponse(iter([])))

        await _chat(
            {"messages": [{"role": "user", "content": "hi"}],
             "tools": [{"type": "function", "function": {"name": "kb_query"}}],
             "rag_mode": "off"},
            mock_db, mock_run)

        assert mock_run.call_args.kwargs["request"]["tools"] is None

    @pytest.mark.asyncio
    async def test_invalid_rag_mode_is_rejected(self):
        mock_db = MagicMock()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_run = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await _chat(
                {"messages": [], "rag_mode": "maybe"}, mock_db, mock_run)
        assert exc.value.status_code == 400
        mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_experiment_never_touches_saved_configuration(self):
        """The switch is per request: RAG_collections must stay untouched."""
        mock_db = MagicMock()
        mock_db.get_assistant_by_id.return_value = _assistant()
        mock_run = AsyncMock(return_value=StreamingResponse(iter([])))

        await _chat(
            {"messages": [{"role": "user", "content": "hi"}],
             "tools": TOOLS, "rag_mode": "off"},
            mock_db, mock_run)

        mock_db.update_assistant.assert_not_called()


class TestProxyStripsPrivateKeys:
    """C10: an external body must not be able to degrade RAG."""

    @staticmethod
    def _auth():
        auth = MagicMock()
        auth.user = {"id": 1, "email": "u@x.com"}
        return auth

    @staticmethod
    def _request(body):
        request = MagicMock()
        request.json = AsyncMock(return_value=body)
        return request

    @pytest.mark.asyncio
    async def test_private_key_is_removed_before_the_pipeline(self):
        from creator_interface import learning_assistant_proxy as proxy

        passed_body = {}

        async def fake_run(request, assistant, headers=None):
            passed_body.update(request)
            return MagicMock()

        with patch.object(proxy, "verify_assistant_access_via_auth_context",
                          return_value=True), \
             patch.object(proxy, "run_lamb_assistant", fake_run):
            await proxy.proxy_assistant_chat(
                assistant_id=7,
                request=self._request({
                    "messages": [{"role": "user", "content": "hi"}],
                    "_workshop_disable_rag": True,
                    "disable_rag": True,
                }),
                auth=self._auth(),
            )

        assert "_workshop_disable_rag" not in passed_body
        # Unrelated (non-namespaced) keys are not our business.
        assert passed_body.get("disable_rag") is True

    @pytest.mark.asyncio
    async def test_private_key_is_stripped_even_alone(self):
        from creator_interface import learning_assistant_proxy as proxy

        passed_body = {}

        async def fake_run(request, assistant, headers=None):
            passed_body.update(request)
            return MagicMock()

        with patch.object(proxy, "verify_assistant_access_via_auth_context",
                          return_value=True), \
             patch.object(proxy, "run_lamb_assistant", fake_run):
            await proxy.proxy_assistant_chat(
                assistant_id=7,
                request=self._request({
                    "messages": [{"role": "user", "content": "hi"}],
                    "_workshop_disable_rag": True,
                }),
                auth=self._auth(),
            )

        assert "_workshop_disable_rag" not in passed_body

    @pytest.mark.asyncio
    async def test_ordinary_requests_are_untouched(self):
        from creator_interface import learning_assistant_proxy as proxy

        passed_body = {}

        async def fake_run(request, assistant, headers=None):
            passed_body.update(request)
            return MagicMock()

        with patch.object(proxy, "verify_assistant_access_via_auth_context",
                          return_value=True), \
             patch.object(proxy, "run_lamb_assistant", fake_run):
            await proxy.proxy_assistant_chat(
                assistant_id=7,
                request=self._request({
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                }),
                auth=self._auth(),
            )

        assert passed_body["messages"] == [{"role": "user", "content": "hi"}]
        assert passed_body["stream"] is True