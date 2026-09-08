"""In-memory TTL cache for document RAG responses.

Caches Library Manager responses (markdown content) keyed by
org_id:library_id:item_id. Entries expire after DOCUMENT_RAG_CACHE_TTL_SECONDS.

Reads configuration from config.py (single source of truth).
"""

import copy
import time
import threading
import logging

import config

logger = logging.getLogger("lamb.completions.document_cache")

_CACHE_ENABLED = config.DOCUMENT_RAG_CACHE_ENABLED
_CACHE_TTL = config.DOCUMENT_RAG_CACHE_TTL_SECONDS

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def is_enabled() -> bool:
    return _CACHE_ENABLED


def get(cache_key: str) -> dict | None:
    """Return a deep copy of cached value if present and not expired, else None.

    Returns a copy to prevent callers from mutating the cached entry.
    """
    if not _CACHE_ENABLED:
        return None
    with _lock:
        entry = _cache.get(cache_key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.time() - stored_at > _CACHE_TTL:
            del _cache[cache_key]
            logger.debug(f"Cache expired: {cache_key}")
            return None
        logger.debug(f"Cache hit: {cache_key} (age={time.time() - stored_at:.0f}s)")
        return copy.deepcopy(value)


def set(cache_key: str, value: dict) -> None:
    """Store a deep copy of value with current timestamp."""
    if not _CACHE_ENABLED:
        return
    with _lock:
        _cache[cache_key] = (time.time(), copy.deepcopy(value))
        logger.debug(f"Cache set: {cache_key} (ttl={_CACHE_TTL}s)")


def clear() -> int:
    """Clear all entries. Returns number of entries removed."""
    with _lock:
        count = len(_cache)
        _cache.clear()
        logger.info(f"Cache cleared: {count} entries removed")
        return count


def stats() -> dict:
    """Return cache statistics."""
    with _lock:
        now = time.time()
        total = len(_cache)
        expired = sum(1 for _, (ts, _) in _cache.items() if now - ts > _CACHE_TTL)
        return {
            "enabled": _CACHE_ENABLED,
            "ttl_seconds": _CACHE_TTL,
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
        }
