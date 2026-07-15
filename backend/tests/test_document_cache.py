"""Tests for document_cache TTL cache module."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

_BACKEND_ROOT = Path(__file__).parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear cache state between tests."""
    from lamb.completions import document_cache
    document_cache.clear()
    yield
    document_cache.clear()


class TestCacheGetSet:
    def test_get_returns_none_for_missing_key(self):
        from lamb.completions import document_cache
        assert document_cache.get("nonexistent") is None

    def test_set_and_get_returns_stored_value(self):
        from lamb.completions import document_cache
        value = {"context": "hello", "sources": []}
        document_cache.set("org1:lib1:item1", value)
        result = document_cache.get("org1:lib1:item1")
        assert result == value

    def test_get_returns_copy_not_original(self):
        """Mutating the returned value must NOT affect the cached entry."""
        from lamb.completions import document_cache
        document_cache.set("key", {"context": "original", "sources": []})
        result = document_cache.get("key")
        result["context"] = "mutated"
        result["_timing"] = {"fetch_ms": 999}
        fresh = document_cache.get("key")
        assert fresh["context"] == "original"
        assert "_timing" not in fresh

    def test_different_keys_are_independent(self):
        from lamb.completions import document_cache
        document_cache.set("key1", {"context": "a"})
        document_cache.set("key2", {"context": "b"})
        assert document_cache.get("key1")["context"] == "a"
        assert document_cache.get("key2")["context"] == "b"


class TestCacheTTL:
    def test_expired_entry_returns_none(self):
        from lamb.completions import document_cache
        with patch.object(document_cache, "_CACHE_TTL", 1):
            document_cache.set("key", {"context": "data"})
            time.sleep(1.1)
            assert document_cache.get("key") is None

    def test_valid_entry_returns_value_before_expiry(self):
        from lamb.completions import document_cache
        with patch.object(document_cache, "_CACHE_TTL", 60):
            document_cache.set("key", {"context": "data"})
            assert document_cache.get("key") is not None


class TestCacheDisabled:
    def test_get_returns_none_when_disabled(self):
        from lamb.completions import document_cache
        with patch.object(document_cache, "_CACHE_ENABLED", False):
            document_cache.set("key", {"context": "data"})
            assert document_cache.get("key") is None

    def test_set_does_nothing_when_disabled(self):
        from lamb.completions import document_cache
        with patch.object(document_cache, "_CACHE_ENABLED", False):
            document_cache.set("key", {"context": "data"})
            assert len(document_cache._cache) == 0


class TestCacheClear:
    def test_clear_removes_all_entries(self):
        from lamb.completions import document_cache
        document_cache.set("k1", {"context": "a"})
        document_cache.set("k2", {"context": "b"})
        removed = document_cache.clear()
        assert removed == 2
        assert document_cache.get("k1") is None

    def test_clear_returns_zero_when_empty(self):
        from lamb.completions import document_cache
        assert document_cache.clear() == 0


class TestCacheStats:
    def test_stats_returns_correct_structure(self):
        from lamb.completions import document_cache
        document_cache.set("k1", {"context": "a"})
        s = document_cache.stats()
        assert "enabled" in s
        assert "ttl_seconds" in s
        assert s["total_entries"] == 1
        assert s["active_entries"] == 1
        assert s["expired_entries"] == 0
