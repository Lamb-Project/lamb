"""
Tests for the ToolLoop class.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from lamb.completions.tools.loop import ToolLoop


# ---------------------------------------------------------------------------
# Fake OpenAI response helpers
# ---------------------------------------------------------------------------

def _make_tool_call(tc_id, name, arguments):
    """Build a fake tool call object matching OpenAI's ChatCompletionMessageToolCall."""
    return SimpleNamespace(
        id=tc_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _make_response(tool_calls=None, content=""):
    """Build a fake ChatCompletion response."""
    msg = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
    )
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


async def _collect_events(loop, messages, tools, llm_fn):
    """Run the ToolLoop and collect all events."""
    events = []
    async for event in loop.run(messages, tools, "auto", llm_fn):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestToolLoopBasic:
    """Fundamental loop behaviors."""

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_result_immediately(self):
        """LLM returns no tool calls → single result event."""
        loop = ToolLoop()
        llm_fn = AsyncMock(return_value=_make_response(tool_calls=None, content="Hello!"))

        events = await _collect_events(loop, [{"role": "user", "content": "Hi"}], [], llm_fn)

        types = [e["type"] for e in events]
        assert types == ["thinking", "result"]
        assert events[-1]["type"] == "result"

    @pytest.mark.asyncio
    async def test_one_round_tool_call(self):
        """One tool call → thinking -> tool -> tool_done -> result."""
        loop = ToolLoop()
        calc_call = _make_tool_call("call_1", "calculator", json.dumps({"expression": "2 + 2"}))
        # First call returns tool_calls; second call returns text → loop stops
        llm_fn = AsyncMock(side_effect=[
            _make_response(tool_calls=[calc_call], content=""),
            _make_response(tool_calls=None, content="4"),
        ])

        events = await _collect_events(loop, [{"role": "user", "content": "What is 2+2?"}], [], llm_fn)

        types = [e["type"] for e in events]
        assert types == ["thinking", "tool", "tool_done", "thinking", "result"]

        # Verify tool event payload
        tool_event = events[1]
        assert tool_event["name"] == "calculator"
        assert "2 + 2" in tool_event["args"]

        # Verify tool_done event
        done_event = events[2]
        assert done_event["name"] == "calculator"
        assert done_event["success"] is True

        # Verify result messages contain the tool result
        result_messages = events[-1]["messages"]
        roles = [m["role"] for m in result_messages]
        assert "assistant" in roles
        assert "tool" in roles
        # The tool message content should contain the calc result
        tool_msg = [m for m in result_messages if m["role"] == "tool"][0]
        assert json.loads(tool_msg["content"])["result"] == 4

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_one_round(self):
        """Multiple tool calls in one response are all executed."""
        loop = ToolLoop()
        call_1 = _make_tool_call("call_1", "calculator", json.dumps({"expression": "1 + 1"}))
        call_2 = _make_tool_call("call_2", "calculator", json.dumps({"expression": "2 + 2"}))
        llm_fn = AsyncMock(side_effect=[
            _make_response(tool_calls=[call_1, call_2], content=""),
            _make_response(tool_calls=None, content="done"),
        ])

        events = await _collect_events(loop, [{"role": "user", "content": "Compute"}], [], llm_fn)

        types = [e["type"] for e in events]
        assert types == ["thinking", "tool", "tool_done", "tool", "tool_done", "thinking", "result"]

        tool_names = [e["name"] for e in events if e["type"] == "tool"]
        assert tool_names == ["calculator", "calculator"]

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Unknown tool name → tool_done with success=False."""
        loop = ToolLoop()
        call = _make_tool_call("call_1", "nonexistent_tool", "{}")
        llm_fn = AsyncMock(side_effect=[
            _make_response(tool_calls=[call], content=""),
            _make_response(tool_calls=None, content="ok"),
        ])

        events = await _collect_events(loop, [{"role": "user", "content": "Run tool"}], [], llm_fn)

        done_event = [e for e in events if e["type"] == "tool_done"][0]
        assert done_event["success"] is False

    @pytest.mark.asyncio
    async def test_invalid_json_args(self):
        """Invalid JSON args → tool_done with success=False."""
        loop = ToolLoop()
        call = _make_tool_call("call_1", "calculator", "{not valid json")
        llm_fn = AsyncMock(side_effect=[
            _make_response(tool_calls=[call], content=""),
            _make_response(tool_calls=None, content="ok"),
        ])

        events = await _collect_events(loop, [{"role": "user", "content": "X"}], [], llm_fn)

        done_event = [e for e in events if e["type"] == "tool_done"][0]
        assert done_event["success"] is False

    @pytest.mark.asyncio
    async def test_max_rounds_enforced(self):
        """After max_rounds, system message injected and loop exits."""
        loop = ToolLoop(max_rounds=1)
        call = _make_tool_call("call_1", "calculator", json.dumps({"expression": "1 + 1"}))
        # Always return a tool call → loop should stop after 1 round
        llm_fn = AsyncMock(return_value=_make_response(tool_calls=[call], content=""))

        events = await _collect_events(loop, [{"role": "user", "content": "Loop"}], [], llm_fn)

        types = [e["type"] for e in events]
        assert types[-1] == "result"
        # With max_rounds=1, we see: thinking, tool, tool_done, result
        # (round 1 executes, then hits max_rounds check)
        assert types.count("tool") == 1

        result_messages = events[-1]["messages"]
        last_msg = result_messages[-1]
        assert last_msg["role"] == "user"
        assert "max tool rounds" in last_msg["content"]

    @pytest.mark.asyncio
    async def test_llm_call_error_handled(self):
        """LLM call raising an exception → loop still terminates with result."""
        loop = ToolLoop()
        llm_fn = AsyncMock(side_effect=RuntimeError("boom"))

        events = await _collect_events(loop, [{"role": "user", "content": "Hi"}], [], llm_fn)

        assert events[-1]["type"] == "result"
        assert "LLM call failed" in events[-1]["messages"][-1]["content"]


class TestToolLoopLoops:
    """Multi-round loop behavior."""

    @pytest.mark.asyncio
    async def test_two_rounds_then_text(self):
        """Round 1 calls tool, round 2 returns text → terminates with result."""
        loop = ToolLoop(max_rounds=5)
        calc_call = _make_tool_call("call_1", "calculator", json.dumps({"expression": "10 * 10"}))

        # First call → tool call; second call → text reply
        async def fake_llm(messages, tools, tool_choice):
            # Count how many times called via tool messages present
            has_tool_msg = any(m.get("role") == "tool" for m in messages)
            if has_tool_msg:
                return _make_response(tool_calls=None, content="The answer is 100.")
            return _make_response(tool_calls=[calc_call], content="")

        events = await _collect_events(loop, [{"role": "user", "content": "Q"}], [], fake_llm)

        types = [e["type"] for e in events]
        assert types == ["thinking", "tool", "tool_done", "thinking", "result"]
        # Result was reached because LLM returned text, not max_rounds
        # (last message is a tool result — that's expected since we appended it)
        assert events[-1]["type"] == "result"