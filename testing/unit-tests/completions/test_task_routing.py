"""
Unit tests for lightweight completion task routing.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from backend.lamb.completions.task_routing import (
    is_title_generation_request,
    maybe_route_non_streaming_task,
)


def test_is_title_generation_request_detects_openwebui_task_marker():
    messages = [
        {
            "role": "user",
            "content": "### Task:\nGenerate 1-3 broad tags and a short conversation title.",
        }
    ]

    assert is_title_generation_request(messages) is True


def test_is_title_generation_request_detects_pattern_in_multimodal_message():
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Please suggest a conversation title and broad tags for this chat history.",
                }
            ],
        }
    ]

    assert is_title_generation_request(messages) is True


def test_is_title_generation_request_ignores_normal_chat_message():
    messages = [{"role": "user", "content": "Help me solve this algebra problem."}]

    assert is_title_generation_request(messages) is False


def test_maybe_route_non_streaming_task_uses_small_fast_model_for_title_requests():
    request = {
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": "### Task:\nGenerate a title for this conversation.",
            }
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
        "messages": [{"role": "user", "content": "### Task:\nGenerate a title."}],
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
