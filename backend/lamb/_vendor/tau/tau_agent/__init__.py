# Vendored from huggingface/tau v0.1.5 (b344d3eb), MIT License.
# Copyright (c) 2026 Alejandro AO. Modified for LAMB — see lamb/_vendor/tau/VENDORED.md.
"""Portable agent harness primitives for Tau."""

from __future__ import annotations

from lamb._vendor.tau.tau_agent.events import (
    AgentEndEvent,
    AgentEvent,
    AgentStartEvent,
    ErrorEvent,
    MessageDeltaEvent,
    MessageEndEvent,
    MessageStartEvent,
    QueueUpdateEvent,
    RetryEvent,
    ThinkingDeltaEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from lamb._vendor.tau.tau_agent.harness import (
    AgentHarness,
    AgentHarnessConfig,
    EventListener,
    QueuedMessages,
    SimpleCancellationToken,
)
from lamb._vendor.tau.tau_agent.loop import run_agent_loop
from lamb._vendor.tau.tau_agent.messages import AgentMessage, AssistantMessage, ToolResultMessage, UserMessage
# LAMB modification: upstream re-exports tau_agent.session (JSONL session-tree
# persistence) here. LAMB deliberately does NOT vendor session/ — AAC sessions
# live in LAMB's own database. See VENDORED.md.
from lamb._vendor.tau.tau_agent.tools import AgentTool, AgentToolResult, ToolCall, ToolExecutor
from lamb._vendor.tau.tau_agent.types import JSONObject, JSONPrimitive, JSONValue

__all__ = [
    "AgentEndEvent",
    "AgentEvent",
    "AgentMessage",
    "AgentStartEvent",
    "AgentHarness",
    "AgentHarnessConfig",
    "AgentTool",
    "AgentToolResult",
    "AssistantMessage",
    "ErrorEvent",
    "EventListener",
    "JSONObject",
    "JSONPrimitive",
    "JSONValue",
    "MessageDeltaEvent",
    "MessageEndEvent",
    "MessageStartEvent",
    "QueuedMessages",
    "QueueUpdateEvent",
    "RetryEvent",
    "SimpleCancellationToken",
    "ThinkingLevelChangeEntry",
    "ThinkingDeltaEvent",
    "ToolCall",
    "ToolExecutionEndEvent",
    "ToolExecutionStartEvent",
    "ToolExecutionUpdateEvent",
    "ToolExecutor",
    "ToolResultMessage",
    "TurnEndEvent",
    "TurnStartEvent",
    "UserMessage",
    "run_agent_loop",
]
