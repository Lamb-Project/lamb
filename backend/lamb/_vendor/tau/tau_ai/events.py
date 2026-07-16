# Vendored from huggingface/tau v0.1.5 (b344d3eb), MIT License.
# Copyright (c) 2026 Alejandro AO. Modified for LAMB — see lamb/_vendor/tau/VENDORED.md.
"""Provider-neutral streaming events emitted by model adapters."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from lamb._vendor.tau.tau_agent.messages import AssistantMessage
from lamb._vendor.tau.tau_agent.tools import ToolCall
from lamb._vendor.tau.tau_agent.types import JSONValue


class ProviderResponseStartEvent(BaseModel):
    """The provider has started a model response."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["response_start"] = "response_start"
    model: str


class ProviderRetryEvent(BaseModel):
    """The provider adapter is retrying a transient request failure."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["retry"] = "retry"
    attempt: int
    max_attempts: int
    delay_seconds: float
    message: str
    data: dict[str, JSONValue] | None = None


class ProviderTextDeltaEvent(BaseModel):
    """A streamed text fragment from the provider."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text_delta"] = "text_delta"
    delta: str


class ProviderThinkingDeltaEvent(BaseModel):
    """A streamed thinking/reasoning fragment from the provider."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["thinking_delta"] = "thinking_delta"
    delta: str


class ProviderToolCallEvent(BaseModel):
    """A complete tool call requested by the model."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_call"] = "tool_call"
    tool_call: ToolCall


class TokenUsage(BaseModel):
    """Token accounting for a completed model response.

    LAMB addition: upstream tau v0.1.5 requests usage from providers that
    support it but never parses the reply. LAMB's quota/cost system needs
    real token counts, so adapters populate this on the response-end event.
    """

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ProviderResponseEndEvent(BaseModel):
    """The provider has completed a model response."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["response_end"] = "response_end"
    message: AssistantMessage
    finish_reason: str | None = None
    usage: TokenUsage | None = None  # LAMB addition — see TokenUsage above


class ProviderErrorEvent(BaseModel):
    """A provider-level error that can be surfaced by the agent layer."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["error"] = "error"
    message: str
    data: dict[str, JSONValue] | None = None


type ProviderEvent = (
    ProviderResponseStartEvent
    | ProviderRetryEvent
    | ProviderTextDeltaEvent
    | ProviderThinkingDeltaEvent
    | ProviderToolCallEvent
    | ProviderResponseEndEvent
    | ProviderErrorEvent
)
