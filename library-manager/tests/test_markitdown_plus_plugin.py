"""Unit tests for ``plugins.markitdown_plus_import``.

MarkItDown, PyMuPDF (``fitz``) and OpenAI are all mocked so the tests run
offline. Covers the conversion happy/error paths, page splitting, MIME maps,
image extraction (bitmap + rasterize fallback + no-fitz), and the three
``_describe_image`` modes.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

import plugins.markitdown_plus_import as mp
from plugins.markitdown_plus_import import (
    MarkItDownPlusPlugin,
    _describe_image,
    _guess_mime,
    _image_mime,
    _split_into_pages,
)


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ext,expected",
    [("png", "image/png"), (".jpg", "image/jpeg"), ("JPEG", "image/jpeg"),
     ("webp", "image/webp"), ("unknown", "image/png")],
)
def test_image_mime(ext, expected):
    assert _image_mime(ext) == expected


@pytest.mark.parametrize(
    "ext,expected",
    [(".pdf", "application/pdf"), (".csv", "text/csv"),
     (".mp3", "audio/mpeg"), (".zzz", "application/octet-stream")],
)
def test_guess_mime(ext, expected):
    assert _guess_mime(ext) == expected


def test_split_into_pages_non_page_aware_returns_empty():
    assert _split_into_pages("a\n---\nb", "html") == []


def test_split_into_pages_with_breaks():
    content = "Page one\n\n---\n\nPage two\n\n---\n\nPage three"
    pages = _split_into_pages(content, "pdf")
    assert len(pages) == 3
    assert pages[0].text == "Page one"


def test_split_into_pages_no_breaks_returns_empty():
    assert _split_into_pages("single page, no breaks", "pdf") == []


def test_get_parameters():
    names = {p.name for p in MarkItDownPlusPlugin().get_parameters()}
    assert "image_descriptions" in names


# ---------------------------------------------------------------------------
# _describe_image
# ---------------------------------------------------------------------------


def test_describe_image_basic():
    assert _describe_image(b"x", "i.png", "png", "basic", {}, {}) == "Image: i.png"


def test_describe_image_none_mode():
    assert _describe_image(b"x", "i.png", "png", "none", {}, {}) is None


def test_describe_image_llm_no_key():
    stats = {"llm_calls": []}
    assert (
        _describe_image(b"x", "i.png", "png", "llm", {}, stats) == "Image: i.png"
    )


def test_describe_image_llm_success(monkeypatch):
    import openai

    class _Msg:
        content = "  A blue diagram.  "

    class _Choice:
        message = _Msg()

    class _Usage:
        total_tokens = 42

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=lambda **kw: _Resp())
            )

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    stats = {"llm_calls": [], "images_with_llm_descriptions": 0}
    out = _describe_image(b"x", "i.png", "png", "llm", {"openai_vision": "sk"}, stats)
    assert out == "A blue diagram."
    assert stats["images_with_llm_descriptions"] == 1
    assert stats["llm_calls"][0]["success"] is True


def test_describe_image_llm_failure(monkeypatch):
    import openai

    class FakeOpenAI:
        def __init__(self, **kwargs):
            raise RuntimeError("api down")

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    stats = {"llm_calls": []}
    out = _describe_image(b"x", "i.png", "png", "llm", {"openai_vision": "sk"}, stats)
    assert out == "Image: i.png"
    assert stats["llm_calls"][0]["success"] is False


# ---------------------------------------------------------------------------
# _extract_images (fitz mocked)
# ---------------------------------------------------------------------------


def _install_fake_fitz(monkeypatch, *, pages):
    fake = types.ModuleType("fitz")

    class FakeDoc:
        def __init__(self, pages):
            self._pages = pages

        def __len__(self):
            return len(self._pages)

        def __getitem__(self, i):
            return self._pages[i]

        def extract_image(self, xref):
            return self._extract_map.get(xref)

        def close(self):
            pass

    doc = FakeDoc(pages)
    doc._extract_map = {}
    for p in pages:
        doc._extract_map.update(getattr(p, "_extract_map", {}))
    fake.open = lambda path: doc
    monkeypatch.setitem(sys.modules, "fitz", fake)
    return doc


class _FakePage:
    def __init__(self, images=None, extract_map=None):
        self._images = images or []
        self._extract_map = extract_map or {}

    def get_images(self, full=True):
        return self._images

    def get_pixmap(self, dpi=144):
        return types.SimpleNamespace(tobytes=lambda fmt: b"PNGBYTES")


def test_extract_images_no_fitz(monkeypatch):
    monkeypatch.setitem(sys.modules, "fitz", None)
    assert mp._extract_images(Path("x.pdf"), "basic", {}, {}) == []


def test_extract_images_non_pdf_suffix(monkeypatch):
    _install_fake_fitz(monkeypatch, pages=[])
    assert mp._extract_images(Path("x.docx"), "basic", {}, {}) == []


def test_extract_images_bitmap(monkeypatch):
    page = _FakePage(
        images=[(7,)],
        extract_map={7: {"image": b"IMGDATA", "ext": "png"}},
    )
    _install_fake_fitz(monkeypatch, pages=[page])
    out = mp._extract_images(Path("x.pdf"), "basic", {}, {"llm_calls": []})
    assert len(out) == 1
    assert out[0].filename == "img_001.png"
    assert out[0].page_number == 1


def test_extract_images_open_failure(monkeypatch):
    fake = types.ModuleType("fitz")

    def _open(path):
        raise RuntimeError("cannot open")

    fake.open = _open
    monkeypatch.setitem(sys.modules, "fitz", fake)
    assert mp._extract_images(Path("x.pdf"), "basic", {}, {}) == []


def test_extract_images_skips_bad_xref_and_empty(monkeypatch):
    # xref 1 raises in extract_image (skipped); xref 2 returns empty (skipped).
    class _BadPage(_FakePage):
        def __init__(self):
            super().__init__(images=[(1,), (2,)])

    page = _BadPage()

    class _Doc:
        def __len__(self):
            return 1

        def __getitem__(self, i):
            return page

        def extract_image(self, xref):
            if xref == 1:
                raise RuntimeError("corrupt")
            return {"image": b""}  # empty -> skipped

        def close(self):
            pass

    fake = types.ModuleType("fitz")
    fake.open = lambda path: _Doc()
    monkeypatch.setitem(sys.modules, "fitz", fake)
    # No bitmap images survive -> falls back to rasterizing the single page.
    out = mp._extract_images(Path("x.pdf"), "basic", {}, {"llm_calls": []})
    assert out[0].filename == "page_001.png"


def test_extract_images_rasterize_pixmap_failure(monkeypatch):
    class _BoomPage(_FakePage):
        def get_pixmap(self, dpi=144):
            raise RuntimeError("render failed")

    _install_fake_fitz(monkeypatch, pages=[_BoomPage(images=[])])
    # Pixmap render fails -> page skipped -> no images.
    assert mp._extract_images(Path("x.pdf"), "basic", {}, {"llm_calls": []}) == []


def test_extract_images_rasterize_fallback(monkeypatch):
    # No bitmap images -> render each page as PNG.
    page = _FakePage(images=[])
    stats = {"llm_calls": []}
    _install_fake_fitz(monkeypatch, pages=[page, _FakePage(images=[])])
    out = mp._extract_images(Path("x.pdf"), "basic", {}, stats)
    assert len(out) == 2
    assert out[0].filename == "page_001.png"
    assert stats["rendered_page_fallback"] == 2


# ---------------------------------------------------------------------------
# import_content
# ---------------------------------------------------------------------------


def _fake_markitdown(monkeypatch, *, text="converted", raises=None):
    import markitdown

    class FakeMD:
        def convert(self, path):
            if raises is not None:
                raise raises
            return types.SimpleNamespace(text_content=text)

    monkeypatch.setattr(markitdown, "MarkItDown", FakeMD)


def test_import_content_file_not_found():
    with pytest.raises(FileNotFoundError):
        MarkItDownPlusPlugin().import_content("/nonexistent/file.pdf")


def test_import_content_success_html(tmp_path, monkeypatch):
    # .html is not page-aware -> no image extraction, no pages.
    f = tmp_path / "doc.html"
    f.write_text("<html></html>")
    _fake_markitdown(monkeypatch, text="# Title\n\nbody")
    result = MarkItDownPlusPlugin().import_content(
        str(f), description="d", citation="c"
    )
    assert "Title" in result.full_text
    assert result.metadata["import_plugin"] == "markitdown_plus_import"
    assert result.metadata["description"] == "d"
    assert result.pages == []
    assert result.images == []


def test_import_content_conversion_error_humanized(tmp_path, monkeypatch):
    f = tmp_path / "doc.html"
    f.write_text("x")
    _fake_markitdown(monkeypatch, raises=RuntimeError("MissingDependencyException"))
    with pytest.raises(RuntimeError):
        MarkItDownPlusPlugin().import_content(str(f))


def test_import_content_pdf_with_images(tmp_path, monkeypatch):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    _fake_markitdown(monkeypatch, text="page one\n\n---\n\npage two")
    page = _FakePage(images=[(1,)], extract_map={1: {"image": b"I", "ext": "png"}})
    _install_fake_fitz(monkeypatch, pages=[page])
    result = MarkItDownPlusPlugin().import_content(str(f), image_descriptions="basic")
    assert result.metadata["image_count"] == 1
    assert result.metadata["page_count"] == 2


def test_import_content_image_mode_none_skips_extraction(tmp_path, monkeypatch):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF fake")
    _fake_markitdown(monkeypatch, text="no breaks here")
    result = MarkItDownPlusPlugin().import_content(str(f), image_descriptions="none")
    assert result.metadata["image_count"] == 0
    assert result.metadata["image_descriptions_mode"] == "none"
