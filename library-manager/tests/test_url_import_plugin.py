"""Unit tests for ``plugins.url_import`` (Firecrawl + MarkItDown fallback).

Both backends are import-mocked so the tests never hit the network. We cover
the URL-validation guard, both crawl paths, the various Firecrawl document
shapes (object metadata, dict metadata, empty pages), error wrapping, and the
``_safe_int`` / ``_safe_bool`` helpers.
"""

from __future__ import annotations

import sys
import types

import pytest

from plugins.url_import import UrlImportPlugin, _safe_bool, _safe_int


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,default,expected",
    [(None, 7, 7), ("3", 0, 3), ("x", 9, 9), (5, 0, 5), (1.5, 0, 1)],
)
def test_safe_int(value, default, expected):
    assert _safe_int(value, default) == expected


@pytest.mark.parametrize(
    "value,default,expected",
    [
        (None, True, True),
        (True, False, True),
        ("false", True, False),
        ("0", True, False),
        ("yes", False, True),
        (1, False, True),
    ],
)
def test_safe_bool(value, default, expected):
    assert _safe_bool(value, default) is expected


def test_get_parameters():
    names = {p.name for p in UrlImportPlugin().get_parameters()}
    assert {"max_discovery_depth", "limit", "crawl_entire_domain", "timeout"} <= names


def test_invalid_url_raises():
    with pytest.raises(ValueError):
        UrlImportPlugin().import_content("not-a-url")


# ---------------------------------------------------------------------------
# Firecrawl path
# ---------------------------------------------------------------------------


def _install_fake_firecrawl(monkeypatch, *, crawl_result=None, raises=None):
    import firecrawl

    class FakeApp:
        def __init__(self, **kwargs):
            self.init_kwargs = kwargs

        def crawl(self, url, **kwargs):
            if raises is not None:
                raise raises
            return crawl_result

    monkeypatch.setattr(firecrawl, "FirecrawlApp", FakeApp)


class _Doc:
    def __init__(self, markdown, metadata=None, url=""):
        self.markdown = markdown
        if metadata is not None:
            self.metadata = metadata
        self.url = url


class _Meta:
    def __init__(self, url="", title=""):
        self.url = url
        self.title = title


class _CrawlResult:
    def __init__(self, data):
        self.data = data


def test_firecrawl_crawl_failure_wrapped(monkeypatch):
    _install_fake_firecrawl(monkeypatch, raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="Firecrawl crawl failed"):
        UrlImportPlugin().import_content(
            "https://example.com", api_keys={"firecrawl_key": "fc-key"}
        )


def test_firecrawl_no_pages_returns_placeholder(monkeypatch):
    _install_fake_firecrawl(monkeypatch, crawl_result=_CrawlResult(data=[]))
    result = UrlImportPlugin().import_content(
        "https://example.com", api_keys={"firecrawl_key": "fc-key"}
    )
    assert "No content could be crawled" in result.full_text
    assert result.metadata["pages_crawled"] == 0


def test_firecrawl_object_docs_with_object_metadata(monkeypatch):
    docs = [
        _Doc("# Page one\n\ntext", metadata=_Meta(url="https://example.com/a",
                                                  title="Page A")),
        _Doc("   ", metadata=_Meta()),  # blank -> skipped
    ]
    _install_fake_firecrawl(monkeypatch, crawl_result=_CrawlResult(data=docs))
    result = UrlImportPlugin().import_content(
        "https://example.com",
        api_keys={"firecrawl_key": "fc-key"},
        description="desc", citation="cite",
    )
    assert "## Page A" in result.full_text
    assert "Source: https://example.com/a" in result.full_text
    assert result.metadata["fetch_method"] == "firecrawl"
    assert result.metadata["description"] == "desc"
    assert result.metadata["citation"] == "cite"
    assert result.metadata["pages_crawled"] == 2


def test_firecrawl_dict_docs(monkeypatch):
    docs = [
        {"markdown": "dict page", "metadata": {"sourceURL": "https://x/b",
                                               "title": "B"}},
    ]
    _install_fake_firecrawl(monkeypatch, crawl_result=_CrawlResult(data=docs))
    result = UrlImportPlugin().import_content(
        "https://x", api_keys={"firecrawl_key": "fc-key"}
    )
    assert "## B" in result.full_text
    assert "dict page" in result.full_text


def test_firecrawl_dict_crawl_result(monkeypatch):
    # crawl returns a plain dict (no .data attribute).
    _install_fake_firecrawl(
        monkeypatch, crawl_result={"data": [{"markdown": "hello"}]}
    )
    result = UrlImportPlugin().import_content(
        "https://x", api_keys={"firecrawl_key": "fc-key"}
    )
    assert "hello" in result.full_text


# ---------------------------------------------------------------------------
# MarkItDown fallback path
# ---------------------------------------------------------------------------


def _install_fake_markitdown(monkeypatch, *, text="", raises=None):
    import markitdown

    class FakeResult:
        def __init__(self, t):
            self.text_content = t

    class FakeMD:
        def convert(self, url):
            if raises is not None:
                raise raises
            return FakeResult(text)

    monkeypatch.setattr(markitdown, "MarkItDown", FakeMD)


def test_markitdown_success(monkeypatch):
    _install_fake_markitdown(monkeypatch, text="# Converted\n\nbody")
    result = UrlImportPlugin().import_content(
        "https://example.com", description="d", citation="c"
    )
    assert "Converted" in result.full_text
    assert result.metadata["fetch_method"] == "markitdown"
    assert result.metadata["description"] == "d"


def test_markitdown_empty_text_placeholder(monkeypatch):
    _install_fake_markitdown(monkeypatch, text="   ")
    result = UrlImportPlugin().import_content("https://example.com")
    assert "No text content could be extracted" in result.full_text


def test_markitdown_convert_failure_wrapped(monkeypatch):
    _install_fake_markitdown(monkeypatch, raises=RuntimeError("bad"))
    with pytest.raises(RuntimeError, match="Failed to fetch and convert"):
        UrlImportPlugin().import_content("https://example.com")


def test_markitdown_not_installed(monkeypatch):
    # Simulate the markitdown import failing.
    monkeypatch.setitem(sys.modules, "markitdown", None)
    with pytest.raises(RuntimeError, match="markitdown is not installed"):
        UrlImportPlugin().import_content("https://example.com")


def test_progress_callback_is_invoked(monkeypatch):
    _install_fake_markitdown(monkeypatch, text="body")
    events = []
    UrlImportPlugin().import_content(
        "https://example.com",
        progress_callback=lambda c, t, m: events.append((c, t, m)),
    )
    assert events  # callback fired for each step
    assert events[-1][0] == events[-1][1]  # last step is "complete"
