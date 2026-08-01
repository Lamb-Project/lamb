"""Unit tests for TauAgentLoop (lamb/aac/agent/tau_loop.py).

Network-free: a scripted provider replaces the LLM, a fake liteshell replaces
LAMB. The three headline assertions certify the legacy bugs dead:

- single LLM call on the no-tool path (legacy frontend paid for two),
- chat and chat_stream produce identical transcripts from one engine
  (the terminal-vs-frontend divergence),
- max_tool_rounds actually terminates a tool-calling runaway (legacy only
  appended a warning message and kept looping).

Plus the ask-flow state machine (queue / approve / reject / ambiguous) with
the real authorizer and classifier, envelope format stability, the legacy
status-dict grammar, and usage accounting.
"""

import json

import pytest

from lamb._vendor.tau.tau_agent.messages import AssistantMessage
from lamb._vendor.tau.tau_agent.tools import ToolCall
from lamb._vendor.tau.tau_ai.events import (
    ProviderResponseEndEvent,
    ProviderTextDeltaEvent,
    TokenUsage,
)
from lamb.aac.agent.tau_loop import TauAgentLoop

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class ScriptedProvider:
    """Replays one scripted ProviderEvent list per LLM call."""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = 0
        self.seen = []  # (system, messages_len) per call
        self.closed = False

    async def stream_response(self, *, model, system, messages, tools, signal=None):
        self.seen.append((system, len(messages)))
        script = self.scripts[min(self.calls, len(self.scripts) - 1)]
        self.calls += 1
        for event in script:
            yield event

    async def aclose(self):
        self.closed = True


class FakeResult:
    def __init__(self, success=True, data=None, error=None):
        self.success = success
        self.data = data if data is not None else {"items": []}
        self.error = error
        self.elapsed_ms = 1.0

    def to_dict(self):
        return {"success": self.success, "data": self.data, "error": self.error}


class FakeShell:
    def __init__(self):
        self.commands = []
        self.history = []

    async def execute(self, command):
        self.commands.append(command)
        result = FakeResult()
        self.history.append(result)
        return result


def _text_end(text, usage=None):
    return [
        ProviderTextDeltaEvent(delta=text),
        ProviderResponseEndEvent(
            message=AssistantMessage(content=text, tool_calls=[]),
            finish_reason="stop", usage=usage),
    ]


def _tool_end(command, call_id="call_1"):
    return [
        ProviderResponseEndEvent(
            message=AssistantMessage(content="", tool_calls=[
                ToolCall(id=call_id, name="execute_command",
                         arguments={"command": command})]),
            finish_reason="tool_calls"),
    ]


def _make_loop(scripts):
    provider = ScriptedProvider(scripts)
    loop = TauAgentLoop(shell=FakeShell(), llm_client=None, model="test-model")
    loop._provider_factory = lambda: provider
    return loop, provider


# ---------------------------------------------------------------------------
# The headline assertions
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_tool_path_is_a_single_llm_call():
    loop, provider = _make_loop([_text_end("Hello there")])
    text = await loop.chat("hi")
    assert text == "Hello there"
    assert provider.calls == 1  # legacy frontend made TWO calls here
    assert provider.closed


@pytest.mark.anyio
async def test_chat_and_stream_share_one_engine():
    """Same scenario through both surfaces -> identical transcripts."""
    loop_a, _ = _make_loop([_text_end("Same answer")])
    loop_b, _ = _make_loop([_text_end("Same answer")])
    text = await loop_a.chat("hi")
    frames = [f async for f in loop_b.chat_stream("hi")]
    streamed_text = "".join(f for f in frames if isinstance(f, str))
    assert text == streamed_text == "Same answer"
    assert loop_a.conversation == loop_b.conversation  # divergence dead


@pytest.mark.anyio
async def test_max_tool_rounds_actually_terminates():
    """A model that always calls tools hits the cap instead of looping forever."""
    loop, provider = _make_loop([_tool_end("lamb assistant list")])
    loop.max_tool_rounds = 3
    await loop.chat("go wild")
    assert provider.calls == 4  # 3 rounds + the capped attempt, then stop


# ---------------------------------------------------------------------------
# Wire grammar + envelope stability
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_stream_grammar_matches_legacy_vocabulary():
    loop, _ = _make_loop([
        _tool_end("lamb assistant list"),
        _text_end("You have 0 assistants."),
    ])
    frames = [f async for f in loop.chat_stream("list my assistants")]
    kinds = [f.get("status") if isinstance(f, dict) else "content" for f in frames]
    assert kinds == ["thinking", "tool", "tool_done", "thinking",
                     "responding", "content"]
    tool_frame = frames[1]
    assert tool_frame["command"] == "Loading assistants"
    assert frames[2]["success"] is True


@pytest.mark.anyio
async def test_envelope_keeps_legacy_openai_dict_format():
    loop, _ = _make_loop([
        _tool_end("lamb assistant list"),
        _text_end("Done."),
    ])
    await loop.chat("list")
    conv = loop.conversation
    assert conv[0] == {"role": "user", "content": "list"}
    assert conv[1]["role"] == "assistant"
    tc = conv[1]["tool_calls"][0]
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "execute_command"
    assert json.loads(tc["function"]["arguments"]) == {
        "command": "lamb assistant list"}
    assert conv[2]["role"] == "tool"
    assert json.loads(conv[2]["content"])["success"] is True
    assert conv[3] == {"role": "assistant", "content": "Done."}
    # round-trip: a second turn re-reads this envelope without loss
    loop2, provider2 = _make_loop([_text_end("ok")])
    loop2.conversation = list(conv)
    await loop2.chat("thanks")
    assert provider2.seen[0][1] == 5  # 4 restored + new user message


@pytest.mark.anyio
async def test_tool_audit_recorded():
    loop, _ = _make_loop([
        _tool_end("lamb assistant list"),
        _text_end("Done."),
    ])
    await loop.chat("list")
    assert len(loop.tool_audit) == 1
    assert loop.tool_audit[0]["action_key"] == "assistant.list"
    assert loop.tool_audit[0]["success"] is True


# ---------------------------------------------------------------------------
# Ask-flow state machine (real authorizer + real classifier)
# ---------------------------------------------------------------------------

_CREATE = 'lamb assistant create "Foo" --system-prompt "Bar"'


@pytest.mark.anyio
async def test_ask_flow_queues_write_action():
    loop, _ = _make_loop([
        _tool_end(_CREATE),
        _text_end("¿Confirmar? (s)í / (n)o"),
    ])
    await loop.chat("crea un asistente Foo")
    assert loop.pending_action is not None
    assert loop.pending_action["action_key"] == "assistant.create"
    assert loop.shell.commands == []  # nothing executed yet
    tool_msg = json.loads(loop.conversation[2]["content"])
    assert tool_msg["awaiting_user_confirmation"] is True
    assert loop.tool_audit[0]["intent"].endswith("[awaiting confirmation]")


@pytest.mark.anyio
async def test_ask_flow_approve_executes():
    loop, _ = _make_loop([
        _tool_end(_CREATE),
        _text_end("¿Confirmar?"),
        _text_end("Creado."),
    ])
    await loop.chat("crea un asistente Foo")
    await loop.chat("sí")
    assert loop.pending_action is None
    assert loop.shell.commands == [_CREATE]
    markers = [m for m in loop.conversation
               if m["role"] == "user" and "[System: User approved" in str(m.get("content"))]
    assert len(markers) == 1


@pytest.mark.anyio
async def test_ask_flow_reject_discards():
    loop, _ = _make_loop([
        _tool_end(_CREATE),
        _text_end("Confirmar?"),
        _text_end("Entès, no ho faig."),
    ])
    await loop.chat("crea un assistent Foo")
    await loop.chat("no")
    assert loop.pending_action is None
    assert loop.shell.commands == []
    markers = [m for m in loop.conversation
               if "[System: User declined" in str(m.get("content"))]
    assert len(markers) == 1


@pytest.mark.anyio
async def test_ask_flow_ambiguous_keeps_pending():
    loop, _ = _make_loop([
        _tool_end(_CREATE),
        _text_end("Confirm?"),
        _text_end("Yes, I can read docs."),
    ])
    await loop.chat("create assistant Foo")
    await loop.chat("by the way, can you read documentation?")
    assert loop.pending_action is not None  # survived the unrelated turn
    assert loop.shell.commands == []


@pytest.mark.anyio
async def test_second_write_while_pending_is_refused():
    loop, _ = _make_loop([
        _tool_end(_CREATE),
        _text_end("Confirm?"),
        [  # next turn: model tries ANOTHER write before resolution
            ProviderResponseEndEvent(
                message=AssistantMessage(content="", tool_calls=[
                    ToolCall(id="call_2", name="execute_command",
                             arguments={"command": 'lamb assistant create "Baz"'})]),
                finish_reason="tool_calls"),
        ],
        _text_end("There is already a pending action."),
    ])
    await loop.chat("create assistant Foo")
    await loop.chat("also create another one called Baz")
    assert loop.pending_action["command"] == _CREATE  # first one intact
    assert loop.shell.commands == []


# ---------------------------------------------------------------------------
# Usage accounting + stats
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_usage_accumulates_across_calls():
    loop, _ = _make_loop([
        _tool_end("lamb assistant list"),
        _text_end("Done.", usage=TokenUsage(prompt_tokens=100,
                                            completion_tokens=20,
                                            total_tokens=120)),
    ])
    await loop.chat("list")
    stats = loop.get_stats()
    assert stats["usage"]["llm_calls"] == 2
    assert stats["usage"]["total_tokens"] == 120  # first call reported none
    assert stats["model"] == "test-model"
    assert stats["tool_calls"] == 1


def test_factory_selects_by_env(monkeypatch):
    from lamb.aac.agent import create_agent_loop
    from lamb.aac.agent.loop import AgentLoop as Legacy
    monkeypatch.delenv("AAC_LOOP", raising=False)
    agent = create_agent_loop(shell=FakeShell(), llm_client=None, model="m")
    assert isinstance(agent, Legacy)
    monkeypatch.setenv("AAC_LOOP", "tau")
    agent = create_agent_loop(shell=FakeShell(), llm_client=None, model="m")
    assert isinstance(agent, TauAgentLoop)
