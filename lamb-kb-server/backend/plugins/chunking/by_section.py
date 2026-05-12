"""Section-level chunking strategy for Markdown documents.

Splits the document on a configurable heading level (default H2).  Each chunk
covers one or more sibling headings at the target level, prefixed with the
parent heading titles for context (titles only, not body text).

If no headings at the target level exist, the strategy falls back to
:class:`~plugins.chunking.simple.SimpleChunking`.

All metadata values are primitives (str/int/float/bool/None) as required by
ChromaDB.  ``section_titles`` is encoded as a pipe-separated string and
``parent_path`` is ``">"``-joined heading titles.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

from plugins.base import Chunk, ChunkingRegistry, ChunkingStrategy, DocumentInput, PluginParameter
from plugins.chunking._common import build_base_metadata, encode_list

logger = logging.getLogger(__name__)

# Matches any H1-H6 Markdown heading
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@ChunkingRegistry.register
class BySectionChunking(ChunkingStrategy):
    """Split on markdown headings at a configurable depth.

    The document is parsed into a tree of headings.  Nodes at ``split_on_heading``
    level become chunk boundaries.  Parent heading *titles* (not their body
    text) are prepended as context so the LLM knows where in the hierarchy a
    chunk lives.

    Metadata keys added beyond the base set:
    - ``section_titles`` — pipe-encoded list of section titles in the chunk
      (ChromaDB requires primitives; decode by splitting on ``"|"``)
    - ``section_count`` — number of sections merged into this chunk
    - ``parent_path`` — ``">"``-joined ancestor heading titles
    - ``chunk_index`` / ``chunk_count`` — position in the output list
    """

    name = "by_section"
    description = "Split on markdown headings"

    def get_parameters(self) -> list[PluginParameter]:
        return [
            PluginParameter(
                "split_on_heading",
                "int",
                "Heading level to split on (1=H1 … 6=H6)",
                2,
                min_value=1,
                max_value=6,
            ),
            PluginParameter(
                "headings_per_chunk",
                "int",
                "Number of sibling headings merged into one chunk",
                1,
                min_value=1,
                max_value=10,
            ),
        ]

    # ------------------------------------------------------------------
    # Internal: document tree
    # ------------------------------------------------------------------

    def _parse_tree(self, text: str) -> dict[str, Any]:
        """Parse *text* into a heading tree.

        Returns a root node dict::

            {
                "level": 0,
                "title": "",
                "body_lines": [...],
                "children": [...],
                "parent": None,
            }
        """
        root: dict[str, Any] = {
            "level": 0,
            "title": "",
            "body_lines": [],
            "children": [],
            "parent": None,
        }
        current = root

        for line in text.split("\n"):
            m = _HEADING_RE.match(line)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()

                # Walk up to find the correct parent
                while current["level"] >= level and current["parent"] is not None:
                    current = current["parent"]

                node: dict[str, Any] = {
                    "level": level,
                    "title": title,
                    "body_lines": [],
                    "children": [],
                    "parent": current,
                }
                current["children"].append(node)
                current = node
            else:
                current["body_lines"].append(line)

        return root

    def _collect_at_level(
        self,
        node: dict[str, Any],
        target_level: int,
        parent_path: list[str],
    ) -> list[dict[str, Any]]:
        """Return all nodes at *target_level* with their ancestor path."""
        results: list[dict[str, Any]] = []

        current_path = (
            parent_path + [node["title"]] if node["level"] > 0 else parent_path
        )

        if node["level"] == target_level:
            results.append({"node": node, "parent_path": parent_path})
            # Do NOT recurse into children of a target-level node — their
            # body is included in the target node's text.
            return results

        for child in node["children"]:
            results.extend(self._collect_at_level(child, target_level, current_path))

        return results

    def _node_to_text(self, node: dict[str, Any]) -> str:
        """Convert a node (heading + body + descendant subtree) to markdown."""
        hashes = "#" * node["level"]
        lines = [f"{hashes} {node['title']}"]
        lines.extend(node["body_lines"])
        for child in node["children"]:
            lines.append(self._node_to_text(child))
        return "\n".join(lines).strip()

    def _parent_prefix(self, ancestor_titles: list[str]) -> str:
        """Build a heading prefix string from ancestor titles."""
        if not ancestor_titles:
            return ""
        lines: list[str] = []
        for lvl, title in enumerate(ancestor_titles, start=1):
            lines.append(f"{'#' * lvl} {title}")
        return "\n".join(lines) + "\n\n"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chunk(
        self,
        document: DocumentInput,
        params: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Split *document* on headings at the configured level.

        Args:
            document: Source document to split.
            params: Optional overrides for ``split_on_heading`` and
                ``headings_per_chunk``.

        Returns:
            List of section-aligned :class:`~plugins.base.Chunk` objects.
        """
        params = params or {}
        split_on_heading: int = int(params.get("split_on_heading", 2))
        headings_per_chunk: int = int(params.get("headings_per_chunk", 1))

        chunking_params = {
            "split_on_heading": split_on_heading,
            "headings_per_chunk": headings_per_chunk,
        }
        base_meta = build_base_metadata(document, "by_section", chunking_params)

        root = self._parse_tree(document.text)
        target_nodes = self._collect_at_level(root, split_on_heading, [])

        if not target_nodes:
            logger.warning(
                "BySectionChunking: no H%d headings in '%s', falling back to SimpleChunking",
                split_on_heading,
                document.source_item_id,
            )
            from plugins.chunking.simple import SimpleChunking  # lazy import

            fallback = SimpleChunking()
            fallback_allowed = {p.name for p in fallback.get_parameters()}
            fallback_params = {k: v for k, v in (params or {}).items() if k in fallback_allowed}
            return fallback.chunk(document, fallback_params)

        # Group by parent path key — sections from different parents are never mixed
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in target_nodes:
            key = " > ".join(item["parent_path"])
            groups[key].append(item)

        # Build output chunks, respecting headings_per_chunk
        raw_chunks: list[dict[str, Any]] = []
        for _parent_key, items in groups.items():
            for i in range(0, len(items), headings_per_chunk):
                batch = items[i : i + headings_per_chunk]
                first = batch[0]
                ancestor_titles = first["parent_path"]
                prefix = self._parent_prefix(ancestor_titles)
                section_texts = [self._node_to_text(item["node"]) for item in batch]
                merged_text = prefix + "\n\n".join(section_texts)
                titles = [item["node"]["title"] for item in batch]
                parent_path_str = " > ".join(ancestor_titles) if ancestor_titles else ""
                raw_chunks.append(
                    {
                        "text": merged_text,
                        "section_titles": titles,
                        "section_count": len(batch),
                        "parent_path": parent_path_str,
                    }
                )

        total = len(raw_chunks)
        chunks: list[Chunk] = []
        for idx, rc in enumerate(raw_chunks):
            meta = dict(base_meta)
            # section_titles encoded as pipe-separated string (ChromaDB cannot
            # store list values in metadata — split on "|" to decode)
            meta["section_titles"] = encode_list(rc["section_titles"])
            meta["section_count"] = rc["section_count"]
            meta["parent_path"] = rc["parent_path"]
            meta["chunk_index"] = idx
            meta["chunk_count"] = total
            chunks.append(Chunk(text=rc["text"], metadata=meta))

        logger.debug(
            "BySectionChunking (H%d): %d chunks from '%s'",
            split_on_heading,
            total,
            document.source_item_id,
        )
        return chunks
