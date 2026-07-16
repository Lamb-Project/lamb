"""Multi-AI compliance connector (issue #404) on the vendored tau provider layer.

Drives LAMB completions through lamb._vendor.tau's provider adapters instead
of a provider SDK, which buys three things the openai connector lacks:
retry with exponential backoff and server-suggested delays, cooperative
cancellation plumbing, and provider-neutral typed events — including the
LAMB usage patch, so token accounting works across provider families.

Configuration (resolved per assistant owner via OrganizationConfigResolver):
an org provider entry named ``multiai`` with an optional ``family`` field
(default ``openai``), else the org's standard ``openai`` entry. Any
OpenAI-compatible endpoint works through the ``openai`` family: OpenAI,
OpenRouter, DashScope, GLM, local Ollama (``http://host:11434/v1``).

Usage reporting: streaming returns ``(generator, usage_out)`` and fills
``usage_out`` with token counts plus a ``provider`` key at stream end;
non-streaming embeds the same ``provider`` hint inside the response's
``usage`` dict. lamb.completions.main pops the hint and logs against the
right ``model_pricing`` rows — that is what lets one connector serve many
provider families without the static connector→provider map.

Current scope: the ``openai`` family is implemented and validated. The
vendored anthropic/google/mistral adapters are wired behind the same
registry but raise until an org config with real credentials exists to
validate them (better loud than blind).

Known gap inherited from tau v0.1.5: per-request sampling parameters
(``temperature`` etc.) are not part of the provider protocol; ``max_tokens``
is honored via provider config. Exactly the parameter-passthrough concern
#404 records.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator, Dict, Optional

from lamb._vendor.tau.tau_agent.messages import (
    AgentMessage,
    AssistantMessage,
    UserMessage,
)
from lamb._vendor.tau.tau_ai.env import OpenAICompatibleConfig
from lamb._vendor.tau.tau_ai.events import (
    ProviderErrorEvent,
    ProviderResponseEndEvent,
    ProviderTextDeltaEvent,
)
from lamb._vendor.tau.tau_ai.openai_compatible import OpenAICompatibleProvider
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="COMPLETIONS")

_UNVALIDATED_FAMILIES = ("anthropic", "google", "mistral")


def _resolve_family_config(assistant_owner: str) -> Dict[str, Any]:
    """Resolve provider family + credentials for this owner's organization.

    Prefers an explicit ``multiai`` org provider entry; falls back to the
    org's standard ``openai`` entry (family ``openai``).
    """
    resolver = OrganizationConfigResolver(assistant_owner)
    cfg = resolver.get_provider_config("multiai")
    if cfg:
        return {"family": (cfg.get("family") or "openai").lower(), **cfg}
    cfg = resolver.get_provider_config("openai")
    if not cfg or not cfg.get("api_key"):
        raise ValueError(
            "multiai connector: no 'multiai' or usable 'openai' provider "
            "configured for this organization")
    return {"family": "openai", **cfg}


def _build_provider(cfg: Dict[str, Any], body: Optional[Dict[str, Any]]):
    family = cfg["family"]
    if family in _UNVALIDATED_FAMILIES:
        raise ValueError(
            f"multiai connector: provider family '{family}' is vendored but "
            "not yet validated against real credentials — see connector "
            "docstring")
    if family != "openai":
        raise ValueError(f"multiai connector: unknown provider family '{family}'")
    max_tokens = None
    if isinstance(body, dict):
        raw = body.get("max_tokens") or body.get("max_completion_tokens")
        if isinstance(raw, int) and raw > 0:
            max_tokens = raw
    provider_config = OpenAICompatibleConfig(
        api_key=cfg["api_key"],
        base_url=(cfg.get("base_url") or "https://api.openai.com/v1"),
        max_tokens=max_tokens,
        provider_name="LAMB multiai (openai-compatible)",
    )
    return OpenAICompatibleProvider(provider_config)


def _to_tau_messages(messages: list) -> tuple[str, list[AgentMessage]]:
    """Split LAMB's composed OpenAI-format messages into (system, transcript)."""
    system_parts: list[str] = []
    transcript: list[AgentMessage] = []
    for msg in messages or []:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "system":
            if content:
                system_parts.append(content)
        elif role == "user":
            transcript.append(UserMessage(content=content))
        elif role == "assistant":
            transcript.append(AssistantMessage(content=content, tool_calls=[]))
        else:
            logger.warning(f"multiai: dropping message with unsupported role '{role}'")
    return "\n\n".join(system_parts), transcript


def _chunk(completion_id: str, created: int, model: str,
           delta: Dict[str, Any], finish_reason: Optional[str] = None) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload)}\n\n"


def _usage_dict(end: ProviderResponseEndEvent, family: str) -> Dict[str, Any]:
    usage = end.usage
    return {
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        # Internal hint for lamb.completions.main — popped before logging,
        # never reaches the client payload.
        "provider": family,
    }


async def llm_connect(
    messages: list,
    stream: bool = False,
    body: Dict[str, Any] = None,
    llm: str = None,
    assistant_owner: Optional[str] = None,
    use_small_fast_model: bool = False,
):
    cfg = _resolve_family_config(assistant_owner)
    provider = _build_provider(cfg, body)
    model = llm or cfg.get("default_model") or (
        (cfg.get("models") or [None])[0])
    if not model:
        raise ValueError("multiai connector: no model requested and none configured")
    system, transcript = _to_tau_messages(messages)
    family = cfg["family"]

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    if stream:
        usage_out: Dict[str, Any] = {}

        async def _generate() -> AsyncIterator[str]:
            try:
                yield _chunk(completion_id, created, model, {"role": "assistant"})
                async for event in provider.stream_response(
                        model=model, system=system, messages=transcript,
                        tools=[], signal=None):
                    if isinstance(event, ProviderTextDeltaEvent):
                        yield _chunk(completion_id, created, model,
                                     {"content": event.delta})
                    elif isinstance(event, ProviderResponseEndEvent):
                        usage_out.update(_usage_dict(event, family))
                        yield _chunk(completion_id, created, model, {},
                                     finish_reason=event.finish_reason or "stop")
                    elif isinstance(event, ProviderErrorEvent):
                        raise RuntimeError(f"multiai provider error: {event.message}")
                    # thinking deltas, retries and tool calls carry no
                    # client-visible payload for a completions request
                yield "data: [DONE]\n\n"
            finally:
                await provider.aclose()

        return _generate(), usage_out

    # Non-streaming: drain the event stream, assemble one completion object.
    content_parts: list[str] = []
    end_event: Optional[ProviderResponseEndEvent] = None
    try:
        async for event in provider.stream_response(
                model=model, system=system, messages=transcript,
                tools=[], signal=None):
            if isinstance(event, ProviderTextDeltaEvent):
                content_parts.append(event.delta)
            elif isinstance(event, ProviderResponseEndEvent):
                end_event = event
            elif isinstance(event, ProviderErrorEvent):
                raise RuntimeError(f"multiai provider error: {event.message}")
    finally:
        await provider.aclose()

    if end_event is None:
        raise RuntimeError("multiai provider ended stream without a response_end event")

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant",
                        "content": end_event.message.content or "".join(content_parts)},
            "finish_reason": end_event.finish_reason or "stop",
        }],
        "usage": _usage_dict(end_event, family),
    }


def get_available_llms(assistant_owner: Optional[str] = None) -> list:
    """Models the resolved org config offers through this connector."""
    try:
        cfg = _resolve_family_config(assistant_owner)
    except Exception as exc:
        logger.warning(f"multiai: could not resolve provider config: {exc}")
        return []
    models = cfg.get("models") or []
    return list(models) if isinstance(models, list) else []
