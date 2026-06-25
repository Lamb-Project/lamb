"""Tests for the opt-in `include_eval_metadata` response field.

When a caller sets `include_eval_metadata=True`, `run_lamb_assistant` attaches
the retrieved RAG context to the non-streaming response under
`eval_metadata.rag_context.context` (consumed by the lamb-eval framework). When
the flag is absent the response is unchanged. These tests exercise that logic
directly with the heavy dependencies (DB, plugin loading, connector, RAG) mocked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_BACKEND_ROOT = Path(__file__).parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from lamb.completions import main as completions_main  # noqa: E402

_RETRIEVED = "RETRIEVED CHUNK TEXT"
_RAG_CONTEXT = {"context": _RETRIEVED, "sources": [{"title": "doc", "score": 0.9}]}


def _patches(rag_context):
    """Patch every external dependency of run_lamb_assistant.

    connector is "ollama" so the token-usage logging branch is skipped.
    """
    assistant_details = MagicMock(owner="creator@example.com", organization_id=None)
    plugin_config = {
        "connector": "ollama",
        "rag_processor": "knowledge_store_rag",
        "llm": "test-llm",
        "document_rag": "",
    }
    connector_func = AsyncMock(return_value={"id": "chatcmpl-x", "choices": [{"message": {"content": "hi"}}]})
    return [
        patch.object(completions_main, "get_assistant_details", return_value=assistant_details),
        patch.object(completions_main, "parse_plugin_config", return_value=plugin_config),
        patch.object(completions_main, "_provider_for_connector", return_value=None),
        patch.object(completions_main, "maybe_route_non_streaming_task", AsyncMock(return_value=None)),
        patch.object(
            completions_main,
            "load_and_validate_plugins",
            return_value=(MagicMock(), {"ollama": connector_func}, MagicMock()),
        ),
        patch.object(completions_main, "get_rag_context", AsyncMock(return_value=rag_context)),
        patch.object(completions_main, "process_completion_request", return_value=[{"role": "user", "content": "q"}]),
    ]


async def _run(include_eval_metadata, rag_context=_RAG_CONTEXT):
    request = {"model": "lamb_assistant.1", "messages": [{"role": "user", "content": "q"}], "stream": False}
    ctxs = _patches(rag_context)
    for c in ctxs:
        c.start()
    try:
        resp = await completions_main.run_lamb_assistant(
            request=request, assistant=1, headers={}, include_eval_metadata=include_eval_metadata
        )
    finally:
        for c in ctxs:
            c.stop()
    return json.loads(resp.body)


@pytest.mark.asyncio
async def test_flag_true_attaches_retrieved_context():
    body = await _run(include_eval_metadata=True)
    assert body["eval_metadata"]["rag_context"]["context"] == _RETRIEVED
    assert body["eval_metadata"]["rag_context"]["sources"]
    # The base OpenAI response is preserved.
    assert body["choices"][0]["message"]["content"] == "hi"


@pytest.mark.asyncio
async def test_flag_absent_leaves_response_unchanged():
    body = await _run(include_eval_metadata=False)
    assert "eval_metadata" not in body


@pytest.mark.asyncio
async def test_flag_true_but_no_rag_context_omits_eval_metadata():
    # A non-dict rag_context (e.g. no_rag returns None upstream) must not attach.
    body = await _run(include_eval_metadata=True, rag_context=None)
    assert "eval_metadata" not in body
