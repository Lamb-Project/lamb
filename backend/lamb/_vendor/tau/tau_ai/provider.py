# Vendored from huggingface/tau v0.1.5 (b344d3eb), MIT License.
# Copyright (c) 2026 Alejandro AO. Modified for LAMB — see lamb/_vendor/tau/VENDORED.md.
"""Provider protocol for Tau model adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from lamb._vendor.tau.tau_agent.messages import AgentMessage
from lamb._vendor.tau.tau_agent.tools import AgentTool
from lamb._vendor.tau.tau_ai.events import ProviderEvent


class CancellationToken(Protocol):
    """Minimal cancellation interface accepted by providers."""

    def is_cancelled(self) -> bool:
        """Return whether the current stream should stop."""
        ...


class ModelProvider(Protocol):
    """Provider-neutral interface for streaming model responses."""

    def stream_response(
        self,
        *,
        model: str,
        system: str,
        messages: list[AgentMessage],
        tools: list[AgentTool],
        signal: CancellationToken | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        """Stream one model response as Tau provider events."""
        ...
