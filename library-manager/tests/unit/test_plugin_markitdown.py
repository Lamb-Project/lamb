"""Unit tests for ``MarkItDownImportPlugin`` with MarkItDown mocked at the boundary.

The ``markitdown`` SDK is replaced via ``patch_markitdown`` so the plugin's own
logic (page splitting, metadata building, empty-content placeholder, error
humanisation) runs for real. Files are created under ``tmp_storage`` and only
need to exist with the right extension — their bytes are never read because
MarkItDown is faked.
"""

from __future__ import annotations

import pytest
from _fakes import patch_markitdown
from plugins.base import ImportResult
from plugins.markitdown_import import MarkItDownImportPlugin
from plugins.markitdown_plus_import import _split_into_pages


def _touch(path):
    """Create an empty file (content irrelevant — MarkItDown is faked)."""
    path.write_bytes(b"")
    return path


class TestImportContent:
    """``MarkItDownImportPlugin.import_content`` with a faked converter."""

    def setup_method(self):
        """Fresh plugin per test."""
        self.plugin = MarkItDownImportPlugin()

    def test_returns_converted_text(self, tmp_storage):
        """The converter's text_content becomes ``full_text``."""
        path = _touch(tmp_storage / "doc.docx")
        with patch_markitdown(text="# Converted\n\nbody"):
            result = self.plugin.import_content(str(path))

        assert isinstance(result, ImportResult)
        assert result.full_text == "# Converted\n\nbody"
        assert result.metadata["import_plugin"] == "markitdown_import"

    def test_pdf_with_page_breaks_splits_pages(self, tmp_storage):
        """A page-aware ext (.pdf) with ``---`` markers yields multiple pages."""
        path = _touch(tmp_storage / "doc.pdf")
        text = "Page one\n\n---\n\nPage two\n\n---\n\nPage three"
        with patch_markitdown(text=text):
            result = self.plugin.import_content(str(path))

        assert len(result.pages) == 3
        assert result.metadata["page_count"] == 3
        assert result.pages[0].text == "Page one"

    def test_non_page_aware_ext_has_no_pages(self, tmp_storage):
        """A non-page-aware ext (.html) never splits even with ``---``."""
        path = _touch(tmp_storage / "doc.html")
        with patch_markitdown(text="A\n\n---\n\nB"):
            result = self.plugin.import_content(str(path))

        assert result.pages == []
        assert result.metadata["page_count"] == 0

    def test_empty_content_placeholder(self, tmp_storage):
        """Blank conversion output is replaced with a no-text placeholder."""
        path = _touch(tmp_storage / "blank.pdf")
        with patch_markitdown(text="   \n  "):
            result = self.plugin.import_content(str(path))

        assert "No extractable text found" in result.full_text
        assert "blank.pdf" in result.full_text

    def test_metadata_and_source_ref_shape(self, tmp_storage):
        """Metadata carries mime/size/char count; source_ref is a file ref."""
        path = _touch(tmp_storage / "sheet.xlsx")
        with patch_markitdown(text="data"):
            result = self.plugin.import_content(str(path))

        meta = result.metadata
        assert meta["original_filename"] == "sheet.xlsx"
        assert meta["content_type"].endswith("spreadsheetml.sheet")
        assert meta["character_count"] == len("data")
        assert result.source_ref == {
            "type": "file",
            "original_filename": "sheet.xlsx",
            "content_type": meta["content_type"],
        }

    def test_description_and_citation_passthrough(self, tmp_storage):
        """Optional description/citation kwargs land in metadata."""
        path = _touch(tmp_storage / "doc.docx")
        with patch_markitdown(text="body"):
            result = self.plugin.import_content(
                str(path), description="A doc", citation="Ref 2024"
            )

        assert result.metadata["description"] == "A doc"
        assert result.metadata["citation"] == "Ref 2024"

    def test_missing_file_raises(self, tmp_storage):
        """A nonexistent source path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            self.plugin.import_content(str(tmp_storage / "absent.pdf"))

    def test_conversion_error_humanized(self, tmp_storage):
        """A converter exception is translated into a RuntimeError."""
        path = _touch(tmp_storage / "doc.pdf")
        with (
            patch_markitdown(raises=ValueError("boom internal")),
            pytest.raises(RuntimeError) as exc,
        ):
            self.plugin.import_content(str(path))
        # The raw internal message is not surfaced verbatim.
        assert "boom internal" not in str(exc.value)


class TestSplitIntoPages:
    """``_split_into_pages`` direct calls (shared with markitdown_plus)."""

    def test_non_page_aware_returns_empty(self):
        """A non-page-aware extension returns no pages."""
        assert _split_into_pages("a\n\n---\n\nb", "html") == []

    def test_no_markers_returns_empty(self):
        """Page-aware ext with no break markers returns no pages."""
        assert _split_into_pages("just text", "pdf") == []

    def test_multiple_pages(self):
        """``---`` markers split a PDF into numbered pages."""
        pages = _split_into_pages("one\n\n---\n\ntwo", "pdf")
        assert [p.page_number for p in pages] == [1, 2]
        assert [p.text for p in pages] == ["one", "two"]


class TestGetParameters:
    """``get_parameters`` contract."""

    def test_description_and_citation(self):
        """Exposes optional description and citation parameters."""
        names = [p.name for p in MarkItDownImportPlugin().get_parameters()]
        assert names == ["description", "citation"]
