"""Unit tests for ``SimpleImportPlugin`` — direct calls, no HTTP, no worker.

Exercises the plain-text import path end to end against the real filesystem
(files created under ``tmp_storage``) plus the ``_mime_for_extension`` map and
the plugin's class-level capability/extension declarations.
"""

from __future__ import annotations

import pytest
from plugins.base import ImportResult
from plugins.content_handlers.capability import Capability
from plugins.simple_import import SimpleImportPlugin, _mime_for_extension


class TestImportContent:
    """``SimpleImportPlugin.import_content`` reading real files."""

    def setup_method(self):
        """Build a fresh plugin instance per test."""
        self.plugin = SimpleImportPlugin()

    def test_reads_markdown_file(self, tmp_storage):
        """A .md file is read verbatim into ``full_text``."""
        path = tmp_storage / "notes.md"
        body = "# Title\n\nSome **markdown** body.\n"
        path.write_text(body, encoding="utf-8")

        result = self.plugin.import_content(str(path))

        assert isinstance(result, ImportResult)
        assert result.full_text == body
        assert result.pages == []
        assert result.images == []

    def test_reads_txt_file(self, tmp_storage):
        """A .txt file is read as UTF-8 text."""
        path = tmp_storage / "plain.txt"
        path.write_text("line one\nline two", encoding="utf-8")

        result = self.plugin.import_content(str(path))

        assert result.full_text == "line one\nline two"

    def test_reads_html_file(self, tmp_storage):
        """A .html file is read as-is (no conversion)."""
        path = tmp_storage / "page.html"
        body = "<html><body><p>hi</p></body></html>"
        path.write_text(body, encoding="utf-8")

        result = self.plugin.import_content(str(path))

        assert result.full_text == body

    def test_metadata_shape(self, tmp_storage):
        """Metadata records filename, mime, size, and character count."""
        path = tmp_storage / "doc.md"
        body = "héllo"  # multibyte to make byte-size differ from char count
        path.write_text(body, encoding="utf-8")

        result = self.plugin.import_content(str(path))

        meta = result.metadata
        assert meta["original_filename"] == "doc.md"
        assert meta["content_type"] == "text/markdown"
        assert meta["file_size"] == path.stat().st_size
        assert meta["character_count"] == len(body)

    def test_source_ref_shape(self, tmp_storage):
        """source_ref is a file reference echoing filename and content type."""
        path = tmp_storage / "doc.txt"
        path.write_text("x", encoding="utf-8")

        result = self.plugin.import_content(str(path))

        assert result.source_ref == {
            "type": "file",
            "original_filename": "doc.txt",
            "content_type": "text/plain",
        }

    def test_missing_file_raises(self, tmp_storage):
        """A nonexistent source path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            self.plugin.import_content(str(tmp_storage / "absent.txt"))

    def test_invalid_utf8_raises_value_error(self, tmp_storage):
        """Bytes that are not valid UTF-8 raise a humanized ValueError."""
        path = tmp_storage / "bad.txt"
        path.write_bytes(b"\xff\xfe\x00invalid")

        with pytest.raises(ValueError, match="not valid UTF-8"):
            self.plugin.import_content(str(path))


class TestGetParameters:
    """``get_parameters`` contract."""

    def test_returns_empty_list(self):
        """The simple plugin exposes no configurable parameters."""
        assert SimpleImportPlugin().get_parameters() == []


class TestMimeForExtension:
    """``_mime_for_extension`` mapping for every supported extension."""

    def test_txt(self):
        """.txt maps to text/plain."""
        assert _mime_for_extension(".txt") == "text/plain"

    def test_md(self):
        """.md maps to text/markdown."""
        assert _mime_for_extension(".md") == "text/markdown"

    def test_html(self):
        """.html maps to text/html."""
        assert _mime_for_extension(".html") == "text/html"

    def test_uppercase_normalized(self):
        """Extension matching is case-insensitive."""
        assert _mime_for_extension(".MD") == "text/markdown"

    def test_unknown_defaults_to_plain(self):
        """Unknown extensions fall back to text/plain."""
        assert _mime_for_extension(".xyz") == "text/plain"


class TestClassAttributes:
    """Class-level declarations used by routing/UI."""

    def test_supported_source_types(self):
        """Only file sources are handled."""
        assert SimpleImportPlugin.supported_source_types == {"file"}

    def test_file_extensions(self):
        """Declares the plain-text extensions it accepts."""
        assert SimpleImportPlugin.file_extensions == ["txt", "md", "html", "htm"]

    def test_capabilities(self):
        """Produces only the TEXT capability."""
        assert SimpleImportPlugin.produces_capabilities == [Capability.TEXT]

    def test_name(self):
        """Registered under the stable plugin name."""
        assert SimpleImportPlugin.name == "simple_import"
