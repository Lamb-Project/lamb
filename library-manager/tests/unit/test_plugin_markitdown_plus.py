"""Unit tests for ``MarkItDownPlusPlugin`` — the richest import plugin.

All third-party SDKs are mocked at their boundaries:

* ``markitdown.MarkItDown`` via ``patch_markitdown``
* ``fitz.open`` via ``patch_fitz`` (PyMuPDF)
* ``openai.OpenAI`` via ``patch_openai_vision``

so the plugin's own logic — page splitting, image extraction, page
rasterisation, MIME mapping, description modes, and stats accounting — runs
for real. Files live under ``tmp_storage`` and only need to exist with the
correct extension.
"""

from __future__ import annotations

from unittest import mock

import pytest
from _fakes import FakeFitzDoc, patch_fitz, patch_markitdown, patch_openai_vision
from plugins.base import ImportResult
from plugins.markitdown_plus_import import (
    _EXT_NORMALIZE,
    MarkItDownPlusPlugin,
    _describe_image,
    _extract_images,
    _image_mime,
    _split_into_pages,
)


def _touch(path):
    """Create an empty file (content irrelevant — SDKs are faked)."""
    path.write_bytes(b"")
    return path


# ---------------------------------------------------------------------------
# _split_into_pages — all three break patterns
# ---------------------------------------------------------------------------


class TestSplitIntoPages:
    """Every page-break pattern plus the non-splitting edge cases."""

    def test_horizontal_rule(self):
        """``---`` horizontal rules split page-aware content."""
        pages = _split_into_pages("one\n\n---\n\ntwo\n\n---\n\nthree", "pdf")
        assert [p.text for p in pages] == ["one", "two", "three"]
        assert [p.page_number for p in pages] == [1, 2, 3]

    def test_form_feed(self):
        """Form-feed (\\f) markers split content."""
        pages = _split_into_pages("one\n\ftwo\n\fthree", "docx")
        assert len(pages) == 3

    def test_html_comment_marker(self):
        """``<!-- page break -->`` comments split content (case-insensitive)."""
        pages = _split_into_pages("one\n<!-- PAGE BREAK -->\ntwo", "pptx")
        assert len(pages) == 2

    def test_non_page_aware_returns_empty(self):
        """Non-page-aware extensions never split."""
        assert _split_into_pages("a\n\n---\n\nb", "html") == []

    def test_single_page_returns_empty(self):
        """Markers that yield fewer than two non-empty pages return empty."""
        assert _split_into_pages("only one page\n\n---\n\n", "pdf") == []

    def test_no_markers_returns_empty(self):
        """No markers at all returns empty."""
        assert _split_into_pages("plain text", "pdf") == []

    def test_empty_pages_filtered(self):
        """Blank sections between markers are dropped."""
        pages = _split_into_pages("Page 1\n\n---\n\n\n\n---\n\nPage 3", "pdf")
        assert len(pages) == 2

    def test_blank_sections_do_not_create_page_number_gaps(self):
        """Empty parts must not consume a page index.

        ``"Page 1 / <blank> / Page 3"`` splits into three parts, but the blank
        middle one is dropped. The two surviving pages must be numbered 1 and 2
        (contiguous) rather than 1 and 3 — otherwise the on-disk
        ``page_NNN.md`` filenames would have gaps.
        """
        pages = _split_into_pages("Page 1\n\n---\n\n\n\n---\n\nPage 3", "pdf")
        assert [p.text for p in pages] == ["Page 1", "Page 3"]
        assert [p.page_number for p in pages] == [1, 2]

    def test_multiple_interior_blanks_stay_contiguous(self):
        """Several blank sections still yield 1,2,3 with no gaps."""
        content = "A\n\n---\n\n\n\n---\n\nB\n\n---\n\n\n\n---\n\nC"
        pages = _split_into_pages(content, "pdf")
        assert [p.text for p in pages] == ["A", "B", "C"]
        assert [p.page_number for p in pages] == [1, 2, 3]


# ---------------------------------------------------------------------------
# _image_mime + _EXT_NORMALIZE
# ---------------------------------------------------------------------------


class TestImageMime:
    """``_image_mime`` mapping including dot/case handling and the fallback."""

    @pytest.mark.parametrize(
        ("ext", "expected"),
        [
            ("png", "image/png"),
            ("jpg", "image/jpeg"),
            ("jpeg", "image/jpeg"),
            ("gif", "image/gif"),
            ("bmp", "image/bmp"),
            ("webp", "image/webp"),
            ("tiff", "image/tiff"),
            ("svg", "image/svg+xml"),
        ],
    )
    def test_known_extensions(self, ext, expected):
        """Each known extension maps to its MIME type."""
        assert _image_mime(ext) == expected

    def test_unknown_defaults_to_png(self):
        """Unknown extensions fall back to image/png."""
        assert _image_mime("xyz") == "image/png"

    def test_dot_prefix_stripped(self):
        """A leading dot is stripped before lookup."""
        assert _image_mime(".jpeg") == "image/jpeg"

    def test_uppercase_normalized(self):
        """Lookup is case-insensitive."""
        assert _image_mime("PNG") == "image/png"


class TestExtNormalize:
    """``_EXT_NORMALIZE`` rewrites exotic PyMuPDF extensions to viewable ones."""

    def test_known_normalizations(self):
        """Each exotic format normalizes to a browser-friendly equivalent."""
        assert _EXT_NORMALIZE["tif"] == "tiff"
        assert _EXT_NORMALIZE["jpx"] == "jpg"
        assert _EXT_NORMALIZE["jb2"] == "png"

    def test_unmapped_passthrough(self):
        """An extension not in the map is left to the caller (no key)."""
        assert "png" not in _EXT_NORMALIZE


# ---------------------------------------------------------------------------
# _describe_image — all four modes
# ---------------------------------------------------------------------------


class TestDescribeImage:
    """``_describe_image`` across basic / none / llm modes."""

    def test_basic_mode(self):
        """basic mode returns a filename-style description."""
        assert _describe_image(b"x", "img_001.png", "png", "basic", {}, {}) == (
            "Image: img_001.png"
        )

    def test_none_mode(self):
        """none (and any non-basic/non-llm) mode returns None."""
        assert _describe_image(b"x", "img_001.png", "png", "none", {}, {}) is None

    def test_llm_mode_without_key_falls_back(self):
        """llm mode with no openai_vision key falls back to filename text."""
        assert _describe_image(b"x", "img_001.png", "png", "llm", {}, {}) == (
            "Image: img_001.png"
        )

    def test_llm_mode_success_records_stats(self):
        """llm mode with a key returns the model description and records stats."""
        stats = {"images_with_llm_descriptions": 0, "llm_calls": []}
        with patch_openai_vision(description="A red square."):
            desc = _describe_image(
                b"x", "img_001.png", "png", "llm", {"openai_vision": "sk-1"}, stats
            )
        assert desc == "A red square."
        assert stats["images_with_llm_descriptions"] == 1
        assert stats["llm_calls"][0]["success"] is True
        assert stats["llm_calls"][0]["tokens_used"] == 42

    def test_llm_mode_failure_falls_back_and_records(self):
        """A vision-call exception falls back to filename text and logs failure."""
        stats = {"images_with_llm_descriptions": 0, "llm_calls": []}
        with patch_openai_vision(raises=RuntimeError("api down")):
            desc = _describe_image(
                b"x", "img_001.png", "png", "llm", {"openai_vision": "sk-1"}, stats
            )
        assert desc == "Image: img_001.png"
        assert stats["llm_calls"][0]["success"] is False
        assert "api down" in stats["llm_calls"][0]["error"]


# ---------------------------------------------------------------------------
# _extract_images — PyMuPDF mocked
# ---------------------------------------------------------------------------


class TestExtractImages:
    """``_extract_images`` against a fake PyMuPDF document."""

    def test_non_pdf_returns_empty(self, tmp_storage):
        """A non-PDF suffix short-circuits to no images."""
        path = _touch(tmp_storage / "doc.docx")
        assert _extract_images(path, "basic", {}, {}) == []

    def test_open_failure_returns_empty(self, tmp_storage):
        """If fitz.open raises, extraction returns no images."""
        path = _touch(tmp_storage / "doc.pdf")
        with patch_fitz(raises=RuntimeError("corrupt pdf")):
            assert _extract_images(path, "basic", {}, {}) == []

    def test_extracts_bitmaps_and_rasterized_pages(self, tmp_storage):
        """Each embedded image plus one rasterized PNG per page is returned."""
        path = _touch(tmp_storage / "doc.pdf")
        stats = {}
        doc = FakeFitzDoc(pages=2, images_per_page=1)
        with patch_fitz(doc=doc):
            images = _extract_images(path, "basic", {}, stats)

        # 2 embedded bitmaps + 2 rasterized pages.
        assert len(images) == 4
        bitmaps = [i for i in images if i.filename.startswith("img_")]
        renders = [i for i in images if i.filename.startswith("page_")]
        assert [i.filename for i in bitmaps] == ["img_001.png", "img_002.png"]
        assert [i.filename for i in renders] == ["page_001.png", "page_002.png"]
        assert [i.page_number for i in renders] == [1, 2]
        # basic mode attaches filename-style descriptions.
        assert images[0].description == "Image: img_001.png"
        assert stats["rendered_page_fallback"] == 2
        assert doc.closed is True

    def test_fitz_not_installed_returns_empty(self, tmp_storage):
        """If PyMuPDF (fitz) cannot be imported, extraction returns empty."""
        import builtins

        path = _touch(tmp_storage / "doc.pdf")
        real_import = builtins.__import__

        def _no_fitz(name, *args, **kwargs):
            if name == "fitz":
                raise ImportError("No module named 'fitz'")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=_no_fitz):
            assert _extract_images(path, "basic", {}, {}) == []

    def test_extract_image_failure_skips_bitmap(self, tmp_storage):
        """A bitmap whose extract_image raises is skipped; pages still render."""
        path = _touch(tmp_storage / "doc.pdf")

        class _Doc(FakeFitzDoc):
            def extract_image(self, xref):
                raise RuntimeError("bad xref")

        with patch_fitz(doc=_Doc(pages=1, images_per_page=1)):
            images = _extract_images(path, "basic", {}, {})

        # No bitmaps survived; the single rasterized page remains.
        assert [i.filename for i in images] == ["page_001.png"]

    def test_empty_image_payload_skipped(self, tmp_storage):
        """A bitmap with no image bytes is skipped."""
        path = _touch(tmp_storage / "doc.pdf")

        class _Doc(FakeFitzDoc):
            def extract_image(self, xref):
                return {"image": b"", "ext": "png"}

        with patch_fitz(doc=_Doc(pages=1, images_per_page=1)):
            images = _extract_images(path, "basic", {}, {})

        assert [i.filename for i in images] == ["page_001.png"]

    def test_rasterize_failure_skips_page(self, tmp_storage):
        """A page whose get_pixmap raises is skipped during rasterisation."""
        from _fakes import _FakeFitzPage

        path = _touch(tmp_storage / "doc.pdf")

        class _BadPage(_FakeFitzPage):
            def get_pixmap(self, *a, **k):
                raise RuntimeError("render failed")

        class _Doc(FakeFitzDoc):
            def __init__(self):
                super().__init__(pages=1, images_per_page=0)
                self._pages = [_BadPage([], b"")]

        doc = _Doc()
        with patch_fitz(doc=doc):
            images = _extract_images(path, "basic", {}, {})

        # No bitmaps, and the only page failed to rasterize.
        assert images == []

    def test_exotic_extension_normalized_in_filename(self, tmp_storage):
        """A PyMuPDF 'jpx' image is normalized to a 'jpg' filename."""
        path = _touch(tmp_storage / "doc.pdf")
        doc = FakeFitzDoc(pages=1, images_per_page=1, extension="jpx")
        with patch_fitz(doc=doc):
            images = _extract_images(path, "basic", {}, {})

        assert images[0].filename == "img_001.jpg"


# ---------------------------------------------------------------------------
# import_content — full pipeline
# ---------------------------------------------------------------------------


class TestImportContent:
    """``MarkItDownPlusPlugin.import_content`` end to end with faked SDKs."""

    def setup_method(self):
        """Fresh plugin per test."""
        self.plugin = MarkItDownPlusPlugin()

    def test_pdf_with_images_and_pages(self, tmp_storage):
        """A faked PDF yields full text, pages, images, and processing stats."""
        path = _touch(tmp_storage / "report.pdf")
        text = "Page one\n\n---\n\nPage two"
        doc = FakeFitzDoc(pages=2, images_per_page=1)
        with patch_markitdown(text=text), patch_fitz(doc=doc):
            result = self.plugin.import_content(str(path))

        assert isinstance(result, ImportResult)
        assert result.full_text == text
        assert len(result.pages) == 2
        # 2 bitmaps + 2 rasterized pages.
        assert len(result.images) == 4
        assert result.metadata["image_count"] == 4
        assert result.metadata["page_count"] == 2
        assert result.metadata["image_descriptions_mode"] == "basic"
        assert result.metadata["import_plugin"] == "markitdown_plus_import"

    def test_image_mode_none_skips_extraction(self, tmp_storage):
        """image_descriptions='none' skips image extraction entirely."""
        path = _touch(tmp_storage / "report.pdf")
        with patch_markitdown(text="body"):
            result = self.plugin.import_content(str(path), image_descriptions="none")

        assert result.images == []
        assert result.metadata["image_count"] == 0

    def test_description_and_citation_passthrough(self, tmp_storage):
        """Optional description/citation kwargs land in metadata."""
        path = _touch(tmp_storage / "report.pdf")
        with patch_markitdown(text="body"):
            result = self.plugin.import_content(
                str(path),
                image_descriptions="none",
                description="A report",
                citation="Cite 2024",
            )

        assert result.metadata["description"] == "A report"
        assert result.metadata["citation"] == "Cite 2024"

    def test_non_pdf_extracts_no_bitmaps(self, tmp_storage):
        """A .docx is page-aware but yields no images (PyMuPDF only reads PDFs)."""
        path = _touch(tmp_storage / "doc.docx")
        with patch_markitdown(text="A\n\f\nB"):
            result = self.plugin.import_content(str(path))

        assert result.images == []
        assert len(result.pages) == 2

    def test_conversion_error_humanized(self, tmp_storage):
        """A converter exception becomes a RuntimeError without leaking internals."""
        path = _touch(tmp_storage / "report.pdf")
        with (
            patch_markitdown(raises=ValueError("internal boom")),
            pytest.raises(RuntimeError) as exc,
        ):
            self.plugin.import_content(str(path))
        assert "internal boom" not in str(exc.value)

    def test_missing_file_raises(self, tmp_storage):
        """A nonexistent source path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            self.plugin.import_content(str(tmp_storage / "absent.pdf"))


class TestGetParameters:
    """``get_parameters`` contract."""

    def test_parameter_names_and_choices(self):
        """Exposes image_descriptions (enum) plus description/citation."""
        params = MarkItDownPlusPlugin().get_parameters()
        names = [p.name for p in params]
        assert names == ["image_descriptions", "description", "citation"]
        img = next(p for p in params if p.name == "image_descriptions")
        assert img.choices == ["none", "basic", "llm"]
        assert img.default == "basic"
