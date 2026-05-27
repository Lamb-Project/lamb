"""URL import plugin: Firecrawl when configured, markitdown fallback otherwise.

When a ``firecrawl_key`` is present in ``api_keys``, the plugin uses
Firecrawl to crawl the URL (and optionally its sub-pages) and convert the
result to Markdown. When no key is configured, it falls back to a direct
HTTP fetch + MarkItDown conversion of the single URL.
"""

import logging
import time
from typing import Any
from urllib.parse import urlparse

from plugins.base import (
    ImportResult,
    LibraryImportPlugin,
    PluginParameter,
    PluginRegistry,
)
from plugins.content_handlers.capability import Capability

logger = logging.getLogger(__name__)


@PluginRegistry.register
class UrlImportPlugin(LibraryImportPlugin):
    """Import web content from URLs.

    Uses Firecrawl for deep crawls when a key is configured; falls back to
    a direct MarkItDown fetch for single-page imports when no key is set.
    """

    name = "url_import"
    description = "Import web pages as Markdown (Firecrawl if configured, direct fetch otherwise)."
    supported_source_types = {"url"}
    required_keys: list[str] = []  # Firecrawl is optional; direct fetch is the fallback.
    # Firecrawl/markitdown produce markdown text only; no per-page or image
    # files are written by either backend.
    produces_capabilities = [Capability.TEXT]
    # URL-based plugin — no local file extension match.
    file_extensions: list[str] = []
    human_label = "Import a webpage URL"

    def import_content(
        self,
        source_path: str,
        *,
        api_keys: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> ImportResult:
        """Fetch a URL and return its content as structured Markdown.

        Args:
            source_path: The URL to import.
            api_keys: Optional ``firecrawl_key`` / ``firecrawl_url`` for
                Firecrawl-powered deep crawls.
            **kwargs: Plugin parameters (max_discovery_depth, limit, etc.).

        Returns:
            ImportResult with the page content.

        Raises:
            ValueError: If the URL is invalid.
            RuntimeError: If the import fails.
        """
        url = source_path
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        api_keys = api_keys or {}
        firecrawl_key = api_keys.get("firecrawl_key", "")

        if firecrawl_key:
            return self._import_via_firecrawl(url, firecrawl_key, api_keys, kwargs)
        return self._import_via_markitdown(url, kwargs)

    # ------------------------------------------------------------------
    # Firecrawl path (deep multi-page crawl)
    # ------------------------------------------------------------------

    def _import_via_firecrawl(
        self,
        url: str,
        api_key: str,
        api_keys: dict[str, str],
        kwargs: dict[str, Any],
    ) -> ImportResult:
        from firecrawl import FirecrawlApp  # noqa: PLC0415

        api_url = api_keys.get("firecrawl_url", "https://api.firecrawl.dev")
        max_depth = _safe_int(kwargs.get("max_discovery_depth"), 2)
        limit = _safe_int(kwargs.get("limit"), 100)
        crawl_domain = _safe_bool(kwargs.get("crawl_entire_domain"), True)
        timeout_s = _safe_int(kwargs.get("timeout"), 300)
        self.report_progress(kwargs, 0, 3, f"Crawling {url} via Firecrawl...")

        t0 = time.monotonic()
        try:
            from firecrawl.v2.types import ScrapeOptions  # noqa: PLC0415

            app = FirecrawlApp(api_key=api_key, api_url=api_url)
            crawl_result = app.crawl(
                url,
                limit=limit,
                max_discovery_depth=max_depth,
                crawl_entire_domain=crawl_domain,
                allow_external_links=False,
                scrape_options=ScrapeOptions(formats=["markdown"]),
                poll_interval=5,
                timeout=timeout_s,
            )
        except Exception as exc:
            raise RuntimeError(f"Firecrawl crawl failed for {url}: {exc}") from exc

        crawl_duration_ms = int((time.monotonic() - t0) * 1000)
        self.report_progress(kwargs, 1, 3, "Processing crawled pages...")

        pages_data = []
        if hasattr(crawl_result, "data"):
            pages_data = crawl_result.data or []
        elif isinstance(crawl_result, dict):
            pages_data = crawl_result.get("data", [])

        if not pages_data:
            logger.warning("Firecrawl returned no data for %s", url)
            return ImportResult(
                full_text=f"*(No content could be crawled from {url})*",
                metadata={"source_url": url, "pages_crawled": 0},
                source_ref={"type": "url", "source_url": url},
            )

        all_text_parts = []
        for doc in pages_data:
            page_md = ""
            page_url = ""
            page_title = ""

            if hasattr(doc, "markdown"):
                page_md = doc.markdown or ""
                meta = getattr(doc, "metadata", None)
                if meta is not None and not isinstance(meta, dict):
                    page_url = getattr(meta, "url", "") or getattr(meta, "source_url", "") or ""
                    page_title = getattr(meta, "title", "") or ""
                elif isinstance(meta, dict):
                    page_url = meta.get("sourceURL", "") or meta.get("source_url", "")
                    page_title = meta.get("title", "")
                page_url = page_url or getattr(doc, "url", "")
            elif isinstance(doc, dict):
                page_md = doc.get("markdown", "")
                page_url = doc.get("metadata", {}).get("sourceURL", "") or doc.get(
                    "metadata", {}
                ).get("source_url", "")
                page_title = doc.get("metadata", {}).get("title", "")

            if page_md.strip():
                header = f"## {page_title}\n\n" if page_title else ""
                source_note = f"*Source: {page_url}*\n\n" if page_url else ""
                all_text_parts.append(f"{header}{source_note}{page_md}")

        full_text = "\n\n---\n\n".join(all_text_parts)
        self.report_progress(kwargs, 2, 3, "Building metadata...")

        metadata = {
            "source_url": url,
            "pages_crawled": len(pages_data),
            "max_discovery_depth": max_depth,
            "crawl_entire_domain": crawl_domain,
            "character_count": len(full_text),
            "crawl_duration_ms": crawl_duration_ms,
            "import_plugin": self.name,
            "fetch_method": "firecrawl",
        }
        if kwargs.get("description"):
            metadata["description"] = kwargs["description"]
        if kwargs.get("citation"):
            metadata["citation"] = kwargs["citation"]

        source_ref = {
            "type": "url",
            "source_url": url,
            "crawled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pages_crawled": len(pages_data),
        }

        self.report_progress(kwargs, 3, 3, "Import complete.")
        return ImportResult(
            full_text=full_text, pages=[], images=[], metadata=metadata, source_ref=source_ref
        )

    # ------------------------------------------------------------------
    # Direct fetch path (single-page, no external service)
    # ------------------------------------------------------------------

    def _import_via_markitdown(self, url: str, kwargs: dict[str, Any]) -> ImportResult:
        """Fetch a single URL and convert it to Markdown via MarkItDown."""
        try:
            from markitdown import MarkItDown  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "markitdown is not installed. Install it with: pip install 'markitdown[all]'"
            ) from exc

        self.report_progress(kwargs, 0, 2, f"Fetching {url}...")
        t0 = time.monotonic()
        try:
            md = MarkItDown()
            result = md.convert(url)
            full_text = result.text_content or ""
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch and convert {url}: {exc}") from exc

        fetch_duration_ms = int((time.monotonic() - t0) * 1000)
        self.report_progress(kwargs, 1, 2, "Building metadata...")

        if not full_text.strip():
            logger.warning("No text content extracted from %s", url)
            full_text = f"*(No text content could be extracted from {url})*"

        metadata = {
            "source_url": url,
            "character_count": len(full_text),
            "fetch_duration_ms": fetch_duration_ms,
            "import_plugin": self.name,
            "fetch_method": "markitdown",
        }
        if kwargs.get("description"):
            metadata["description"] = kwargs["description"]
        if kwargs.get("citation"):
            metadata["citation"] = kwargs["citation"]

        source_ref = {
            "type": "url",
            "source_url": url,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        self.report_progress(kwargs, 2, 2, "Import complete.")
        return ImportResult(
            full_text=full_text, pages=[], images=[], metadata=metadata, source_ref=source_ref
        )

    def get_parameters(self) -> list[PluginParameter]:
        """Return configurable parameters for URL crawling.

        Returns:
            Parameter descriptors.
        """
        return [
            PluginParameter(
                name="max_discovery_depth",
                type="int",
                description="Maximum crawl depth from the start URL.",
                default=2,
                min_value=1,
                max_value=10,
            ),
            PluginParameter(
                name="limit",
                type="int",
                description="Maximum number of pages to crawl.",
                default=100,
                min_value=1,
                max_value=1000,
                advanced=True,
            ),
            PluginParameter(
                name="crawl_entire_domain",
                type="bool",
                description="Whether to follow links across the entire domain.",
                default=True,
            ),
            PluginParameter(
                name="timeout",
                type="int",
                description="Crawl job timeout in seconds.",
                default=300,
                advanced=True,
            ),
            PluginParameter(
                name="description",
                type="string",
                description="Optional description.",
                advanced=True,
            ),
            PluginParameter(
                name="citation",
                type="string",
                description="Optional citation reference.",
                advanced=True,
            ),
        ]


def _safe_int(value: Any, default: int) -> int:
    """Safely convert a value to int, returning default on failure.

    Args:
        value: Value to convert.
        default: Fallback value.

    Returns:
        Integer value.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_bool(value: Any, default: bool) -> bool:
    """Safely convert a value to bool, handling string "false"/"true".

    Args:
        value: Value to convert.
        default: Fallback value.

    Returns:
        Boolean value.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in ("false", "0", "no", "off")
    return bool(value)
