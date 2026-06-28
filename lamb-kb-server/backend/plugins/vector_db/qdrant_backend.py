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
import threading
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

# Known embedding dimensions for the project's allow-list of (vendor, model)
# pairs. Used to size a Qdrant collection WITHOUT a live embedding call —
# Qdrant requires the vector size up front, but at collection-creation time
# no request-scoped API credentials are available (ADR-4). Probing an API
# vendor (e.g. openai) with a dummy key would fail, so we resolve the
# dimension from this table first and only fall back to a live probe for
# vendors/models that need no credentials (local/ollama) or are unknown.
_KNOWN_EMBEDDING_DIMENSIONS: dict[tuple[str, str], int] = {
    ("openai", "text-embedding-3-small"): 1536,
    ("openai", "text-embedding-3-large"): 3072,
    ("openai", "text-embedding-ada-002"): 1536,
    ("local", "all-MiniLM-L6-v2"): 384,
}


def _resolve_known_dimension(embedding_function: EmbeddingFunction) -> int | None:
    """Return the known vector dimension for *embedding_function*, or None.

    Looks up ``(vendor, model)`` in :data:`_KNOWN_EMBEDDING_DIMENSIONS`. The
    vendor is the plugin's class-level ``name``; the model is the instance's
    ``model`` attribute (set by ``EmbeddingFunction.__init__``). Returns None
    when either is missing or the pair is not in the table, signalling the
    caller to fall back to a live probe.
    """
    vendor = getattr(type(embedding_function), "name", None)
    model = getattr(embedding_function, "model", None)
    if not vendor or not model:
        return None
    return _KNOWN_EMBEDDING_DIMENSIONS.get((vendor, model))


# Module-level client cache so embedded Qdrant's per-path file lock is held by
# a single client per storage path. Without this, a fresh QdrantClient on every
# add/query/delete raises "Storage folder ... already accessed" under
# concurrency (mirrors the ChromaDB backend's cache). Remote clients are cached
# per URL since they share one connection regardless of collection.
_clients: dict[str, QdrantClient] = {}
_clients_lock = threading.Lock()


def _client_cache_key(storage_path: str) -> str:
    """Cache key: by URL in remote mode, by storage path in local mode."""
    if config.QDRANT_URL:
        return f"remote::{config.QDRANT_URL}"
    return f"local::{storage_path}"


def _make_client(storage_path: str) -> QdrantClient:
    """Return a cached Qdrant client (remote or local on-disk).

    Thread-safe: at most one client is constructed per cache key even under
    concurrent calls. The client is reused across add/query/delete so embedded
    Qdrant's file lock is not re-acquired on every operation.
    """
    key = _client_cache_key(storage_path)
    with _clients_lock:
        client = _clients.get(key)
        if client is None:
            if config.QDRANT_URL:
                logger.debug(
                    "QdrantBackend: using remote client at %s", config.QDRANT_URL
                )
                client = QdrantClient(
                    url=config.QDRANT_URL,
                    api_key=config.QDRANT_API_KEY or None,
                )
            else:
                logger.debug(
                    "QdrantBackend: using local on-disk client at %s", storage_path
                )
                client = QdrantClient(path=storage_path)
            _clients[key] = client
        return client


def _close_cached_client(storage_path: str) -> None:
    """Drop and close the cached local client for *storage_path*.

    Releases the embedded Qdrant file lock so the storage directory can be
    removed. Remote clients are keyed by URL and shared, so they are left in
    place (no per-path lock to release).
    """
    if config.QDRANT_URL:
        return
    key = _client_cache_key(storage_path)
    with _clients_lock:
        client = _clients.pop(key, None)
    if client is not None:
        try:
            client.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("QdrantBackend: error closing client for %s: %s", key, exc)


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

        Qdrant requires the vector size at collection-creation time (ChromaDB
        deduces it lazily). Since request-scoped embedding credentials are not
        available here (ADR-4), the dimension is resolved from a known
        ``(vendor, model)`` table first; only when that lookup misses do we
        fall back to a live probe (safe for credential-free vendors such as
        local/ollama).

        Returns:
            ``collection_id`` (Qdrant uses name-based addressing).
        """
        _ensure_marker_dir(storage_path)
        client = _make_client(storage_path)

        # Resolve the embedding dimension without a live API call when possible.
        embedding_dim = _resolve_known_dimension(embedding_function)
        if embedding_dim is None:
            # Fall back to a live probe (credential-free vendors / unknown models).
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
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Qdrant delete_collection '%s' failed (may already be absent): %s",
                collection_id,
                exc,
            )

        # Release the cached client's file lock before removing the directory.
        _close_cached_client(storage_path)
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

        response = client.query_points(
            collection_name=collection_id,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
        hits = response.points

        results: list[QueryResult] = []
        for hit in hits:
            payload: dict[str, Any] = dict(hit.payload or {})
            # Extract stored text and strip the internal key from metadata
            chunk_text: str = payload.pop(_TEXT_KEY, "")
            # Parent-document retrieval: prefer parent_text if present
            text = payload.pop("parent_text", None) or chunk_text
            # Normalise Qdrant cosine score from [-1,1] to [0,1]. Clamp to
            # guard against tiny float overshoots (e.g. 1.0000000002 for an
            # exact match), matching the ChromaDB backend's [0,1] contract.
            score = max(0.0, min(1.0, (float(hit.score) + 1.0) / 2.0))
            results.append(QueryResult(text=text, score=score, metadata=payload))

        return results
