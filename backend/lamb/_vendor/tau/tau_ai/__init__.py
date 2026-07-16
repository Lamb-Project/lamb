# Vendored from huggingface/tau v0.1.5 (b344d3eb), MIT License.
# Copyright (c) 2026 Alejandro AO. Modified for LAMB — see lamb/_vendor/tau/VENDORED.md.
"""Provider and model streaming layer for Tau."""

from __future__ import annotations

from lamb._vendor.tau.tau_ai.anthropic import AnthropicProvider
from lamb._vendor.tau.tau_ai.env import (
    DEFAULT_ANTHROPIC_BASE_URL,
    DEFAULT_OPENAI_COMPATIBLE_MAX_RETRIES,
    DEFAULT_OPENAI_COMPATIBLE_MAX_RETRY_DELAY_SECONDS,
    DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS,
    AnthropicConfig,
    OpenAICompatibleConfig,
    openai_compatible_config_from_env,
)
from lamb._vendor.tau.tau_ai.events import (
    ProviderErrorEvent,
    ProviderEvent,
    ProviderResponseEndEvent,
    TokenUsage,  # LAMB addition
    ProviderResponseStartEvent,
    ProviderRetryEvent,
    ProviderTextDeltaEvent,
    ProviderThinkingDeltaEvent,
    ProviderToolCallEvent,
)
from lamb._vendor.tau.tau_ai.fake import FakeProvider
from lamb._vendor.tau.tau_ai.google import GoogleGenerativeAIProvider
from lamb._vendor.tau.tau_ai.mistral import MistralConversationsProvider
from lamb._vendor.tau.tau_ai.openai_codex import (
    DEFAULT_OPENAI_CODEX_BASE_URL,
    OpenAICodexConfig,
    OpenAICodexCredentials,
    OpenAICodexProvider,
)
from lamb._vendor.tau.tau_ai.openai_compatible import OpenAICompatibleProvider
from lamb._vendor.tau.tau_ai.provider import CancellationToken, ModelProvider

__all__ = [
    "CancellationToken",
    "AnthropicConfig",
    "AnthropicProvider",
    "DEFAULT_ANTHROPIC_BASE_URL",
    "DEFAULT_OPENAI_COMPATIBLE_MAX_RETRIES",
    "DEFAULT_OPENAI_COMPATIBLE_MAX_RETRY_DELAY_SECONDS",
    "DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS",
    "DEFAULT_OPENAI_CODEX_BASE_URL",
    "FakeProvider",
    "GoogleGenerativeAIProvider",
    "MistralConversationsProvider",
    "ModelProvider",
    "OpenAICodexConfig",
    "OpenAICodexCredentials",
    "OpenAICodexProvider",
    "OpenAICompatibleConfig",
    "OpenAICompatibleProvider",
    "ProviderErrorEvent",
    "ProviderEvent",
    "ProviderResponseEndEvent",
    "TokenUsage",  # LAMB addition
    "ProviderResponseStartEvent",
    "ProviderRetryEvent",
    "ProviderThinkingDeltaEvent",
    "ProviderTextDeltaEvent",
    "ProviderToolCallEvent",
    "openai_compatible_config_from_env",
]
