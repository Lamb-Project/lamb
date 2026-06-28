"""Unit tests for ``backend/plugins/_mime.py`` extension-to-MIME mapping."""

from __future__ import annotations

import pytest
from plugins._mime import guess_mime


class TestGuessMime:
    """``guess_mime`` maps known extensions and falls back otherwise."""

    @pytest.mark.parametrize(
        ("ext", "expected"),
        [
            (".pdf", "application/pdf"),
            (
                ".docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            (
                ".pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            (
                ".xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            (".xls", "application/vnd.ms-excel"),
            (".html", "text/html"),
            (".csv", "text/csv"),
            (".json", "application/json"),
            (".xml", "application/xml"),
            (".zip", "application/zip"),
            (".epub", "application/epub+zip"),
            (".txt", "text/plain"),
            (".md", "text/markdown"),
            (".mp3", "audio/mpeg"),
            (".wav", "audio/wav"),
        ],
    )
    def test_known_extensions(self, ext, expected):
        """Each known extension maps to its documented MIME type."""
        assert guess_mime(ext) == expected

    def test_case_insensitive(self):
        """Extension matching is case-insensitive (lower-cased internally)."""
        assert guess_mime(".PDF") == "application/pdf"
        assert guess_mime(".Md") == "text/markdown"

    @pytest.mark.parametrize("ext", [".unknown", "", ".xyz", "pdf", ".tar.gz"])
    def test_unknown_falls_back(self, ext):
        """Unknown or malformed extensions fall back to octet-stream."""
        assert guess_mime(ext) == "application/octet-stream"
