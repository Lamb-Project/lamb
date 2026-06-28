"""Boundary doubles for the external libraries the import plugins call.

The rule (borrowed from the Knowledge Store suite): **mock only at the
boundary**. We replace the third-party SDK/client at the exact point each
plugin imports it, so the plugin's own code — SSRF guards, page splitting,
image extraction, metadata building, error humanisation — still runs for
real. Nothing here touches the network.

Each plugin lazy-imports its dependency *inside* the function that uses it
(e.g. ``from markitdown import MarkItDown`` inside ``import_content``), so
patching the attribute on the dependency's module (``markitdown.MarkItDown``)
is picked up at call time. That is what every ``patch_*`` context manager
below does.

Usage::

    from _fakes import patch_markitdown
    with patch_markitdown(text="# Title\\n\\npage one\\n\\n---\\n\\npage two"):
        result = MarkItDownImportPlugin().import_content(path)
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest import mock

# ---------------------------------------------------------------------------
# DNS — url_import's SSRF guard resolves the target host via
# ``socket.getaddrinfo`` before any fetch. Tests must never hit a real
# resolver, so this fake returns a fixed, deterministic address.
# ---------------------------------------------------------------------------


def make_fake_getaddrinfo(ip: str = "93.184.216.34"):
    """Build a ``socket.getaddrinfo`` replacement that always returns ``ip``.

    ``93.184.216.34`` (the historical example.com address) is a public,
    non-private address, so the SSRF guard treats it as allowed.
    """
    import socket as _socket

    family = _socket.AF_INET6 if ":" in ip else _socket.AF_INET

    def _fake_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any):
        return [(family, _socket.SOCK_STREAM, 6, "", (ip, port or 0))]

    return _fake_getaddrinfo


@contextmanager
def patch_dns(ip: str = "93.184.216.34"):
    """Patch ``socket.getaddrinfo`` so host resolution returns ``ip`` offline."""
    with mock.patch("socket.getaddrinfo", make_fake_getaddrinfo(ip)):
        yield


# ---------------------------------------------------------------------------
# markitdown — used by markitdown_import, markitdown_plus_import, and the
# url_import direct-fetch fallback. Call shape:
#     md = MarkItDown(); result = md.convert(src); result.text_content
# ---------------------------------------------------------------------------


class FakeConversionResult:
    """Stand-in for ``markitdown.MarkItDown().convert(...)``'s return value."""

    def __init__(self, text_content: str) -> None:
        self.text_content = text_content


def make_fake_markitdown(text: str = "converted text", raises: Exception | None = None):
    """Build a fake ``MarkItDown`` class returning ``text`` from ``convert``.

    If ``raises`` is given, ``convert`` raises it (to exercise error paths).
    """

    class _FakeMarkItDown:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._args = args
            self._kwargs = kwargs

        def convert(self, src: Any, *args: Any, **kwargs: Any) -> FakeConversionResult:
            if raises is not None:
                raise raises
            return FakeConversionResult(text)

    return _FakeMarkItDown


@contextmanager
def patch_markitdown(text: str = "converted text", raises: Exception | None = None):
    """Patch ``markitdown.MarkItDown`` with a fake for the duration of the block."""
    with mock.patch("markitdown.MarkItDown", make_fake_markitdown(text=text, raises=raises)):
        yield


# ---------------------------------------------------------------------------
# firecrawl — used by url_import's deep-crawl path. Call shape:
#     app = FirecrawlApp(api_key=..., api_url=...)
#     result = app.scrape(url, formats=["markdown"], timeout=...)
#     result.markdown / result.metadata
# ---------------------------------------------------------------------------


class FakeFirecrawlDoc:
    """Stand-in for a Firecrawl scrape result document."""

    def __init__(self, markdown: str = "# Scraped\n\nbody", metadata: Any | None = None) -> None:
        self.markdown = markdown
        self.metadata = metadata if metadata is not None else {"title": "Scraped", "sourceURL": ""}


def make_fake_firecrawl(
    markdown: str = "# Scraped\n\nbody",
    metadata: Any | None = None,
    raises: Exception | None = None,
):
    """Build a fake ``FirecrawlApp`` class whose ``scrape`` returns one doc."""

    class _FakeFirecrawlApp:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._args = args
            self._kwargs = kwargs

        def scrape(self, url: str, *args: Any, **kwargs: Any) -> FakeFirecrawlDoc:
            if raises is not None:
                raise raises
            return FakeFirecrawlDoc(markdown=markdown, metadata=metadata)

    return _FakeFirecrawlApp


@contextmanager
def patch_firecrawl(
    markdown: str = "# Scraped\n\nbody",
    metadata: Any | None = None,
    raises: Exception | None = None,
):
    """Patch ``firecrawl.FirecrawlApp`` with a fake for the duration of the block."""
    with mock.patch(
        "firecrawl.FirecrawlApp",
        make_fake_firecrawl(markdown=markdown, metadata=metadata, raises=raises),
    ):
        yield


# ---------------------------------------------------------------------------
# PyMuPDF (fitz) — used by markitdown_plus_import._extract_images. Call shape:
#     doc = fitz.open(path); len(doc); page = doc[i]
#     page.get_images(full=True) -> [(xref, ...), ...]
#     doc.extract_image(xref) -> {"image": bytes, "ext": "png"}
#     page.get_pixmap(dpi=144).tobytes("png") -> bytes
#     doc.close()
# ---------------------------------------------------------------------------


class _FakePixmap:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def tobytes(self, *_args: Any, **_kwargs: Any) -> bytes:
        return self._data


class _FakeFitzPage:
    def __init__(self, image_xrefs: list[int], page_png: bytes) -> None:
        self._image_xrefs = image_xrefs
        self._page_png = page_png

    def get_images(self, full: bool = False) -> list[tuple]:
        # Real PyMuPDF returns tuples whose first element is the xref.
        return [(xref, 0, 0, 0, 0, "", "", "") for xref in self._image_xrefs]

    def get_pixmap(self, *_args: Any, **_kwargs: Any) -> _FakePixmap:
        return _FakePixmap(self._page_png)


class FakeFitzDoc:
    """Stand-in for ``fitz.open(...)`` covering the calls _extract_images makes."""

    def __init__(
        self,
        pages: int = 1,
        images_per_page: int = 1,
        image_bytes: bytes = b"\x89PNG-fake-image",
        page_png: bytes = b"\x89PNG-fake-page",
        extension: str = "png",
    ) -> None:
        self._image_bytes = image_bytes
        self._extension = extension
        # Give each image a unique xref so extract_image is exercised per image.
        xref = 1
        self._pages: list[_FakeFitzPage] = []
        for _ in range(pages):
            xrefs = list(range(xref, xref + images_per_page))
            xref += images_per_page
            self._pages.append(_FakeFitzPage(xrefs, page_png))
        self.closed = False

    def __len__(self) -> int:
        return len(self._pages)

    def __getitem__(self, idx: int) -> _FakeFitzPage:
        return self._pages[idx]

    def extract_image(self, xref: int) -> dict[str, Any]:
        return {"image": self._image_bytes, "ext": self._extension}

    def close(self) -> None:
        self.closed = True


@contextmanager
def patch_fitz(doc: FakeFitzDoc | None = None, raises: Exception | None = None):
    """Patch ``fitz.open`` to return a :class:`FakeFitzDoc` (or raise)."""
    fake_doc = doc if doc is not None else FakeFitzDoc()

    def _fake_open(*_args: Any, **_kwargs: Any) -> FakeFitzDoc:
        if raises is not None:
            raise raises
        return fake_doc

    with mock.patch("fitz.open", _fake_open):
        yield fake_doc


# ---------------------------------------------------------------------------
# openai — used by markitdown_plus_import._describe_image (llm mode). Call shape:
#     client = OpenAI(api_key=...)
#     resp = client.chat.completions.create(model=..., messages=..., max_tokens=...)
#     resp.choices[0].message.content ; resp.usage.total_tokens
# ---------------------------------------------------------------------------


def make_fake_openai(description: str = "A fake description.", raises: Exception | None = None):
    """Build a fake ``OpenAI`` class whose vision call returns ``description``."""

    class _Msg:
        def __init__(self, content: str) -> None:
            self.message = mock.Mock(content=content)

    class _Resp:
        def __init__(self, content: str) -> None:
            self.choices = [_Msg(content)]
            self.usage = mock.Mock(total_tokens=42)

    class _Completions:
        def create(self, *args: Any, **kwargs: Any) -> _Resp:
            if raises is not None:
                raise raises
            return _Resp(description)

    class _Chat:
        def __init__(self) -> None:
            self.completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.chat = _Chat()

    return _FakeOpenAI


@contextmanager
def patch_openai_vision(description: str = "A fake description.", raises: Exception | None = None):
    """Patch ``openai.OpenAI`` with a fake vision client for the block."""
    with mock.patch("openai.OpenAI", make_fake_openai(description=description, raises=raises)):
        yield
