"""ChromaDB persistent vector store backend.

Each collection is backed by a dedicated on-disk ``PersistentClient`` rooted
at ``storage_path``.  Clients are cached in a module-level dict keyed by
path so that multiple calls within one server process share a single client
and avoid re-opening the database.

Hierarchical parent-document retrieval is supported transparently: if a chunk's
metadata contains ``parent_text``, ``query()`` returns the parent text instead
of the child text so the LLM receives richer context.
"""

from __future__ import annotations

import logging
import shutil
from typing import Any
from uuid import uuid4

import chromadb
from chromadb.api.types import EmbeddingFunction as ChromaEmbeddingFunction
from chromadb.config import Settings as ChromaSettings

from plugins.base import (
    Chunk,
    EmbeddingFunction,
    QueryResult,
    VectorDBBackend,
    VectorDBRegistry,
)

logger = logging.getLogger(__name__)

# Module-level client cache: storage_path (str) → PersistentClient
_clients: dict[str, chromadb.PersistentClient] = {}

_BATCH_SIZE = 100


def _get_client(storage_path: str) -> chromadb.PersistentClient:
    """Return a cached ``PersistentClient`` for *storage_path*."""
    if storage_path not in _clients:
        logger.debug("Creating ChromaDB PersistentClient at %s", storage_path)
        _clients[storage_path] = chromadb.PersistentClient(
            path=storage_path,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
    return _clients[storage_path]


def _to_chroma_ef(ef: EmbeddingFunction) -> ChromaEmbeddingFunction:
    """Return a ChromaDB-compatible embedding function.

    ChromaDB 1.5+ requires the embedding function to expose a ``name()``
    method (not an attribute). Our plugin base uses ``name`` as a class
    attribute because it doubles as the registry key, so we either:

    * unwrap an underlying chromadb-native ``_fn`` if the plugin wraps one
      (``OpenAIEmbedding``, ``OllamaEmbedding``), or
    * build a thin adapter that forwards ``__call__`` to our plugin.

    The adapter path is used for plugins that produce embeddings directly
    (e.g. ``LocalEmbedding`` via sentence-transformers).
    """
    native = getattr(ef, "_fn", None)
    if isinstance(native, ChromaEmbeddingFunction):
        return native

    plugin_name = getattr(ef.__class__, "name", "custom") or "custom"

    class _Adapter(ChromaEmbeddingFunction):  # type: ignore[misc]
        @staticmethod
        def name() -> str:  # noqa: D401
            return plugin_name

        def __call__(self, input):  # noqa: D401
            return ef(input)

    return _Adapter()


@VectorDBRegistry.register
class ChromaDBBackend(VectorDBBackend):
    """ChromaDB persistent client backend.

    Collections use cosine distance (``hnsw:space=cosine``) so query scores are
    in ``[0, 1]`` where 1 is an exact match.  Scores are computed as
    ``1 - distance`` because ChromaDB reports distances, not similarities.
    """

    name = "chromadb"
    description = "ChromaDB persistent client"

    # ------------------------------------------------------------------
    # VectorDBBackend interface
    # ------------------------------------------------------------------

    def create_collection(
        self,
        *,
        collection_id: str,
        storage_path: str,
        embedding_function: EmbeddingFunction,
    ) -> str:
        """Create a new cosine-distance collection.

        Args:
            collection_id: Used as the ChromaDB collection name.
            storage_path: Filesystem directory for persistent data.
            embedding_function: Vendor embedding function attached to the
                collection (ChromaDB uses it for auto-embedding queries).

        Returns:
            The ChromaDB-assigned UUID as a string.
        """
        client = _get_client(storage_path)
        collection = client.create_collection(
            name=collection_id,
            metadata={"hnsw:space": "cosine"},
            embedding_function=_to_chroma_ef(embedding_function),  # type: ignore[arg-type]
        )
        logger.info(
            "ChromaDB collection created: name=%s id=%s", collection_id, collection.id
        )
        return str(collection.id)

    def delete_collection(self, *, collection_id: str, storage_path: str) -> None:
        """Delete a collection and remove all on-disk data.

        Swallows ``ValueError`` and ``InvalidCollectionException`` if the
        collection is already gone (idempotent).  Then removes the storage
        directory entirely.
        """
        client = _get_client(storage_path)
        try:
            client.delete_collection(name=collection_id)
            logger.info("ChromaDB collection deleted: %s", collection_id)
        except (ValueError, chromadb.errors.NotFoundError):
            logger.warning(
                "ChromaDB delete_collection: '%s' already absent, skipping",
                collection_id,
            )

        # Evict the cached client before removing its directory
        _clients.pop(storage_path, None)
        shutil.rmtree(storage_path, ignore_errors=True)
        logger.debug("Removed storage directory: %s", storage_path)

    def add_chunks(
        self,
        *,
        collection_id: str,
        storage_path: str,
        chunks: list[Chunk],
        embedding_function: EmbeddingFunction,
    ) -> int:
        """Embed and store chunks in batches of 100.

        Args:
            collection_id: Target collection name.
            storage_path: Filesystem directory for the persistent client.
            chunks: Chunks to store; metadata values must be primitives.
            embedding_function: Vendor embedding function used for embedding.

        Returns:
            Number of chunks successfully stored.
        """
        if not chunks:
            return 0

        client = _get_client(storage_path)
        collection = client.get_collection(
            name=collection_id,
            embedding_function=_to_chroma_ef(embedding_function),  # type: ignore[arg-type]
        )

        stored = 0
        for batch_start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[batch_start : batch_start + _BATCH_SIZE]
            collection.add(
                ids=[uuid4().hex for _ in batch],
                documents=[c.text for c in batch],
                metadatas=[c.metadata for c in batch],
            )
            stored += len(batch)

        logger.debug(
            "ChromaDB add_chunks: stored %d chunks in '%s'", stored, collection_id
        )
        return stored

    def delete_by_source(
        self,
        *,
        collection_id: str,
        storage_path: str,
        source_item_id: str,
    ) -> int:
        """Delete all vectors whose ``source_item_id`` metadata matches.

        Returns:
            The number of vectors deleted (count before deletion).
        """
        client = _get_client(storage_path)
        collection = client.get_collection(name=collection_id)

        # Count matching records first
        result = collection.get(
            where={"source_item_id": source_item_id},
            include=[],
        )
        count = len(result.get("ids", []))

        if count:
            collection.delete(where={"source_item_id": source_item_id})
            logger.info(
                "ChromaDB delete_by_source: deleted %d vectors for source '%s'",
                count,
                source_item_id,
            )
        else:
            logger.debug(
                "ChromaDB delete_by_source: no vectors found for source '%s'",
                source_item_id,
            )

        return count

    def query(
        self,
        *,
        collection_id: str,
        storage_path: str,
        query_text: str,
        top_k: int,
        embedding_function: EmbeddingFunction,
    ) -> list[QueryResult]:
        """Embed *query_text* and return top-k similar chunks.

        For chunks produced by the hierarchical strategy, ``metadata`` contains
        ``parent_text``.  In that case the *parent* text is returned as the
        result text so the LLM sees the richer context, while the child
        embedding was used for precision retrieval.

        Returns:
            List of :class:`~plugins.base.QueryResult` objects sorted by
            descending score (best match first).
        """
        client = _get_client(storage_path)
        collection = client.get_collection(
            name=collection_id,
            embedding_function=_to_chroma_ef(embedding_function),  # type: ignore[arg-type]
        )

        raw = collection.query(
            query_texts=[query_text],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        results: list[QueryResult] = []
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            meta_dict: dict[str, Any] = dict(meta) if meta else {}
            # For hierarchical retrieval: return parent context if available
            text = meta_dict.pop("parent_text", None) or doc
            score = max(0.0, min(1.0, 1.0 - float(dist)))
            results.append(QueryResult(text=text, score=score, metadata=meta_dict))

        return results
