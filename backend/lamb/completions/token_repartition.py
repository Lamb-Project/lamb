from __future__ import annotations

from typing import Any


def extract_token_buckets(usage_data: dict[str, Any]) -> dict[str, int]:
    """Extract three prompt token buckets from provider usage data.

    Returns dict with: prompt_tokens, completion_tokens, cache_read, cache_write, non_cached.

    Handles both OpenAI auto-cache (cache_write=0) and explicit-cache providers
    (Alibaba, Anthropic) that report cache_creation_input_tokens.

    Deduplication: if both flat cache_creation_input_tokens and nested
    cache_creation.ephemeral_5m_input_tokens are present with the same value,
    count once (prefer flat).
    """
    prompt_tokens = usage_data.get("prompt_tokens", 0) or 0
    completion_tokens = usage_data.get("completion_tokens", 0) or 0

    details = usage_data.get("prompt_tokens_details") or {}
    if not isinstance(details, dict):
        details = {}

    cache_read = details.get("cached_tokens", 0) or 0

    flat_write = details.get("cache_creation_input_tokens", 0) or 0
    nested_obj = details.get("cache_creation") or {}
    nested_write = 0
    if isinstance(nested_obj, dict):
        nested_write = nested_obj.get("ephemeral_5m_input_tokens", 0) or 0

    # Prefer flat field; fall back to nested
    cache_write = flat_write if flat_write > 0 else nested_write

    # Clamp: cache_read + cache_write cannot exceed prompt_tokens
    cache_read = min(cache_read, prompt_tokens)
    remaining = prompt_tokens - cache_read
    cache_write = min(cache_write, max(0, remaining))
    non_cached = max(0, prompt_tokens - cache_read - cache_write)

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cache_read": cache_read,
        "cache_write": cache_write,
        "non_cached": non_cached,
    }
