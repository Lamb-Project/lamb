from __future__ import annotations

from typing import Any, Optional


def compute_cost_usd(
    pricing: Optional[dict[str, Any]],
    buckets: dict[str, int],
) -> float:
    """Compute cost in USD given pricing rates and token buckets.

    For auto-cache models (OpenAI): cache_write is forced to 0.
    For explicit-cache models (Alibaba, Anthropic): all three buckets are billed.

    If cache_read_per_1m or cache_write_per_1m is None, falls back to input_per_1m.
    If pricing is None, returns 0.0.
    """
    if pricing is None:
        return 0.0

    input_rate = pricing.get("input_per_1m") or 0.0
    cache_read_rate = pricing.get("cache_read_per_1m")
    if cache_read_rate is None:
        cache_read_rate = input_rate
    cache_write_rate = pricing.get("cache_write_per_1m")
    if cache_write_rate is None:
        cache_write_rate = input_rate
    output_rate = pricing.get("output_per_1m") or 0.0
    requires_explicit = bool(pricing.get("requires_explicit_cache", False))

    non_cached = buckets.get("non_cached", 0)
    cache_read = buckets.get("cache_read", 0)
    cache_write = buckets.get("cache_write", 0) if requires_explicit else 0
    completion = buckets.get("completion_tokens", 0)

    cost = (
        non_cached * input_rate / 1e6
        + cache_read * cache_read_rate / 1e6
        + cache_write * cache_write_rate / 1e6
        + completion * output_rate / 1e6
    )
    return cost
