"""Pages capability handler: returns per-page markdown for paginated items."""

from __future__ import annotations

import re
from pathlib import Path

from plugins.content_handlers.capability import (
    Capability,
    CapabilityPayload,
    CapabilityRegistry,
    ContentHandler,
    HandlerUnavailable,
)

# Matches ``page_001.md``, ``page_42.md`` etc. — the format written by
# ``content_service.write_structured_content``.
_PAGE_NUMBER_RE = re.compile(r"page[_-]?(\d+)", re.IGNORECASE)


def _extract_page_number(filename: str) -> int:
    """Return the page number embedded in a page filename.

    Falls back to ``0`` when no number is present so the file still appears
    in the listing (just at the top).
    """
    match = _PAGE_NUMBER_RE.search(filename)
    return int(match.group(1)) if match else 0


@CapabilityRegistry.register
class PagesHandler(ContentHandler):
    """Return per-page Markdown for paginated items (PDF, DOCX, PPTX)."""

    capability = Capability.PAGES
    description = "Per-page Markdown breakdown of the imported item."

    def get(self, item_path: Path) -> CapabilityPayload:
        """List ``content/pages/*.md`` in page-number order.

        Args:
            item_path: Path to the item directory.

        Returns:
            CapabilityPayload with ``mime="application/json"`` and ``body``
            shaped ``[{"page": int, "markdown": str}, ...]``.

        Raises:
            HandlerUnavailable: If the ``content/pages`` directory is
                missing or empty.
        """
        pages_dir = item_path / "content" / "pages"
        if not pages_dir.is_dir():
            raise HandlerUnavailable(
                f"Item at {item_path} has no content/pages directory"
            )

        page_files = sorted(
            (p for p in pages_dir.iterdir() if p.is_file() and p.suffix == ".md"),
            key=lambda p: (_extract_page_number(p.name), p.name),
        )
        if not page_files:
            raise HandlerUnavailable(
                f"Item at {item_path} has no page files"
            )

        pages = [
            {
                "page": _extract_page_number(p.name),
                "markdown": p.read_text(encoding="utf-8"),
            }
            for p in page_files
        ]

        return CapabilityPayload(mime="application/json", body=pages)
