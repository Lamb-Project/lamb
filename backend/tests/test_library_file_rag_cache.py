"""Tests for library_file_rag cache integration and timing instrumentation."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_BACKEND_ROOT = Path(__file__).parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


@pytest.fixture(autouse=True)
def reset_cache():
    from lamb.completions import document_cache
    document_cache.clear()
    yield
    document_cache.clear()


def _make_assistant(org_id=1, library_id="lib-1", item_id="item-1"):
    assistant = MagicMock()
    assistant.organization_id = org_id
    assistant.metadata = f'{{"library_id": "{library_id}", "item_id": "{item_id}"}}'
    return assistant


class TestFetchWithCache:
    @pytest.fixture(autouse=True)
    def setup_lm_env(self, monkeypatch):
        monkeypatch.setenv("LAMB_LIBRARY_SERVER", "http://localhost:9091")
        monkeypatch.setenv("LAMB_LIBRARY_TOKEN", "test-token")

    def test_cache_miss_calls_library_manager(self):
        from lamb.completions.rag import library_file_rag
        assistant = _make_assistant()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Document content"

        with patch.object(library_file_rag.httpx, "get", return_value=mock_response) as mock_get:
            result = library_file_rag.rag_processor([], assistant=assistant)

        mock_get.assert_called_once()
        assert result["context"] == "# Document content"
        assert result["_timing"]["cache"] == "miss"
        assert result["_timing"]["fetch_ms"] >= 0

    def test_cache_hit_skips_library_manager(self):
        from lamb.completions.rag import library_file_rag
        from lamb.completions import document_cache

        document_cache.set("1:lib-1:item-1", {
            "context": "# Cached content",
            "sources": [{"title": "Library Document"}],
        })

        assistant = _make_assistant()

        with patch.object(library_file_rag.httpx, "get") as mock_get:
            result = library_file_rag.rag_processor([], assistant=assistant)

        mock_get.assert_not_called()
        assert result["context"] == "# Cached content"
        assert result["_timing"]["cache"] == "hit"

    def test_cache_hit_does_not_mutate_cached_entry(self):
        """The _timing key added on hit must not persist in the cache."""
        from lamb.completions.rag import library_file_rag
        from lamb.completions import document_cache

        document_cache.set("1:lib-1:item-1", {
            "context": "# Cached",
            "sources": [],
        })

        assistant = _make_assistant()
        with patch.object(library_file_rag.httpx, "get"):
            library_file_rag.rag_processor([], assistant=assistant)

        raw = document_cache.get("1:lib-1:item-1")
        assert "_timing" not in raw

    def test_cache_key_includes_org_id(self):
        from lamb.completions.rag import library_file_rag
        from lamb.completions import document_cache

        assistant = _make_assistant(org_id=42, library_id="lib-x", item_id="item-y")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Content"

        with patch.object(library_file_rag.httpx, "get", return_value=mock_response):
            library_file_rag.rag_processor([], assistant=assistant)

        assert document_cache.get("42:lib-x:item-y") is not None
        assert document_cache.get("1:lib-x:item-y") is None

    def test_timing_always_present(self):
        from lamb.completions.rag import library_file_rag
        assistant = _make_assistant()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Content"

        with patch.object(library_file_rag.httpx, "get", return_value=mock_response):
            result = library_file_rag.rag_processor([], assistant=assistant)

        assert "_timing" in result
        assert "fetch_ms" in result["_timing"]
        assert "cache" in result["_timing"]

    def test_failed_fetch_does_not_cache(self):
        from lamb.completions.rag import library_file_rag
        from lamb.completions import document_cache

        assistant = _make_assistant()
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(library_file_rag.httpx, "get", return_value=mock_response):
            result = library_file_rag.rag_processor([], assistant=assistant)

        assert result["context"] == ""
        assert document_cache.get("1:lib-1:item-1") is None

    def test_no_assistant_returns_skip_timing(self):
        from lamb.completions.rag import library_file_rag
        result = library_file_rag.rag_processor([], assistant=None)
        assert result["_timing"]["cache"] == "skip"
