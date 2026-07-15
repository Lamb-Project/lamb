"""Tests for document RAG timing header extraction logic.

These tests verify the extraction pattern used in main.py to convert
_timing dicts from document_context into response headers. The pattern
is tested in isolation because full integration with run_lamb_assistant
requires the entire plugin pipeline (connectors, RAG processors, etc.).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def extract_timing_headers(document_context, final_headers):
    """Replicate the extraction logic from main.py for isolated testing."""
    if document_context and isinstance(document_context, dict):
        _doc_timing = document_context.pop("_timing", None)
        if _doc_timing:
            final_headers["X-Doc-RAG-Time-Ms"] = str(_doc_timing.get("fetch_ms", 0))
            final_headers["X-Doc-RAG-Cache"] = _doc_timing.get("cache", "unknown")


class TestTimingExtraction:
    def test_timing_popped_from_document_context(self):
        document_context = {
            "context": "some doc",
            "sources": [],
            "_timing": {"fetch_ms": 42.5, "cache": "hit"},
        }
        headers = {}
        extract_timing_headers(document_context, headers)

        assert "_timing" not in document_context
        assert headers["X-Doc-RAG-Time-Ms"] == "42.5"
        assert headers["X-Doc-RAG-Cache"] == "hit"

    def test_no_headers_when_timing_absent(self):
        document_context = {"context": "some doc", "sources": []}
        headers = {}
        extract_timing_headers(document_context, headers)

        assert "X-Doc-RAG-Time-Ms" not in headers

    def test_no_headers_when_document_context_is_none(self):
        headers = {}
        extract_timing_headers(None, headers)
        assert len(headers) == 0

    def test_no_headers_when_document_context_is_string(self):
        headers = {}
        extract_timing_headers("not a dict", headers)
        assert len(headers) == 0

    def test_cache_miss_value(self):
        document_context = {
            "context": "doc",
            "sources": [],
            "_timing": {"fetch_ms": 123.45, "cache": "miss"},
        }
        headers = {}
        extract_timing_headers(document_context, headers)
        assert headers["X-Doc-RAG-Cache"] == "miss"

    def test_cache_skip_value(self):
        document_context = {
            "context": "doc",
            "sources": [],
            "_timing": {"fetch_ms": 0, "cache": "skip"},
        }
        headers = {}
        extract_timing_headers(document_context, headers)
        assert headers["X-Doc-RAG-Cache"] == "skip"
        assert headers["X-Doc-RAG-Time-Ms"] == "0"
