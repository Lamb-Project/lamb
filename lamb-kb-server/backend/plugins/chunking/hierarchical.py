"""Hierarchical (parent-child) chunking strategy for Markdown documents.

Splits the document into *parent* sections on H2/H3 headers
(``r'^(#{2,3})\\s+(.+)$'``).  Each parent section is then further split into
smaller *child* chunks suitable for dense semantic search.

Only child chunks are emitted.  Each child carries the full parent text in
``metadata["parent_text"]`` so the query layer can return the richer context
to the LLM while using the compact child embedding for retrieval — the classic
"parent-document retrieval" pattern.

All metadata values are primitives (str/int/float/bool/None) to satisfy
ChromaDB's constraint.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from plugins.base import Chunk, ChunkingRegistry, ChunkingStrategy, DocumentInput, PluginParameter
from plugins.chunking._common import build_base_metadata

logger = logging.getLogger(__name__)

# Matches H2 and H3 Markdown headers (## Title or ### Title)
_HEADER_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)


@ChunkingRegistry.register
class HierarchicalChunking(ChunkingStrategy):
    """Parent-child header-based chunking for markdown.

    Sections are delimited by H2/H3 headings.  Oversized sections are split
    with a secondary ``RecursiveCharacterTextSplitter``.  The preamble (text
    before the first heading) becomes parent chunk 0, labelled "Preamble".

    Metadata keys added beyond the base set:
    - ``parent_chunk_id`` — integer index of the parent section
    - ``child_chunk_id`` — integer index of the child within that parent
    - ``chunk_level`` — always ``"child"``
    - ``parent_text`` — full text of the parent section (used by vector
      backends for parent-document retrieval)
    - ``children_in_parent`` — how many children this parent produced
    - ``section_title`` — heading title of the parent section
    - ``section_part`` — which sub-split this chunk came from when a section
      was too large to fit in one parent chunk (only present when > 1)
    """

    name = "hierarchical"
    description = "Parent-child header-based chunking for markdown"

    def get_parameters(self) -> list[PluginParameter]:
        return [
            PluginParameter(
                "parent_chunk_size",
                "int",
                "Maximum characters in a parent section before secondary splitting",
                2000,
                min_value=200,
                max_value=16000,
            ),
            PluginParameter(
                "child_chunk_size",
                "int",
                "Maximum characters in each child chunk (used for embedding)",
                400,
                min_value=50,
                max_value=4000,
            ),
            PluginParameter(
                "child_chunk_overlap",
                "int",
                "Characters of overlap between adjacent child chunks",
                50,
                min_value=0,
                max_value=500,
            ),
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_sections(
        self,
        text: str,
        parent_chunk_size: int,
    ) -> list[dict[str, Any]]:
        """Return a flat list of parent-chunk dicts from *text*.

        Each dict has keys ``section_title`` (str), ``text`` (str), and
        optionally ``section_part`` (int, 1-based, only when a section was
        split because it exceeded *parent_chunk_size*).
        """
        matches = list(_HEADER_RE.finditer(text))

        # Collect raw sections: (title, body_text)
        raw_sections: list[tuple[str, str]] = []

        # Preamble — text before the first header
        if matches:
            preamble = text[: matches[0].start()].strip()
            if preamble:
                raw_sections.append(("Preamble", preamble))
        else:
            # No headers at all — treat entire document as one section
            raw_sections.append(("Document", text.strip()))

        for i, m in enumerate(matches):
            section_title = m.group(2).strip()
            body_start = m.start()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_body = text[body_start:body_end].strip()
            raw_sections.append((section_title, section_body))

        # Secondary splitting for oversized sections
        secondary_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""],
        )

        parent_chunks: list[dict[str, Any]] = []
        for title, body in raw_sections:
            if len(body) <= parent_chunk_size:
                parent_chunks.append({"section_title": title, "text": body})
            else:
                sub_chunks = secondary_splitter.split_text(body)
                for part_idx, sub in enumerate(sub_chunks):
                    entry: dict[str, Any] = {
                        "section_title": title,
                        "text": sub,
                    }
                    if len(sub_chunks) > 1:
                        entry["section_part"] = part_idx + 1
                    parent_chunks.append(entry)

        return parent_chunks

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chunk(
        self,
        document: DocumentInput,
        params: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Split *document* into child chunks with parent-text metadata.

        Args:
            document: Source document to split.
            params: Optional overrides for ``parent_chunk_size``,
                ``child_chunk_size``, and ``child_chunk_overlap``.

        Returns:
            List of child :class:`~plugins.base.Chunk` objects.  The list
            never contains parent chunks directly — only children.
        """
        params = params or {}
        parent_chunk_size: int = int(params.get("parent_chunk_size", 2000))
        child_chunk_size: int = int(params.get("child_chunk_size", 400))
        child_chunk_overlap: int = int(params.get("child_chunk_overlap", 50))

        chunking_params = {
            "parent_chunk_size": parent_chunk_size,
            "child_chunk_size": child_chunk_size,
            "child_chunk_overlap": child_chunk_overlap,
        }
        base_meta = build_base_metadata(document, "hierarchical", chunking_params)

        child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        parent_sections = self._extract_sections(document.text, parent_chunk_size)

        # First pass: collect all children so we know total chunk count
        all_children: list[dict[str, Any]] = []
        for parent_idx, parent in enumerate(parent_sections):
            parent_text = parent["text"]
            child_texts = child_splitter.split_text(parent_text)
            for child_idx, child_text in enumerate(child_texts):
                all_children.append(
                    {
                        "text": child_text,
                        "parent_text": parent_text,
                        "parent_chunk_id": parent_idx,
                        "child_chunk_id": child_idx,
                        "children_in_parent": len(child_texts),
                        "section_title": parent["section_title"],
                        "section_part": parent.get("section_part"),
                    }
                )

        total = len(all_children)

        chunks: list[Chunk] = []
        for entry in all_children:
            meta = dict(base_meta)
            meta["parent_chunk_id"] = entry["parent_chunk_id"]
            meta["child_chunk_id"] = entry["child_chunk_id"]
            meta["chunk_level"] = "child"
            meta["parent_text"] = entry["parent_text"]
            meta["children_in_parent"] = entry["children_in_parent"]
            meta["section_title"] = entry["section_title"]
            meta["chunk_count"] = total
            if entry["section_part"] is not None:
                meta["section_part"] = entry["section_part"]
            chunks.append(Chunk(text=entry["text"], metadata=meta))

        logger.debug(
            "HierarchicalChunking: %d parent sections → %d child chunks for '%s'",
            len(parent_sections),
            total,
            document.source_item_id,
        )
        return chunks
