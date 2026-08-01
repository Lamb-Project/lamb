# Vendored from huggingface/tau v0.1.5 (b344d3eb), MIT License.
# Copyright (c) 2026 Alejandro AO. Modified for LAMB — see lamb/_vendor/tau/VENDORED.md.
"""Deterministic model provider for tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

from lamb._vendor.tau.tau_agent.messages import AgentMessage
from lamb._vendor.tau.tau_agent.tools import AgentTool
from lamb._vendor.tau.tau_ai.events import ProviderEvent
from lamb._vendor.tau.tau_ai.provider import CancellationToken


class FakeProvider:
    """A provider that replays predefined event streams.

    Each call to `stream_response` consumes the next scripted stream. This gives
    agent-loop tests deterministic model behavior without network access.
    """

    def __init__(self, streams: Iterable[Iterable[ProviderEvent]]) -> None:
        self._streams = [list(stream) for stream in streams]
        self.calls: list[tuple[str, str, list[AgentMessage], list[AgentTool]]] = []

    def stream_response(
        self,
        *,
        model: str,
        system: str,
        messages: list[AgentMessage],
        tools: list[AgentTool],
        signal: CancellationToken | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        """Replay the next scripted stream."""
        self.calls.append((model, system, list(messages), list(tools)))
        stream = self._streams.pop(0) if self._streams else []

        async def iterator() -> AsyncIterator[ProviderEvent]:
            for event in stream:
                if signal is not None and signal.is_cancelled():
                    return
                yield event

        return iterator()
