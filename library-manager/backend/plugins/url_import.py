"""URL import plugin using Firecrawl for web crawling.

Crawls a URL (and optionally its sub-pages) and converts the web content
to Markdown. Supports self-hosted Firecrawl or the public API.
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

logger = logging.getLogger(__name__)


@PluginRegistry.register
class UrlImportPlugin(LibraryImportPlugin):
    """Import web content from URLs via Firecrawl."""

    name = "url_import"
    description = "Import web pages as Markdown using Firecrawl."
    supported_source_types = {"url"}
    supported_file_types: set[str] = set()
    required_keys = ["firecrawl"]

    def import_content(
        self,
        source_path: str,
        *,
        api_keys: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> ImportResult:
        """Crawl a URL and return the content as structured Markdown.

        Args:
            source_path: The URL to crawl.
            api_keys: Must contain ``firecrawl_key`` and optionally
                ``firecrawl_url`` for self-hosted instances.
            **kwargs: Plugin parameters (max_discovery_depth, limit, etc.).

        Returns:
            ImportResult with the crawled content.

        Raises:
            ValueError: If the URL is invalid.
            RuntimeError: If crawling fails.
        """
        from firecrawl import FirecrawlApp  # noqa: PLC0415

        url = source_path
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        api_keys = api_keys or {}
        api_key = api_keys.get("firecrawl_key", "")
        api_url = api_keys.get("firecrawl_url", "https://api.firecrawl.dev")

        max_depth = _safe_int(kwargs.get("max_discovery_depth"), 2)
        limit = _safe_int(kwargs.get("limit"), 100)
        crawl_domain = _safe_bool(kwargs.get("crawl_entire_domain"), True)
        self.report_progress(kwargs, 0, 3, f"Crawling {url}...")

        t0 = time.monotonic()
        try:
            app = FirecrawlApp(api_key=api_key, api_url=api_url)
            crawl_params = {
                "limit": limit,
                "maxDepth": max_depth,
                "scrapeOptions": {"formats": ["markdown"]},
            }
            if not crawl_domain:
                crawl_params["allowExternalLinks"] = False

            crawl_result = app.crawl_url(url, params=crawl_params, poll_interval=5)
        except Exception as exc:
            raise RuntimeError(f"Firecrawl crawl failed for {url}: {exc}") from exc

        crawl_duration_ms = int((time.monotonic() - t0) * 1000)

        self.report_progress(kwargs, 1, 3, "Processing crawled pages...")

        # Firecrawl returns a result object with a 'data' list.
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
                page_url = getattr(doc, "url", "") or (
                    getattr(doc, "metadata", {}) or {}
                ).get("sourceURL", "")
                page_title = (getattr(doc, "metadata", {}) or {}).get("title", "")
            elif isinstance(doc, dict):
                page_md = doc.get("markdown", "")
                page_url = doc.get("metadata", {}).get("sourceURL", "")
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
            full_text=full_text,
            pages=[],
            images=[],
            metadata=metadata,
            source_ref=source_ref,
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
