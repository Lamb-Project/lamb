"""Simple recursive character-based chunking strategy.

Splits documents using LangChain's ``RecursiveCharacterTextSplitter``, which
tries progressively smaller separators (double-newline → newline → space →
empty string) so chunks respect natural paragraph and sentence boundaries.

This is the default strategy — suitable for plain text and markdown where
document structure is not important for retrieval.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from plugins.base import Chunk, ChunkingRegistry, ChunkingStrategy, DocumentInput, PluginParameter
from plugins.chunking._common import build_base_metadata

logger = logging.getLogger(__name__)


@ChunkingRegistry.register
class SimpleChunking(ChunkingStrategy):
    """Recursive character text splitting with configurable size and overlap.

    Every chunk receives ``chunk_index`` and ``chunk_count`` metadata in
    addition to the standard LAMB fields from :func:`build_base_metadata`.
    All metadata values are primitives (str/int/float/bool/None) as required
    by ChromaDB.
    """

    name = "simple"
    description = "Recursive character text splitting"

    def get_parameters(self) -> list[PluginParameter]:
        return [
            PluginParameter(
                "chunk_size",
                "int",
                "Maximum characters per chunk",
                1000,
                min_value=50,
                max_value=8000,
            ),
            PluginParameter(
                "chunk_overlap",
                "int",
                "Characters of overlap between adjacent chunks",
                200,
                min_value=0,
                max_value=2000,
            ),
        ]

    def chunk(
        self,
        document: DocumentInput,
        params: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Split *document* into overlapping character chunks.

        Args:
            document: Source document to split.
            params: Optional overrides for ``chunk_size`` and
                ``chunk_overlap``.

        Returns:
            List of :class:`~plugins.base.Chunk` objects with metadata.
        """
        params = params or {}
        chunk_size: int = int(params.get("chunk_size", 1000))
        chunk_overlap: int = int(params.get("chunk_overlap", 200))

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )

        texts = splitter.split_text(document.text)
        chunk_count = len(texts)

        chunking_params = {"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
        base_meta = build_base_metadata(document, "simple", chunking_params)

        chunks: list[Chunk] = []
        for idx, text in enumerate(texts):
            meta = dict(base_meta)
            meta["chunk_index"] = idx
            meta["chunk_count"] = chunk_count
            chunks.append(Chunk(text=text, metadata=meta))

        logger.debug(
            "SimpleChunking produced %d chunks from '%s'",
            chunk_count,
            document.source_item_id,
        )
        return chunks
