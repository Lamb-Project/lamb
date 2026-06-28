"""
Unit tests for lightweight completion task routing.

Open WebUI flags auxiliary requests (title/tags/query generation, etc.) via
``request["metadata"]["task"]``; the router detects that field and routes such
non-streaming requests through the small-fast model, skipping RAG/PPS.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from backend.lamb.completions.task_routing import (
    is_task_request,
    maybe_route_non_streaming_task,
)


def test_is_task_request_detects_owi_task_metadata():
    request = {
        "metadata": {"task": "title_generation"},
        "messages": [{"role": "user", "content": "hi"}],
    }

    assert is_task_request(request) is True


def test_is_task_request_detects_tags_generation_task():
    request = {"metadata": {"task": "tags_generation"}}

    assert is_task_request(request) is True


def test_is_task_request_ignores_normal_chat_request():
    request = {"messages": [{"role": "user", "content": "Help me solve this algebra problem."}]}

    assert is_task_request(request) is False


def test_maybe_route_non_streaming_task_uses_small_fast_model_for_task_requests():
    request = {
        "stream": False,
        "metadata": {"task": "title_generation"},
        "messages": [
            {"role": "user", "content": "Generate a title for this conversation."}
        ],
    }
    expected_response = {"id": "chatcmpl-1", "choices": []}

    with patch(
        "backend.lamb.completions.task_routing.invoke_small_fast_model",
        new=AsyncMock(return_value=expected_response),
    ) as mock_invoke:
        result = asyncio.run(
            maybe_route_non_streaming_task(request, "owner@example.com")
        )

    assert result == expected_response
    mock_invoke.assert_awaited_once_with(
        messages=request["messages"],
        assistant_owner="owner@example.com",
        stream=False,
        body=request,
    )


def test_maybe_route_non_streaming_task_skips_streaming_requests():
    request = {
        "stream": True,
        "metadata": {"task": "title_generation"},
        "messages": [{"role": "user", "content": "Generate a title."}],
    }

    with patch(
        "backend.lamb.completions.task_routing.invoke_small_fast_model",
        new=AsyncMock(),
    ) as mock_invoke:
        result = asyncio.run(
            maybe_route_non_streaming_task(request, "owner@example.com")
        )

    assert result is None
    mock_invoke.assert_not_awaited()


def test_maybe_route_non_streaming_task_skips_non_task_requests():
    request = {
        "stream": False,
        "messages": [{"role": "user", "content": "A normal chat message."}],
    }

    with patch(
        "backend.lamb.completions.task_routing.invoke_small_fast_model",
        new=AsyncMock(),
    ) as mock_invoke:
        result = asyncio.run(
            maybe_route_non_streaming_task(request, "owner@example.com")
        )

    assert result is None
    mock_invoke.assert_not_awaited()
