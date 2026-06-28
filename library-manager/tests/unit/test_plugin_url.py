"""Unit tests for ``UrlImportPlugin`` with HTTP backends mocked at the boundary.

``firecrawl.FirecrawlApp`` and ``markitdown.MarkItDown`` are replaced via the
``patch_firecrawl`` / ``patch_markitdown`` context managers so the plugin's URL
validation, SSRF blocklist, backend-selection branch, metadata building, and
error humanisation all run for real with no network access.
"""

from __future__ import annotations

import socket
from unittest import mock

import pytest
from _fakes import patch_firecrawl, patch_markitdown
from plugins.base import ImportResult
from plugins.url_import import (
    UrlImportPlugin,
    _guard_ssrf,
    _is_blocked_ip,
    _safe_int,
)

FIRECRAWL_KEYS = {"firecrawl_key": "fc-test"}


def _addrinfo(*ips: str):
    """Build a ``socket.getaddrinfo`` return value for the given IP strings."""
    entries = []
    for ip in ips:
        if ":" in ip:
            entries.append((socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, 0, 0, 0)))
        else:
            entries.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)))
    return entries


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


class TestSsrfIpClassification:
    """``_is_blocked_ip`` — the address-range classifier behind the guard."""

    @pytest.mark.parametrize(
        "ip",
        [
            "10.0.0.1",  # 10/8 private
            "10.255.255.255",
            "172.16.0.1",  # 172.16/12 private
            "172.31.255.255",
            "192.168.1.1",  # 192.168/16 private
            "127.0.0.1",  # loopback
            "127.5.5.5",
            "169.254.169.254",  # link-local incl. cloud metadata
            "169.254.0.1",
            "0.0.0.0",  # unspecified / 0/8
            "0.1.2.3",
            "224.0.0.1",  # multicast
            "240.0.0.1",  # reserved
            "::1",  # IPv6 loopback
            "fc00::1",  # IPv6 ULA
            "fd12:3456::1",
            "fe80::1",  # IPv6 link-local
            "::ffff:10.0.0.1",  # IPv4-mapped private
            "::ffff:169.254.169.254",  # IPv4-mapped metadata
        ],
    )
    def test_internal_addresses_blocked(self, ip):
        """Every private/reserved/internal address is classified as blocked."""
        import ipaddress

        assert _is_blocked_ip(ipaddress.ip_address(ip)) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "93.184.216.34",  # example.com (public)
            "8.8.8.8",  # public DNS
            "172.15.255.255",  # just below the 172.16/12 private block
            "172.32.0.1",  # just above the 172.16/12 private block
            "2606:2800:220:1:248:1893:25c8:1946",  # public IPv6
        ],
    )
    def test_public_addresses_allowed(self, ip):
        """Genuinely public addresses are not blocked."""
        import ipaddress

        assert _is_blocked_ip(ipaddress.ip_address(ip)) is False

    def test_ipv4_mapped_recheck_blocks_when_outer_properties_clean(self):
        """IPv4-mapped unwrap blocks even if the IPv6 properties read clean.

        On Python < 3.13 an IPv4-mapped address's ``is_private`` does not
        reflect the embedded IPv4 address, so the guard must unwrap and
        re-classify. This stub forces that path: all outer ``is_*`` flags are
        False, but ``ipv4_mapped`` is a private address.
        """

        class _FakeMapped:
            is_private = is_loopback = is_link_local = False
            is_reserved = is_multicast = is_unspecified = False
            import ipaddress as _ip

            ipv4_mapped = _ip.ip_address("10.0.0.1")

        assert _is_blocked_ip(_FakeMapped()) is True


class TestSsrfGuardResolution:
    """``_guard_ssrf`` — denylist + DNS-resolution-based blocking."""

    def test_empty_host_raises(self):
        """A blank hostname is rejected."""
        with pytest.raises(ValueError, match="host is missing"):
            _guard_ssrf("")

    def test_denylisted_hostname_rejected_without_dns(self):
        """A denylisted name is rejected before any resolution occurs."""
        with (
            mock.patch("socket.getaddrinfo", side_effect=AssertionError("no DNS")),
            pytest.raises(ValueError, match="not allowed"),
        ):
            _guard_ssrf("metadata.google.internal")

    def test_literal_private_ip_rejected_without_dns(self):
        """A literal private IP is classified directly, never resolved."""
        with (
            mock.patch("socket.getaddrinfo", side_effect=AssertionError("no DNS")),
            pytest.raises(ValueError, match="blocked address"),
        ):
            _guard_ssrf("192.168.1.10")

    def test_literal_public_ip_allowed_without_dns(self):
        """A literal public IP passes without a DNS lookup."""
        with mock.patch("socket.getaddrinfo", side_effect=AssertionError("no DNS")):
            _guard_ssrf("93.184.216.34")  # does not raise

    def test_hostname_resolving_to_private_ip_rejected(self):
        """A public-looking host that resolves to a private IP is blocked."""
        with (
            mock.patch("socket.getaddrinfo", return_value=_addrinfo("10.1.2.3")),
            pytest.raises(ValueError, match="resolves to a blocked address"),
        ):
            _guard_ssrf("evil.example.com")

    def test_hostname_resolving_to_public_ip_allowed(self):
        """A host resolving to a public IP passes."""
        with mock.patch("socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            _guard_ssrf("good.example.com")  # does not raise

    def test_any_private_in_mixed_resolution_blocks(self):
        """If ANY resolved address is internal, the host is blocked."""
        with (
            mock.patch(
                "socket.getaddrinfo",
                return_value=_addrinfo("93.184.216.34", "169.254.169.254"),
            ),
            pytest.raises(ValueError, match="resolves to a blocked address"),
        ):
            _guard_ssrf("dns-rebind.example.com")

    def test_resolution_failure_raises(self):
        """A DNS failure is surfaced as a clear ValueError, not a crash."""
        with (
            mock.patch("socket.getaddrinfo", side_effect=OSError("nxdomain")),
            pytest.raises(ValueError, match="Could not resolve"),
        ):
            _guard_ssrf("does-not-exist.invalid")

    def test_unparseable_resolved_address_skipped(self):
        """A non-IP sockaddr entry is skipped rather than crashing the guard."""
        bogus = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("not-an-ip", 0))]
        with mock.patch("socket.getaddrinfo", return_value=bogus):
            _guard_ssrf("weird.example.com")  # no raise: nothing classifiable


class TestSsrfGuardIntegration:
    """The guard is enforced through ``import_content`` on both fetch paths."""

    def setup_method(self):
        """Fresh plugin per test."""
        self.plugin = UrlImportPlugin()

    def test_markitdown_path_blocked_before_fetch(self):
        """A host resolving to a private IP is rejected on the direct path.

        MarkItDown is patched to fail loudly so the test proves the guard
        fires *before* any conversion/network call.
        """
        with (
            mock.patch("socket.getaddrinfo", return_value=_addrinfo("10.0.0.5")),
            patch_markitdown(raises=AssertionError("must not fetch")),
            pytest.raises(ValueError, match="blocked address"),
        ):
            self.plugin.import_content("https://internal.example.com/x")

    def test_firecrawl_path_blocked_before_fetch(self):
        """A host resolving to a private IP is rejected on the Firecrawl path."""
        with (
            mock.patch("socket.getaddrinfo", return_value=_addrinfo("172.16.5.5")),
            patch_firecrawl(raises=AssertionError("must not scrape")),
            pytest.raises(ValueError, match="blocked address"),
        ):
            self.plugin.import_content(
                "https://internal.example.com/x", api_keys=FIRECRAWL_KEYS
            )


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
