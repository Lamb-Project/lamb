"""D1 tests — the observability panel is fed *before* the first LLM call.

The panel used to appear only after the model had already answered, which made
it useless as a "look at what your assistant is about to receive" tool: by the
time it rendered, the teaching moment had passed. These tests pin the frame
order, the payload shape, and the failure mode that removing the eager
connector call introduced (a crash inside the generator must become an error
frame, not a hung stream).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import StreamingResponse

from lamb.completions import main as completions_main


def _make_assistant(**overrides):
    assistant = MagicMock()
    assistant.id = 1
    assistant.name = "Tutor"
    assistant.system_prompt = "You are a tutor."
    assistant.metadata = json.dumps({"connector": "openai", "llm": "gpt-4"})
    assistant.organization_id = 10
    assistant.owner = "student@lamb-lti.local"
    assistant.RAG_collections = ""
    assistant.RAG_Top_k = 3
    for key, value in overrides.items():
        setattr(assistant, key, value)
    return assistant


def _async_gen(*chunks):
    async def generator():
        for chunk in chunks:
            yield chunk
    return generator()


async def _drain(response: StreamingResponse):
    out = []
    async for chunk in response.body_iterator:
        out.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    return out


def _frames(chunks, frame_type="observability"):
    """Parse every SSE frame of a given type, in order."""
    parsed = []
    for chunk in chunks:
        for line in chunk.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if data.get("type") == frame_type:
                parsed.append(data)
    return parsed


class TestRequestFrameOrder:
    """C11: the request frame is the first thing on the wire."""

    @pytest.mark.asyncio
    @patch("lamb.completions.main.ToolLoop")
    @patch("lamb.completions.main.db_manager")
    @patch("lamb.completions.main.get_rag_context")
    @patch("lamb.completions.main.process_completion_request")
    @patch("lamb.completions.main.load_and_validate_plugins")
    async def test_request_frame_precedes_the_first_content_chunk(
            self, mock_load, mock_process, mock_rag, mock_db, mock_tool_loop):
        mock_db.get_assistant_by_id.return_value = _make_assistant()
        mock_rag.return_value = {"context": "", "sources": []}
        mock_process.return_value = [
            {"role": "system", "content": "You are a tutor."},
            {"role": "user", "content": "Hi"},
        ]

        connector = AsyncMock()
        connector.return_value = (_async_gen(
            'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
            "data: [DONE]\n\n",
        ), None)
        mock_load.return_value = (
            {"default": MagicMock()}, {"openai": connector},
            {"simple_rag": AsyncMock()})

        # The tool loop yields a tool round, then the final text stream.
        async def fake_run(**kwargs):
            yield {"type": "result", "messages": kwargs["messages"]}
        loop = MagicMock()
        loop.run = fake_run
        mock_tool_loop.return_value = loop

        request = {
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
            "observability": True,
            "tools": [{"type": "function", "function": {"name": "calculator"}}],
        }
        response = await completions_main.run_lamb_assistant(
            request=request, assistant=1)
        chunks = await _drain(response)

        obs = _frames(chunks)
        assert len(obs) == 2, chunks
        assert obs[0]["data"]["phase"] == "request"
        assert obs[1]["data"]["phase"] == "result"

        # …and the request frame is emitted before any content chunk.
        joined = "".join(chunks)
        assert joined.index('"phase": "request"') < joined.index('"delta"')

    @pytest.mark.asyncio
    @patch("lamb.completions.main.ToolLoop")
    @patch("lamb.completions.main.db_manager")
    @patch("lamb.completions.main.get_rag_context")
    @patch("lamb.completions.main.process_completion_request")
    @patch("lamb.completions.main.load_and_validate_plugins")
    async def test_tool_path_does_not_pre_call_the_connector(
            self, mock_load, mock_process, mock_rag, mock_db, mock_tool_loop):
        """The eager call whose result was discarded is gone (D1/C11).

        It cost a full model turn before the panel could render, and its output
        was thrown away. Removing it means the tool path calls the connector
        exactly once for the final reply.
        """
        mock_db.get_assistant_by_id.return_value = _make_assistant()
        mock_rag.return_value = {"context": "", "sources": []}
        mock_process.return_value = [{"role": "user", "content": "Hi"}]

        connector = AsyncMock()
        connector.return_value = (_async_gen("data: [DONE]\n\n"), None)
        mock_load.return_value = (
            {"default": MagicMock()}, {"openai": connector},
            {"simple_rag": AsyncMock()})

        async def fake_run(**kwargs):
            yield {"type": "result", "messages": kwargs["messages"]}
        loop = MagicMock()
        loop.run = fake_run
        mock_tool_loop.return_value = loop

        request = {
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
            "observability": True,
            "tools": [{"type": "function", "function": {"name": "calculator"}}],
        }
        stream = await completions_main.run_lamb_assistant(
            request=request, assistant=1)

        # Nothing has been called yet: the response is a lazy generator.
        assert connector.await_count == 0
        await _drain(stream)
        # Exactly one call — the final streaming reply.
        assert connector.await_count == 1

    @pytest.mark.asyncio
    @patch("lamb.completions.main.db_manager")
    @patch("lamb.completions.main.get_rag_context")
    @patch("lamb.completions.main.process_completion_request")
    @patch("lamb.completions.main.load_and_validate_plugins")
    async def test_non_tool_path_is_unchanged(
            self, mock_load, mock_process, mock_rag, mock_db):
        """Regression: the standard streaming path still emits one result frame."""
        mock_db.get_assistant_by_id.return_value = _make_assistant()
        mock_rag.return_value = {"context": "", "sources": []}
        mock_process.return_value = [{"role": "user", "content": "Hi"}]

        connector = AsyncMock()
        connector.return_value = (_async_gen(
            'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n',
            "data: [DONE]\n\n",
        ), None)
        mock_load.return_value = (
            {"default": MagicMock()}, {"openai": connector},
            {"simple_rag": AsyncMock()})

        request = {
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
            "observability": True,
        }
        response = await completions_main.run_lamb_assistant(
            request=request, assistant=1)
        chunks = await _drain(response)

        obs = _frames(chunks)
        assert len(obs) == 1
        assert obs[0]["data"]["phase"] == "result"
        assert connector.await_count == 1


class TestObservabilityPayload:
    def test_phase_and_rag_mode_default_to_result_on(self):
        payload = completions_main.build_observability_payload(
            _make_assistant(), {"messages": []}, None, [])
        assert payload["data"]["phase"] == "result"
        assert payload["data"]["rag_mode"] == "on"

    def test_request_phase_reports_an_honest_rag_state(self):
        """RAG off must not be papered over with a made-up context."""
        payload = completions_main.build_observability_payload(
            _make_assistant(), {"messages": []}, None, [],
            phase="request", rag_mode="off")
        assert payload["data"]["phase"] == "request"
        assert payload["data"]["rag_mode"] == "off"
        assert payload["data"]["rag_context"] == ""
        assert payload["data"]["retrieved_sources"] == []

    def test_request_phase_includes_retrieved_sources_when_available(self):
        rag_context = {
            "context": "Fractions are parts of a whole.",
            "sources": [{"document_id": "d1", "chunk_id": "c1",
                         "similarity": 0.9, "content": "abc"}],
        }
        payload = completions_main.build_observability_payload(
            _make_assistant(), {"messages": []}, rag_context, [],
            phase="request", rag_mode="on")
        assert payload["data"]["retrieved_sources"][0]["similarity"] == 0.9


class TestErrorFrames:
    """A crash after the headers are sent must not hang the browser."""

    @pytest.mark.asyncio
    @patch("lamb.completions.main.ToolLoop")
    @patch("lamb.completions.main.db_manager")
    @patch("lamb.completions.main.get_rag_context")
    @patch("lamb.completions.main.process_completion_request")
    @patch("lamb.completions.main.load_and_validate_plugins")
    async def test_tool_generator_crash_becomes_an_error_frame(
            self, mock_load, mock_process, mock_rag, mock_db, mock_tool_loop):
        mock_db.get_assistant_by_id.return_value = _make_assistant()
        mock_rag.return_value = {"context": "", "sources": []}
        mock_process.return_value = [{"role": "user", "content": "Hi"}]
        mock_load.return_value = (
            {"default": MagicMock()}, {"openai": AsyncMock()},
            {"simple_rag": AsyncMock()})

        async def exploding_run(**kwargs):
            raise RuntimeError("connector exploded")
            yield  # pragma: no cover - makes this an async generator
        loop = MagicMock()
        loop.run = exploding_run
        mock_tool_loop.return_value = loop

        request = {
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
            "observability": True,
            "tools": [{"type": "function", "function": {"name": "calculator"}}],
        }
        response = await completions_main.run_lamb_assistant(
            request=request, assistant=1)
        chunks = await _drain(response)

        errors = _frames(chunks, "error")
        assert len(errors) == 1
        assert "connector exploded" in errors[0]["data"]["message"]
        # The request frame still arrived first — the student learns what was
        # about to be sent even though the call failed.
        assert _frames(chunks)[0]["data"]["phase"] == "request"

    @pytest.mark.asyncio
    @patch("lamb.completions.main.db_manager")
    @patch("lamb.completions.main.get_rag_context")
    @patch("lamb.completions.main.process_completion_request")
    @patch("lamb.completions.main.load_and_validate_plugins")
    async def test_standard_stream_crash_becomes_an_error_frame(
            self, mock_load, mock_process, mock_rag, mock_db):
        mock_db.get_assistant_by_id.return_value = _make_assistant()
        mock_rag.return_value = {"context": "", "sources": []}
        mock_process.return_value = [{"role": "user", "content": "Hi"}]

        async def exploding_generator():
            yield 'data: {"choices":[{"delta":{"content":"par"}}]}\n\n'
            raise RuntimeError("mid-stream failure")

        connector = AsyncMock()
        connector.return_value = (exploding_generator(), None)
        mock_load.return_value = (
            {"default": MagicMock()}, {"openai": connector},
            {"simple_rag": AsyncMock()})

        response = await completions_main.run_lamb_assistant(
            request={"messages": [{"role": "user", "content": "Hi"}],
                     "stream": True, "observability": True},
            assistant=1)
        chunks = await _drain(response)

        errors = _frames(chunks, "error")
        assert len(errors) == 1
        assert "mid-stream failure" in errors[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_error_frame_shape_matches_the_sse_dialect(self):
        frame = completions_main.error_frame("boom")
        assert frame.startswith("data: ")
        assert frame.endswith("\n\n")
        payload = json.loads(frame[6:].strip())
        assert payload["type"] == "error"
        assert payload["data"]["message"] == "boom"


class TestWorkshopRagMode:
    """C10: the private key drives RAG, and only the workshop sets it."""

    def test_default_is_on(self):
        assert completions_main.workshop_rag_mode({}) == "on"

    def test_private_key_turns_it_off(self):
        assert completions_main.workshop_rag_mode(
            {"_workshop_disable_rag": True}) == "off"

    def test_truthy_lookalikes_do_not_turn_it_off(self):
        assert completions_main.workshop_rag_mode(
            {"_workshop_disable_rag": "yes"}) == "on"
        assert completions_main.workshop_rag_mode(
            {"disable_rag": True}) == "on"

    @pytest.mark.asyncio
    @patch("lamb.completions.main.db_manager")
    @patch("lamb.completions.main.get_rag_context", new_callable=AsyncMock)
    @patch("lamb.completions.main.process_completion_request")
    @patch("lamb.completions.main.load_and_validate_plugins")
    async def test_rag_is_skipped_when_off(
            self, mock_load, mock_process, mock_rag, mock_db):
        mock_db.get_assistant_by_id.return_value = _make_assistant()
        mock_process.return_value = [{"role": "user", "content": "Hi"}]
        connector = AsyncMock()
        connector.return_value = (_async_gen("data: [DONE]\n\n"), None)
        mock_load.return_value = (
            {"default": MagicMock()}, {"openai": connector},
            {"simple_rag": AsyncMock()})

        response = await completions_main.run_lamb_assistant(
            request={"messages": [{"role": "user", "content": "Hi"}],
                     "stream": True, "observability": True,
                     "_workshop_disable_rag": True},
            assistant=1)
        chunks = await _drain(response)

        mock_rag.assert_not_awaited()
        assert _frames(chunks)[0]["data"]["rag_mode"] == "off"

    @pytest.mark.asyncio
    @patch("lamb.completions.main.db_manager")
    @patch("lamb.completions.main.get_rag_context", new_callable=AsyncMock)
    @patch("lamb.completions.main.process_completion_request")
    @patch("lamb.completions.main.load_and_validate_plugins")
    async def test_private_key_never_reaches_the_connector(
            self, mock_load, mock_process, mock_rag, mock_db):
        """The connector forwards `body` verbatim — internal keys must be gone.

        `connectors/*.py` do `params = body.copy()` and hand it to the provider,
        so leaving `_workshop_disable_rag` in the request would send an unknown
        parameter to the model API.
        """
        mock_db.get_assistant_by_id.return_value = _make_assistant()
        mock_process.return_value = [{"role": "user", "content": "Hi"}]
        connector = AsyncMock()
        connector.return_value = (_async_gen("data: [DONE]\n\n"), None)
        mock_load.return_value = (
            {"default": MagicMock()}, {"openai": connector},
            {"simple_rag": AsyncMock()})

        response = await completions_main.run_lamb_assistant(
            request={"messages": [{"role": "user", "content": "Hi"}],
                     "stream": True, "observability": True,
                     "_workshop_disable_rag": True},
            assistant=1)
        await _drain(response)

        body_sent = connector.await_args.kwargs["body"]
        assert "_workshop_disable_rag" not in body_sent

    @pytest.mark.asyncio
    @patch("lamb.completions.main.db_manager")
    @patch("lamb.completions.main.get_rag_context", new_callable=AsyncMock)
    @patch("lamb.completions.main.process_completion_request")
    @patch("lamb.completions.main.load_and_validate_plugins")
    async def test_rag_runs_normally_when_on(
            self, mock_load, mock_process, mock_rag, mock_db):
        mock_db.get_assistant_by_id.return_value = _make_assistant()
        mock_rag.return_value = {"context": "ctx", "sources": []}
        mock_process.return_value = [{"role": "user", "content": "Hi"}]
        connector = AsyncMock()
        connector.return_value = (_async_gen("data: [DONE]\n\n"), None)
        mock_load.return_value = (
            {"default": MagicMock()}, {"openai": connector},
            {"simple_rag": AsyncMock()})

        response = await completions_main.run_lamb_assistant(
            request={"messages": [{"role": "user", "content": "Hi"}],
                     "stream": True, "observability": True},
            assistant=1)
        chunks = await _drain(response)

        mock_rag.assert_awaited_once()
        assert _frames(chunks)[0]["data"]["rag_mode"] == "on"
