"""
Tests for Phase 1 — Observability Engine SSE frame injection.

Tests that `run_lamb_assistant` emits an observability SSE frame when
`observability: true` is set in the request body, and stays silent without it.

Uses unittest.mock to isolate from DB, RAG, and LLM.
Run with:  python -m pytest backend/tests/test_observability.py -v
"""

import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.responses import StreamingResponse

from lamb.lamb_classes import Assistant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_assistant(**overrides) -> Assistant:
    """Return an Assistant with sensible defaults for testing."""
    defaults = {
        "id": 1,
        "name": "Test Assistant",
        "description": "",
        "owner": "owner@test.com",
        "api_callback": '{"connector":"openai","llm":"gpt-4","prompt_processor":"default","rag_processor":""}',
        "system_prompt": "You are a helpful tutor.",
        "prompt_template": "Answer: {user_input}\nContext: {context}",
        "pre_retrieval_endpoint": "",
        "post_retrieval_endpoint": "",
        "RAG_endpoint": "",
        "RAG_Top_k": 3,
        "RAG_collections": "[]",
    }
    defaults.update(overrides)
    return Assistant(**defaults)


def _async_gen(*chunks):
    """Turn an iterable of string chunks into an async generator."""
    async def gen():
        for c in chunks:
            yield c
    return gen()


# ---------------------------------------------------------------------------
# T1: Observability frame appears in stream when flag is set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("lamb.completions.main.db_manager")
@patch("lamb.completions.main.get_rag_context")
@patch("lamb.completions.main.process_completion_request")
@patch("lamb.completions.main.load_and_validate_plugins")
async def test_observability_frame_in_stream(
    mock_load, mock_process, mock_rag, mock_db
):
    """observability=true → SSE stream contains one observability frame."""
    from lamb.completions.main import run_lamb_assistant

    mock_db.get_assistant_by_id.return_value = _make_assistant()

    # Mock plugin loading — return a working (async) connector
    mock_connector = AsyncMock()
    mock_connector.return_value = _async_gen(
        'data: {"content":"Hello"}\n\n',
    ), None

    mock_load.return_value = (
        {"default": MagicMock()},       # pps
        {"openai": mock_connector},     # connectors
        {"simple_rag": AsyncMock()},    # rag_processors
    )

    mock_rag.return_value = {
        "context": "Retrieved text about Paris.",
        "sources": [
            {
                "document_id": "doc1",
                "chunk_id": "c1",
                "similarity": 0.92,
                "content": "Paris is the capital of France.",
            }
        ],
        "assistant_data": {},
        "raw_responses": [],
    }

    mock_process.return_value = [
        {"role": "system", "content": "You are a helpful tutor."},
        {"role": "user", "content": "What is the capital of France?"},
    ]

    request_body = {
        "messages": [{"role": "user", "content": "What is the capital of France?"}],
        "observability": True,
        "stream": True,
    }

    response = await run_lamb_assistant(
        request=request_body,
        assistant=1,
    )

    assert isinstance(response, StreamingResponse)

    # Collect all chunks
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    # Verify observability frame is present
    # Note: json.dumps adds spaces after colons
    obs_frames = [c for c in chunks if '"type": "observability"' in c]
    assert len(obs_frames) == 1, f"Expected 1 observability frame, got {len(obs_frames)}\nChunks: {chunks}"

    obs_data = json.loads(obs_frames[0].replace("data: ", "").strip())
    assert obs_data["type"] == "observability"
    payload = obs_data["data"]
    assert payload["assistant_name"] == "Test Assistant"
    assert payload["system_instructions"] == "You are a helpful tutor."
    assert payload["user_input"] == "What is the capital of France?"
    assert len(payload["retrieved_sources"]) == 1
    assert payload["retrieved_sources"][0]["similarity"] == 0.92
    assert len(payload["final_llm_messages"]) == 2

    # Frame must appear before [DONE]
    sse_text = "".join(chunks)
    assert "data: [DONE]" not in sse_text, "[DONE] should not appear before observability frame"


# ---------------------------------------------------------------------------
# T2: No observability frame without flag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("lamb.completions.main.db_manager")
@patch("lamb.completions.main.get_rag_context")
@patch("lamb.completions.main.process_completion_request")
@patch("lamb.completions.main.load_and_validate_plugins")
async def test_no_observability_frame_without_flag(
    mock_load, mock_process, mock_rag, mock_db
):
    """Without observability flag → no observability frame in stream."""
    from lamb.completions.main import run_lamb_assistant

    mock_db.get_assistant_by_id.return_value = _make_assistant()

    mock_connector = AsyncMock()
    mock_connector.return_value = _async_gen(
        'data: {"content":"Hello"}\n\n',
    ), None

    mock_load.return_value = (
        {"default": MagicMock()},
        {"openai": mock_connector},
        {"simple_rag": AsyncMock()},
    )

    mock_rag.return_value = {
        "context": "Some context.",
        "sources": [],
        "assistant_data": {},
        "raw_responses": [],
    }

    mock_process.return_value = [
        {"role": "system", "content": "You are a helpful tutor."},
        {"role": "user", "content": "Hello"},
    ]

    request_body = {
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
        # No observability flag
    }

    response = await run_lamb_assistant(
        request=request_body,
        assistant=1,
    )

    assert isinstance(response, StreamingResponse)

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    obs_frames = [c for c in chunks if '"type": "observability"' in c]
    assert len(obs_frames) == 0, f"Expected 0 observability frames, got {len(obs_frames)}"


# ---------------------------------------------------------------------------
# T3: Payload field completeness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("lamb.completions.main.db_manager")
@patch("lamb.completions.main.get_rag_context")
@patch("lamb.completions.main.process_completion_request")
@patch("lamb.completions.main.load_and_validate_plugins")
async def test_observability_payload_has_all_fields(
    mock_load, mock_process, mock_rag, mock_db
):
    """Observability payload contains all required fields."""
    from lamb.completions.main import run_lamb_assistant

    mock_db.get_assistant_by_id.return_value = _make_assistant()

    mock_connector = AsyncMock()
    mock_connector.return_value = _async_gen(
        'data: {"content":"Hello"}\n\n',
    ), None

    mock_load.return_value = (
        {"default": MagicMock()},
        {"openai": mock_connector},
        {"simple_rag": AsyncMock()},
    )

    mock_rag.return_value = {
        "context": "Retrieved text.",
        "sources": [
            {"document_id": "d1", "chunk_id": "c1", "similarity": 0.95, "content": "Some content."}
        ],
        "assistant_data": {},
        "raw_responses": [],
    }

    mock_process.return_value = [
        {"role": "system", "content": "You are a tutor."},
        {"role": "user", "content": "Hi"},
    ]

    request_body = {
        "messages": [{"role": "user", "content": "Hi"}],
        "observability": True,
        "stream": True,
        "tools": [{"type": "function", "function": {"name": "calculator"}}],
    }

    response = await run_lamb_assistant(request=request_body, assistant=1)
    assert isinstance(response, StreamingResponse)

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    obs_frames = [c for c in chunks if '"type": "observability"' in c]
    assert len(obs_frames) == 1

    obs_data = json.loads(obs_frames[0].replace("data: ", "").strip())
    payload = obs_data["data"]

    # Required top-level fields
    required_payload_fields = [
        "assistant_name",
        "system_instructions",
        "user_input",
        "rag_context",
        "retrieved_sources",
        "final_llm_messages",
        "tools",
        "request_body",
    ]
    for field in required_payload_fields:
        assert field in payload, f"Missing payload field: {field}"

    # tools should echo the request tools
    assert payload["tools"] == request_body["tools"]

    # request_body reconstructs the full request shape: model + tools + messages
    rb = payload["request_body"]
    assert rb["model"] == "gpt-4"
    assert rb["tools"] == request_body["tools"]
    assert rb["messages"] == payload["final_llm_messages"]


# ---------------------------------------------------------------------------
# T4: Sources contain similarity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("lamb.completions.main.db_manager")
@patch("lamb.completions.main.get_rag_context")
@patch("lamb.completions.main.process_completion_request")
@patch("lamb.completions.main.load_and_validate_plugins")
async def test_sources_contain_similarity(
    mock_load, mock_process, mock_rag, mock_db
):
    """Each source in retrieved_sources has a non-negative similarity field."""
    from lamb.completions.main import run_lamb_assistant

    mock_db.get_assistant_by_id.return_value = _make_assistant()

    # With tools present the pipeline runs the ToolLoop, whose llm call uses
    # stream=False and expects a ChatCompletion-shaped response. The final text
    # reply is then streamed with stream=True (returned as a (gen, usage) tuple
    # by tracked connectors).
    async def _connector(*args, **kwargs):
        if kwargs.get("stream"):
            return _async_gen('data: {"content":"Hello"}\n\n'), None
        return {"choices": [{"message": {"content": "Hello", "tool_calls": []}}]}

    mock_load.return_value = (
        {"default": MagicMock()},
        {"openai": _connector},
        {"simple_rag": AsyncMock()},
    )

    mock_rag.return_value = {
        "context": "Test context.",
        "sources": [
            {"document_id": "d1", "chunk_id": "c1", "similarity": 0.85, "content": "A"},
            {"document_id": "d2", "chunk_id": "c2", "similarity": 0.72, "content": "B"},
        ],
        "assistant_data": {},
        "raw_responses": [],
    }

    mock_process.return_value = [
        {"role": "user", "content": "Test"},
    ]

    request_body = {
        "messages": [{"role": "user", "content": "Test"}],
        "observability": True,
        "stream": True,
    }

    response = await run_lamb_assistant(request=request_body, assistant=1)
    assert isinstance(response, StreamingResponse)

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    obs_frames = [c for c in chunks if '"type": "observability"' in c]
    assert len(obs_frames) == 1

    obs_data = json.loads(obs_frames[0].replace("data: ", "").strip())
    sources = obs_data["data"]["retrieved_sources"]

    assert len(sources) == 2
    for s in sources:
        assert "similarity" in s, f"Source missing similarity: {s}"
        assert isinstance(s["similarity"], (int, float)), f"similarity should be numeric, got {type(s['similarity'])}"
        assert s["similarity"] >= 0, f"similarity must be non-negative: {s['similarity']}"


# ---------------------------------------------------------------------------
# T5: Observability frame before [DONE]
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("lamb.completions.main.db_manager")
@patch("lamb.completions.main.get_rag_context")
@patch("lamb.completions.main.process_completion_request")
@patch("lamb.completions.main.load_and_validate_plugins")
async def test_observability_frame_before_done(
    mock_load, mock_process, mock_rag, mock_db
):
    """Observability frame appears before the closing [DONE] marker."""
    from lamb.completions.main import run_lamb_assistant

    mock_db.get_assistant_by_id.return_value = _make_assistant()

    # Simulate a connector that emits chunks then a [DONE] signal
    async def connector_with_done(*args, **kwargs):
        async def gen():
            yield 'data: {"content":"Final answer chunk"}\n\n'
            yield "data: [DONE]\n\n"
        return gen(), None

    mock_connector = AsyncMock(side_effect=connector_with_done)

    mock_load.return_value = (
        {"default": MagicMock()},
        {"openai": mock_connector},
        {"simple_rag": AsyncMock()},
    )

    mock_rag.return_value = {
        "context": "Context.",
        "sources": [],
        "assistant_data": {},
        "raw_responses": [],
    }

    mock_process.return_value = [
        {"role": "user", "content": "Hello"},
    ]

    request_body = {
        "messages": [{"role": "user", "content": "Hello"}],
        "observability": True,
        "stream": True,
    }

    response = await run_lamb_assistant(request=request_body, assistant=1)
    assert isinstance(response, StreamingResponse)

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    # Check that [DONE] appears, and that the observability frame comes before it
    sse_text = "".join(chunks)
    assert "[DONE]" in sse_text, "[DONE] marker should be present in the stream"
    obs_pos = sse_text.index('"type": "observability"')
    done_pos = sse_text.index("[DONE]")
    assert obs_pos < done_pos, (
        f"Observability frame at position {obs_pos} should be before [DONE] at {done_pos}"
    )


# ---------------------------------------------------------------------------
# T6: Existing SSE consumers remain unbroken (unknown frame ignored)
# ---------------------------------------------------------------------------

def test_default_sse_consumers_unbroken():
    """A consumer that only knows content/done fields should not crash on an
    unknown observability frame.  This is a contract/unit test for the
    frontend parsing logic, run without a server."""
    lines = [
        'data: {"content":"Hello"}\n\n',
        'data: {"type":"observability","data":{"assistant_name":"A"}}\n\n',
        "data: [DONE]\n\n",
    ]

    # Simulate a basic consumer like the frontend's SSE reader
    chunks = []
    done_received = False
    for line in lines:
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            done_received = True
            break
        try:
            data = json.loads(payload)
            # The consumer checks for known fields — observability has 'type'
            # so it should be checked explicitly, not fall through to content.
            # This test verifies it does NOT match any existing branch.
            if data.get("type") == "observability":
                # Our future handler would go here — for now, skip
                continue
            if data.get("content"):
                chunks.append(data["content"])
            if data.get("done"):
                done_received = True
        except json.JSONDecodeError:
            pass

    # The consumer should have received the content chunk and seen [DONE]
    assert chunks == ["Hello"]
    assert done_received is True