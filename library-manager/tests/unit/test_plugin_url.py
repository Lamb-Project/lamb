"""Unit tests for ``UrlImportPlugin`` with HTTP backends mocked at the boundary.

``firecrawl.FirecrawlApp`` and ``markitdown.MarkItDown`` are replaced via the
``patch_firecrawl`` / ``patch_markitdown`` context managers so the plugin's URL
validation, SSRF blocklist, backend-selection branch, metadata building, and
error humanisation all run for real with no network access.
"""

from __future__ import annotations

from unittest import mock

import pytest
from _fakes import patch_firecrawl, patch_markitdown
from plugins.base import ImportResult
from plugins.url_import import UrlImportPlugin, _safe_int

FIRECRAWL_KEYS = {"firecrawl_key": "fc-test"}


class TestUrlValidation:
    """URL scheme/host validation and the SSRF blocklist."""

    def setup_method(self):
        """Fresh plugin per test."""
        self.plugin = UrlImportPlugin()

    def test_no_scheme_raises(self):
        """A URL without a scheme is rejected."""
        with pytest.raises(ValueError, match="Invalid URL"):
            self.plugin.import_content("example.com")

    def test_no_netloc_raises(self):
        """A scheme with no host is rejected."""
        with pytest.raises(ValueError, match="Invalid URL"):
            self.plugin.import_content("http://")

    def test_non_http_scheme_raises(self):
        """Non-http(s) schemes are rejected."""
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            self.plugin.import_content("ftp://example.com/x")

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/p",
            "http://127.0.0.1/p",
            "http://0.0.0.0/p",
            "http://[::1]/p",
            "http://169.254.169.254/latest/meta-data",
            "http://metadata.google.internal/computeMetadata",
        ],
    )
    def test_blocked_hosts(self, url):
        """Each SSRF-sensitive host is rejected."""
        with pytest.raises(ValueError, match="not allowed"):
            self.plugin.import_content(url)


class TestMarkitdownFallback:
    """No firecrawl_key → direct MarkItDown fetch path."""

    def setup_method(self):
        """Fresh plugin per test."""
        self.plugin = UrlImportPlugin()

    def test_returns_markitdown_result(self):
        """Without a key, content is fetched via MarkItDown."""
        with patch_markitdown(text="# Hello"):
            result = self.plugin.import_content("https://example.com/page")

        assert isinstance(result, ImportResult)
        assert result.full_text == "# Hello"
        assert result.metadata["fetch_method"] == "markitdown"
        assert result.metadata["source_url"] == "https://example.com/page"
        assert result.source_ref["type"] == "url"

    def test_empty_text_placeholder(self):
        """Blank conversion output yields a no-content placeholder."""
        with patch_markitdown(text=""):
            result = self.plugin.import_content("https://example.com/empty")

        assert "No text content could be extracted" in result.full_text

    def test_fetch_failure_raises_runtime(self):
        """A converter exception becomes a RuntimeError."""
        with (
            patch_markitdown(raises=Exception("connection refused")),
            pytest.raises(RuntimeError, match="Failed to fetch"),
        ):
            self.plugin.import_content("https://example.com/fail")

    def test_description_and_citation_passthrough(self):
        """Optional description/citation kwargs reach metadata."""
        with patch_markitdown(text="body"):
            result = self.plugin.import_content(
                "https://example.com/p", description="A page", citation="Ref"
            )

        assert result.metadata["description"] == "A page"
        assert result.metadata["citation"] == "Ref"


class TestFirecrawlPath:
    """firecrawl_key present → Firecrawl scrape path."""

    def setup_method(self):
        """Fresh plugin per test."""
        self.plugin = UrlImportPlugin()

    def test_returns_firecrawl_result(self):
        """With a key, content is scraped via Firecrawl."""
        meta = {"title": "Example", "sourceURL": "https://example.com"}
        with patch_firecrawl(markdown="# Example body", metadata=meta):
            result = self.plugin.import_content(
                "https://example.com", api_keys=FIRECRAWL_KEYS
            )

        assert "# Example body" in result.full_text
        assert result.metadata["fetch_method"] == "firecrawl"
        assert result.metadata["pages_crawled"] == 1
        assert result.source_ref["type"] == "url"

    def test_empty_markdown_yields_empty_text(self):
        """A doc with blank markdown contributes no text parts.

        The fake doc still exposes a ``.markdown`` attribute, so it counts as
        one crawled page, but its empty body produces an empty ``full_text``.
        """
        with patch_firecrawl(markdown="", metadata={}):
            result = self.plugin.import_content(
                "https://example.com", api_keys=FIRECRAWL_KEYS
            )

        assert result.full_text == ""
        assert result.metadata["pages_crawled"] == 1

    def test_scrape_failure_raises_runtime(self):
        """A scrape exception becomes a RuntimeError."""
        with (
            patch_firecrawl(raises=Exception("API error")),
            pytest.raises(RuntimeError, match="Firecrawl scrape failed"),
        ):
            self.plugin.import_content("https://example.com", api_keys=FIRECRAWL_KEYS)

    def test_object_metadata_branch(self):
        """Metadata supplied as an object (not a dict) is read via attributes."""

        class _Meta:
            url = "https://example.com/from-attr"
            source_url = ""
            title = "Attr Title"

        with patch_firecrawl(markdown="# body", metadata=_Meta()):
            result = self.plugin.import_content(
                "https://example.com", api_keys=FIRECRAWL_KEYS
            )

        # Title header and source note derived from the object attributes.
        assert "## Attr Title" in result.full_text
        assert "https://example.com/from-attr" in result.full_text

    def test_description_and_citation_passthrough(self):
        """Optional description/citation kwargs reach metadata."""
        meta = {"title": "", "sourceURL": "https://example.com"}
        with patch_firecrawl(markdown="# body", metadata=meta):
            result = self.plugin.import_content(
                "https://example.com",
                api_keys=FIRECRAWL_KEYS,
                description="Desc",
                citation="Cite",
            )

        assert result.metadata["description"] == "Desc"
        assert result.metadata["citation"] == "Cite"


class TestFirecrawlDictResults:
    """Firecrawl returning plain dicts instead of doc objects.

    The shared ``patch_firecrawl`` fake always yields an object with a
    ``.markdown`` attribute, so the dict-shaped branches are driven by patching
    ``firecrawl.FirecrawlApp`` directly at the same boundary.
    """

    def setup_method(self):
        """Fresh plugin per test."""
        self.plugin = UrlImportPlugin()

    def test_dict_with_markdown(self):
        """A dict result carrying markdown is parsed via the dict branch."""
        doc = {"markdown": "# Dict body", "metadata": {"sourceURL": "u", "title": "T"}}
        with mock.patch("firecrawl.FirecrawlApp") as App:
            App.return_value.scrape.return_value = doc
            result = self.plugin.import_content(
                "https://example.com", api_keys=FIRECRAWL_KEYS
            )

        assert "# Dict body" in result.full_text
        assert result.metadata["pages_crawled"] == 1

    def test_dict_without_markdown_is_no_content(self):
        """An empty dict (no markdown) produces the no-content placeholder."""
        with mock.patch("firecrawl.FirecrawlApp") as App:
            App.return_value.scrape.return_value = {}
            result = self.plugin.import_content(
                "https://example.com", api_keys=FIRECRAWL_KEYS
            )

        assert "No content could be scraped" in result.full_text
        assert result.metadata["pages_crawled"] == 0


class TestMarkitdownNotInstalled:
    """The markitdown-fallback path when the SDK is unavailable."""

    def test_import_error_raises_runtime(self):
        """A missing markitdown package surfaces an install hint."""
        plugin = UrlImportPlugin()
        real_import = __import__

        def _no_md(name, *args, **kwargs):
            if name == "markitdown":
                raise ImportError("No module named 'markitdown'")
            return real_import(name, *args, **kwargs)

        with (
            mock.patch("builtins.__import__", side_effect=_no_md),
            pytest.raises(RuntimeError, match="markitdown is not installed"),
        ):
            plugin.import_content("https://example.com/p")


class TestSafeInt:
    """``_safe_int`` conversion helper."""

    def test_none_returns_default(self):
        """None yields the default."""
        assert _safe_int(None, 42) == 42

    def test_valid_int_string(self):
        """A numeric string is parsed."""
        assert _safe_int("10", 0) == 10

    def test_valid_int(self):
        """An int passes through."""
        assert _safe_int(25, 0) == 25

    def test_invalid_string_returns_default(self):
        """A non-numeric string yields the default."""
        assert _safe_int("abc", 99) == 99

    def test_float_string_returns_default(self):
        """A float-shaped string is not an int and yields the default."""
        assert _safe_int("3.14", 7) == 7


class TestGetParameters:
    """``get_parameters`` contract."""

    def test_parameter_names(self):
        """Exposes crawl knobs plus description/citation."""
        names = [p.name for p in UrlImportPlugin().get_parameters()]
        assert names == ["max_discovery_depth", "limit", "timeout", "description", "citation"]
