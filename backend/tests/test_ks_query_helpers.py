import pytest
from lamb.completions.rag._ks_query_helpers import _extract_sources


class TestExtractSources:
    def test_empty_results_returns_empty_list(self):
        assert _extract_sources("ks-1", []) == []

    def test_extracts_title_from_source_title(self):
        results = [{"text": "chunk", "score": 0.9, "metadata": {"source_title": "My Doc"}}]
        sources = _extract_sources("ks-1", results)
        assert len(sources) == 1
        assert sources[0]["title"] == "My Doc"
        assert sources[0]["knowledge_store_id"] == "ks-1"
        assert sources[0]["score"] == 0.9

    def test_falls_back_to_library_name_for_title(self):
        results = [{"text": "chunk", "score": 0.8, "metadata": {"library_name": "Lib A"}}]
        sources = _extract_sources("ks-1", results)
        assert sources[0]["title"] == "Lib A"

    def test_falls_back_to_source_for_title(self):
        results = [{"text": "chunk", "score": 0.8, "metadata": {}}]
        sources = _extract_sources("ks-1", results)
        assert sources[0]["title"] == "Source"

    def test_permalink_page_is_primary_url(self):
        results = [{"text": "c", "score": 0.5, "metadata": {
            "permalink_original": "/docs/1/lib/item/original.pdf",
            "permalink_markdown": "/docs/1/lib/item/full.md",
            "permalink_page": "/docs/1/lib/item/pages/1.md",
        }}]
        sources = _extract_sources("ks-1", results)
        assert sources[0]["url"] == "/docs/1/lib/item/pages/1.md"
        assert sources[0]["permalink_original"] == "/docs/1/lib/item/original.pdf"
        assert sources[0]["permalink_markdown"] == "/docs/1/lib/item/full.md"
        assert sources[0]["permalink_page"] == "/docs/1/lib/item/pages/1.md"

    def test_permalink_markdown_is_primary_when_no_page(self):
        results = [{"text": "c", "score": 0.5, "metadata": {
            "permalink_original": "/docs/1/lib/item/original.pdf",
            "permalink_markdown": "/docs/1/lib/item/full.md",
        }}]
        sources = _extract_sources("ks-1", results)
        assert sources[0]["url"] == "/docs/1/lib/item/full.md"

    def test_includes_library_metadata(self):
        results = [{"text": "c", "score": 0.5, "metadata": {
            "library_id": "lib-1",
            "library_name": "My Library",
            "source_item_id": "item-1",
        }}]
        sources = _extract_sources("ks-1", results)
        assert sources[0]["library_id"] == "lib-1"
        assert sources[0]["library_name"] == "My Library"
        assert sources[0]["source_item_id"] == "item-1"

    def test_handles_none_metadata(self):
        results = [{"text": "c", "score": 0.5, "metadata": None}]
        sources = _extract_sources("ks-1", results)
        assert len(sources) == 1
        assert sources[0]["title"] == "Source"
