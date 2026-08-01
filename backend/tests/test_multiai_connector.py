"""Unit tests for the multiai connector (lamb/completions/connectors/multiai.py).

Network-free: the provider is replaced with a scripted fake; org-config
resolution is monkeypatched. Covers the LAMB connector contract (SSE string
generator + usage_out tuple for streaming, completion dict for non-streaming)
and the dynamic provider hint that lets one connector serve many families.
"""

import json

import pytest

from lamb._vendor.tau.tau_agent.messages import AssistantMessage, UserMessage
from lamb._vendor.tau.tau_ai.events import (
    ProviderErrorEvent,
    ProviderResponseEndEvent,
    ProviderTextDeltaEvent,
    TokenUsage,
)
from lamb.completions.connectors import multiai


class _ScriptedProvider:
    def __init__(self, events):
        self._events = events
        self.closed = False

    async def stream_response(self, *, model, system, messages, tools, signal=None):
        for event in self._events:
            yield event

    async def aclose(self):
        self.closed = True


def _events_ok():
    return [
        ProviderTextDeltaEvent(delta="Hello "),
        ProviderTextDeltaEvent(delta="world"),
        ProviderResponseEndEvent(
            message=AssistantMessage(content="Hello world", tool_calls=[]),
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=9, completion_tokens=2, total_tokens=11),
        ),
    ]


@pytest.fixture
def patched(monkeypatch):
    provider = _ScriptedProvider(_events_ok())
    monkeypatch.setattr(multiai, "_resolve_family_config",
                        lambda owner: {"family": "openai", "api_key": "k",
                                       "models": ["m1", "m2"], "default_model": "m1"})
    monkeypatch.setattr(multiai, "_build_provider", lambda cfg, body: provider)
    return provider


def test_to_tau_messages_splits_system_and_roles():
    system, transcript = multiai._to_tau_messages([
        {"role": "system", "content": "You are LAMB."},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "tool", "content": "ignored"},
        {"role": "system", "content": "Extra rules."},
    ])
    assert system == "You are LAMB.\n\nExtra rules."
    assert [type(m) for m in transcript] == [UserMessage, AssistantMessage]


@pytest.mark.anyio
async def test_stream_contract_and_usage_out(patched):
    result = await multiai.llm_connect(
        [{"role": "user", "content": "hi"}], stream=True,
        llm="m1", assistant_owner="owner@test")
    assert isinstance(result, tuple)
    generator, usage_out = result
    assert usage_out == {}  # not filled until the stream is drained

    frames = [f async for f in generator]
    assert all(f.startswith("data: ") for f in frames)
    assert frames[-1] == "data: [DONE]\n\n"
    payloads = [json.loads(f[6:]) for f in frames[:-1]]
    assert payloads[0]["choices"][0]["delta"] == {"role": "assistant"}
    text = "".join(p["choices"][0]["delta"].get("content", "") for p in payloads)
    assert text == "Hello world"
    assert payloads[-1]["choices"][0]["finish_reason"] == "stop"
    assert all(p["object"] == "chat.completion.chunk" for p in payloads)

    assert usage_out == {"prompt_tokens": 9, "completion_tokens": 2,
                         "total_tokens": 11, "provider": "openai"}
    assert patched.closed


@pytest.mark.anyio
async def test_non_stream_contract(patched):
    result = await multiai.llm_connect(
        [{"role": "user", "content": "hi"}], stream=False,
        llm="m1", assistant_owner="owner@test")
    assert result["object"] == "chat.completion"
    assert result["choices"][0]["message"]["content"] == "Hello world"
    assert result["usage"]["total_tokens"] == 11
    # the provider hint rides inside usage; lamb.completions.main pops it
    assert result["usage"]["provider"] == "openai"
    assert patched.closed


@pytest.mark.anyio
async def test_provider_error_raises(patched, monkeypatch):
    provider = _ScriptedProvider([ProviderErrorEvent(message="boom")])
    monkeypatch.setattr(multiai, "_build_provider", lambda cfg, body: provider)
    generator, _ = await multiai.llm_connect(
        [{"role": "user", "content": "hi"}], stream=True,
        llm="m1", assistant_owner="owner@test")
    with pytest.raises(RuntimeError, match="boom"):
        async for _ in generator:
            pass
    assert provider.closed  # aclose runs even on error


@pytest.mark.anyio
async def test_missing_usage_yields_zero_counts(patched, monkeypatch):
    events = [
        ProviderTextDeltaEvent(delta="x"),
        ProviderResponseEndEvent(
            message=AssistantMessage(content="x", tool_calls=[]),
            finish_reason="stop", usage=None),
    ]
    monkeypatch.setattr(multiai, "_build_provider",
                        lambda cfg, body: _ScriptedProvider(events))
    generator, usage_out = await multiai.llm_connect(
        [{"role": "user", "content": "hi"}], stream=True,
        llm="m1", assistant_owner="owner@test")
    async for _ in generator:
        pass
    assert usage_out["total_tokens"] == 0
    assert usage_out["provider"] == "openai"


def test_unvalidated_family_raises():
    with pytest.raises(ValueError, match="not yet validated"):
        multiai._build_provider({"family": "anthropic", "api_key": "k"}, None)


def test_get_available_llms(patched):
    assert multiai.get_available_llms("owner@test") == ["m1", "m2"]


def test_get_available_llms_survives_resolver_failure(monkeypatch):
    def _boom(owner):
        raise ValueError("no org")
    monkeypatch.setattr(multiai, "_resolve_family_config", _boom)
    assert multiai.get_available_llms("owner@test") == []
