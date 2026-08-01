"""Page-boundary-preserving chunking strategy.

Chunks map directly to document pages so that retrieved text can be cited by
page number.  The strategy has three data sources, tried in order:

1. ``document.pages`` — pre-split page list supplied by LAMB (e.g. from the
   Library Manager's per-page content).  Each element is a dict with at least
   ``"page_number"`` (int) and ``"text"`` (str).
2. ``<!-- Page N -->`` markers embedded in ``document.text`` by the Library
   Manager's PDF import pipeline.
3. Fall back to :class:`~plugins.chunking.simple.SimpleChunking` when neither
   source is available (no page information in the document).

``pages_per_chunk`` pages may be merged into a single chunk, which is useful
for dense documents where individual pages are too short.

All metadata values are primitives (str/int/float/bool/None) as required by
ChromaDB.  ``page_numbers`` is encoded as a pipe-separated string.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from plugins.base import Chunk, ChunkingRegistry, ChunkingStrategy, DocumentInput, PluginParameter
from plugins.chunking._common import build_base_metadata, encode_list

logger = logging.getLogger(__name__)

# Matches <!-- Page N --> markers (case-insensitive, any whitespace)
_PAGE_MARKER_RE = re.compile(r"<!--\s*[Pp]age\s+(\d+)\s*-->")


@ChunkingRegistry.register
class ByPageChunking(ChunkingStrategy):
    """Preserve page boundaries — one chunk per page (or N pages merged).

    Metadata keys added beyond the base set:
    - ``page_range`` — human-readable range, e.g. ``"1"`` or ``"1-3"``
    - ``page_numbers`` — pipe-encoded list of page numbers, e.g. ``"1|2|3"``
      (encoded as a string because ChromaDB does not accept list metadata values)
    - ``chunk_index`` — zero-based position in the output list
    - ``chunk_count`` — total number of chunks produced
    """

    name = "by_page"
    description = "Preserve page boundaries"

    def get_parameters(self) -> list[PluginParameter]:
        return [
            PluginParameter(
                "pages_per_chunk",
                "int",
                "Number of pages to merge into one chunk",
                1,
                min_value=1,
                max_value=20,
            ),
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pages_from_structured(
        self, pages: list[dict[str, Any]]
    ) -> list[tuple[int, str]]:
        """Convert ``document.pages`` list to ``(page_number, text)`` pairs."""
        result: list[tuple[int, str]] = []
        for p in pages:
            num = int(p.get("page_number", len(result) + 1))
            text = str(p.get("text", "")).strip()
            if text:
                result.append((num, text))
        return result

    def _pages_from_markers(self, text: str) -> list[tuple[int, str]] | None:
        """Split *text* on ``<!-- Page N -->`` markers.

        Returns ``None`` if no markers are found (caller falls back to simple
        chunking).
        """
        parts = _PAGE_MARKER_RE.split(text)
        # split() with a capturing group alternates: [pre, N, body, N, body …]
        if len(parts) <= 1:
            return None

        pages: list[tuple[int, str]] = []

        # Anything before the first marker is discarded (usually empty)
        # parts[0] = pre-marker text (skip)
        # parts[1] = "1", parts[2] = body, parts[3] = "2", …
        i = 1
        while i + 1 < len(parts):
            page_num = int(parts[i])
            body = parts[i + 1].strip()
            if body:
                pages.append((page_num, body))
            i += 2

        return pages if pages else None

    def _build_chunks(
        self,
        pages: list[tuple[int, str]],
        pages_per_chunk: int,
        base_meta: dict[str, Any],
        permalink_pages: list[str],
    ) -> list[Chunk]:
        """Merge pages into groups and produce Chunk objects."""
        chunks: list[Chunk] = []

        for group_start in range(0, len(pages), pages_per_chunk):
            group = pages[group_start : group_start + pages_per_chunk]
            combined_text = "\n\n".join(text for _, text in group)
            page_nums = [num for num, _ in group]

            first_page = page_nums[0]
            last_page = page_nums[-1]
            page_range = (
                str(first_page) if first_page == last_page else f"{first_page}-{last_page}"
            )

            meta = dict(base_meta)
            meta["page_range"] = page_range
            # ChromaDB requires primitive metadata values — encode the list as
            # a pipe-separated string.  Decoders split on "|" to recover ints.
            meta["page_numbers"] = encode_list(page_nums)
            meta["chunk_index"] = len(chunks)

            # Attach the matching page permalink if available (first page of group)
            if permalink_pages:
                page_idx = first_page - 1  # pages are 1-based
                if 0 <= page_idx < len(permalink_pages):
                    meta["permalink_page"] = permalink_pages[page_idx]

            chunks.append(Chunk(text=combined_text, metadata=meta))

        # Backfill chunk_count now that we know it
        total = len(chunks)
        for c in chunks:
            c.metadata["chunk_count"] = total

        return chunks

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chunk(
        self,
        document: DocumentInput,
        params: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Split *document* into page chunks.

        Args:
            document: Source document; may carry pre-split ``pages`` or
                ``<!-- Page N -->`` markers embedded in ``text``.
            params: Optional override for ``pages_per_chunk``.

        Returns:
            List of page-aligned :class:`~plugins.base.Chunk` objects.
        """
        params = params or {}
        pages_per_chunk: int = int(params.get("pages_per_chunk", 1))

        chunking_params = {"pages_per_chunk": pages_per_chunk}
        base_meta = build_base_metadata(document, "by_page", chunking_params)

        permalink_pages: list[str] = (document.permalinks or {}).get("pages") or []

        # --- Source 1: structured pages list from LAMB ---
        if document.pages:
            pages = self._pages_from_structured(document.pages)
            if pages:
                logger.debug(
                    "ByPageChunking: using %d structured pages from document.pages",
                    len(pages),
                )
                return self._build_chunks(pages, pages_per_chunk, base_meta, permalink_pages)

        # --- Source 2: <!-- Page N --> markers in document.text ---
        pages = self._pages_from_markers(document.text)
        if pages is not None:
            logger.debug(
                "ByPageChunking: using %d pages from <!-- Page N --> markers",
                len(pages),
            )
            return self._build_chunks(pages, pages_per_chunk, base_meta, permalink_pages)

        # --- Source 3: fall back to SimpleChunking ---
        logger.warning(
            "ByPageChunking: no page information found in '%s', falling back to SimpleChunking",
            document.source_item_id,
        )
        from plugins.chunking.simple import SimpleChunking  # lazy import, avoid cycle

        fallback = SimpleChunking()
        fallback_params = {"chunk_size": 1000, "chunk_overlap": 200}
        return fallback.chunk(document, fallback_params)
