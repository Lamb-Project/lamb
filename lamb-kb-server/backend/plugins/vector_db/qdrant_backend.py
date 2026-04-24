"""Qdrant vector store backend.

Supports two modes selected by environment configuration:

* **Local on-disk** (default): ``QdrantClient(path=storage_path)`` — no
  external service required.  Each collection lives in its own directory under
  ``storage_path``.
* **Remote** (when ``QDRANT_URL`` is set in env / :mod:`config`):
  ``QdrantClient(url=..., api_key=...)`` — ``storage_path`` is still created
  as an empty marker directory so storage accounting in the KB server DB
  remains consistent.

If ``qdrant_client`` is not installed this module raises ``ImportError`` at
import time and :func:`main._discover_plugins` silently skips registration.

Hierarchical parent-document retrieval is supported: if ``parent_text`` is
present in a point's payload the query layer returns that text instead of the
stored child text.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    from qdrant_client import QdrantClient, models
except ImportError:
    raise ImportError(
        "qdrant-client is not installed; "
        "the 'qdrant' vector DB plugin will not be available."
    )

import config

from plugins.base import (
    Chunk,
    EmbeddingFunction,
    QueryResult,
    VectorDBBackend,
    VectorDBRegistry,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100
# Internal payload key used to store the chunk's text alongside the vector
_TEXT_KEY = "_text"


def _make_client(storage_path: str) -> QdrantClient:
    """Create a Qdrant client in remote or local mode."""
    if config.QDRANT_URL:
        logger.debug("QdrantBackend: using remote client at %s", config.QDRANT_URL)
        return QdrantClient(
            url=config.QDRANT_URL,
            api_key=config.QDRANT_API_KEY or None,
        )
    logger.debug("QdrantBackend: using local on-disk client at %s", storage_path)
    return QdrantClient(path=storage_path)


def _ensure_marker_dir(storage_path: str) -> None:
    """Create the storage directory if it does not exist (remote-mode marker)."""
    Path(storage_path).mkdir(parents=True, exist_ok=True)


@VectorDBRegistry.register
class QdrantBackend(VectorDBBackend):
    """Qdrant vector store backend (local on-disk or remote).

    Vectors are stored with cosine distance.  Query scores are returned in
    ``[0, 1]`` via ``(raw_cosine_score + 1) / 2`` since Qdrant's cosine scores
    span ``[-1, 1]``.
    """

    name = "qdrant"
    description = "Qdrant vector store"

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
        """Create a Qdrant collection with cosine distance.

        The embedding dimension is detected by embedding a single probe string.
        This is necessary because Qdrant requires the vector size at collection
        creation time while ChromaDB deduces it lazily.

        Returns:
            ``collection_id`` (Qdrant uses name-based addressing).
        """
        _ensure_marker_dir(storage_path)
        client = _make_client(storage_path)

        # Detect embedding dimension by probing
        probe_vectors = embedding_function(["dimension probe"])
        embedding_dim = len(probe_vectors[0])

        client.create_collection(
            collection_name=collection_id,
            vectors_config=models.VectorParams(
                size=embedding_dim,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info(
            "Qdrant collection created: name=%s dim=%d", collection_id, embedding_dim
        )
        return collection_id

    def delete_collection(self, *, collection_id: str, storage_path: str) -> None:
        """Delete a Qdrant collection and clean up on-disk data.

        Swallows exceptions if the collection is already absent.
        """
        import shutil

        client = _make_client(storage_path)
        try:
            client.delete_collection(collection_name=collection_id)
            logger.info("Qdrant collection deleted: %s", collection_id)
        except Exception as exc:
            logger.warning(
                "Qdrant delete_collection '%s' failed (may already be absent): %s",
                collection_id,
                exc,
            )

        shutil.rmtree(storage_path, ignore_errors=True)
        logger.debug("Removed Qdrant storage directory: %s", storage_path)

    def add_chunks(
        self,
        *,
        collection_id: str,
        storage_path: str,
        chunks: list[Chunk],
        embedding_function: EmbeddingFunction,
    ) -> int:
        """Embed and upsert chunks in batches of 100.

        Each point's payload stores chunk metadata plus ``_text`` (the chunk
        text) so the text can be recovered during query without a separate
        document store.

        Returns:
            Number of chunks successfully stored.
        """
        if not chunks:
            return 0

        _ensure_marker_dir(storage_path)
        client = _make_client(storage_path)

        stored = 0
        for batch_start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[batch_start : batch_start + _BATCH_SIZE]
            texts = [c.text for c in batch]
            vectors = embedding_function(texts)

            points = [
                models.PointStruct(
                    id=uuid4().hex,
                    vector=vec,
                    payload={**chunk.metadata, _TEXT_KEY: chunk.text},
                )
                for chunk, vec in zip(batch, vectors)
            ]
            client.upsert(collection_name=collection_id, points=points)
            stored += len(batch)

        logger.debug(
            "Qdrant add_chunks: stored %d chunks in '%s'", stored, collection_id
        )
        return stored

    def delete_by_source(
        self,
        *,
        collection_id: str,
        storage_path: str,
        source_item_id: str,
    ) -> int:
        """Delete all vectors whose ``source_item_id`` payload matches.

        Returns:
            Count of vectors that were present before deletion.
        """
        _ensure_marker_dir(storage_path)
        client = _make_client(storage_path)

        # Count before deletion
        count_result = client.count(
            collection_name=collection_id,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_item_id",
                        match=models.MatchValue(value=source_item_id),
                    )
                ]
            ),
            exact=True,
        )
        count = count_result.count

        client.delete(
            collection_name=collection_id,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_item_id",
                            match=models.MatchValue(value=source_item_id),
                        )
                    ]
                )
            ),
        )
        logger.info(
            "Qdrant delete_by_source: deleted %d vectors for source '%s'",
            count,
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
        """Embed *query_text* and return the top-k most similar chunks.

        Qdrant cosine scores span ``[-1, 1]``; they are normalised to
        ``[0, 1]`` via ``(score + 1) / 2`` before being returned.

        For hierarchical chunks, ``parent_text`` in the payload is returned as
        the result text (parent-document retrieval pattern).

        Returns:
            List of :class:`~plugins.base.QueryResult`, best match first.
        """
        _ensure_marker_dir(storage_path)
        client = _make_client(storage_path)

        query_vectors = embedding_function([query_text])
        query_vector = query_vectors[0]

        hits = client.search(
            collection_name=collection_id,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )

        results: list[QueryResult] = []
        for hit in hits:
            payload: dict[str, Any] = dict(hit.payload or {})
            # Extract stored text and strip the internal key from metadata
            chunk_text: str = payload.pop(_TEXT_KEY, "")
            # Parent-document retrieval: prefer parent_text if present
            text = payload.pop("parent_text", None) or chunk_text
            # Normalise Qdrant cosine score from [-1,1] to [0,1]
            score = (float(hit.score) + 1.0) / 2.0
            results.append(QueryResult(text=text, score=score, metadata=payload))

        return results
