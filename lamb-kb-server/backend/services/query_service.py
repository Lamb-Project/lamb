"""Business logic for vector similarity queries."""

import logging
from typing import Any

from database.models import Collection
from fastapi import HTTPException, status
from plugins.base import EmbeddingRegistry, QueryResult, VectorDBRegistry
from schemas.query import QueryRequest
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def query_collection(
    db: Session, collection_id: str, req: QueryRequest
) -> list[QueryResult]:
    """Run a similarity search against a collection.

    Embedding credentials are request-scoped (ADR-4) and come from the
    query request body — never from the collection row.

    Args:
        db: Database session.
        collection_id: Target collection primary key.
        req: Validated query request.

    Returns:
        List of ``QueryResult`` objects (text, score, metadata).

    Raises:
        HTTPException: 404 if collection not found, 503 if backend unavailable.
    """
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_id}' not found.",
        )

    creds = req.embedding_credentials
    embedding_function = EmbeddingRegistry.build(
        collection.embedding_vendor,
        model=collection.embedding_model,
        api_key=creds.api_key,
        api_endpoint=creds.api_endpoint or collection.embedding_endpoint or "",
    )

    backend = VectorDBRegistry.get(collection.vector_db_backend)
    if backend is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Vector DB backend '{collection.vector_db_backend}' is not available."
            ),
        )

    results = backend.query(
        collection_id=collection.backend_collection_id or collection_id,
        storage_path=collection.storage_path,
        query_text=req.query_text,
        top_k=req.top_k,
        embedding_function=embedding_function,
    )

    # Auto-route through the KG-RAG plugin when the collection was built
    # with a graph. This makes the regular /query endpoint (used by the
    # "Test Query" affordance and by ``knowledge_store_rag.py`` at chat
    # time) actually exercise question-entity extraction + graph
    # expansion — without any caller-side opt-in. The plugin gracefully
    # degrades to the vector baseline when Neo4j isn't reachable or the
    # graph returns nothing, so this is safe to always-on for
    # graph-enabled collections.
    if getattr(collection, "graph_enabled", False):
        import config as config_module  # noqa: PLC0415

        if config_module.KG_RAG_ENABLED:
            from plugins.kg_rag_query import KGRAGQueryPlugin  # noqa: PLC0415

            baseline_dicts = [
                {
                    "similarity": r.score,
                    "data": r.text,
                    "metadata": dict(r.metadata or {}),
                }
                for r in results
            ]
            try:
                augmented = KGRAGQueryPlugin().augment(
                    db=db,
                    collection=collection,
                    backend=backend,
                    embedding_function=embedding_function,
                    query_text=req.query_text,
                    baseline_results=baseline_dicts,
                    params={"top_k": req.top_k, "include_trace": True},
                )
                results = [
                    QueryResult(
                        text=item.get("data", "") or "",
                        score=float(item.get("similarity") or 0.0),
                        metadata=dict(item.get("metadata") or {}),
                    )
                    for item in augmented
                ]
            except Exception as exc:  # noqa: BLE001 — degrade to baseline on any failure
                logger.warning(
                    "KG-RAG augmentation failed for collection %s, "
                    "returning vector baseline: %s",
                    collection_id,
                    exc,
                )

    logger.debug(
        "Query on collection %s returned %d results for '%s'",
        collection_id,
        len(results),
        req.query_text[:80],
    )
    return results


def query_with_plugin(
    *,
    db: Session,
    collection_id: str,
    query_text: str,
    plugin_name: str = "simple_query",
    plugin_params: dict[str, Any] | None = None,
    embedding_credentials: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a query through a named plugin (``simple_query`` or ``kg_rag_query``).

    This is the path used by KG-RAG / benchmark callers that need both
    results and side-channel metadata (graph trace, latency timings). The
    return shape is a dict with ``{results, query, top_k, timing}`` so
    benchmark code can read ``timing.total_ms`` and walk the result-attached
    ``metadata.kg_rag`` trace.

    Args:
        db: Database session.
        collection_id: Target collection ID.
        query_text: Free-text query.
        plugin_name: ``simple_query`` (baseline vector retrieval) or
            ``kg_rag_query`` (vector seed + Neo4j graph expansion).
        plugin_params: Plugin-specific tuning (``top_k``, ``threshold``,
            ``graph_depth``, ``include_trace``, ...).
        embedding_credentials: Per-request embedding credentials
            (``{"api_key": ..., "api_endpoint": ...}``). Falls back to the
            collection-level endpoint when no key is supplied.

    Returns:
        ``{"results": [...], "query": str, "top_k": int, "timing": {...}}``.
    """
    import time

    params = dict(plugin_params or {})
    top_k = int(params.get("top_k", 5) or 5)
    threshold = float(params.get("threshold", 0.0) or 0.0)
    creds = embedding_credentials or {}

    collection = (
        db.query(Collection).filter(Collection.id == collection_id).first()
    )
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_id}' not found.",
        )

    embedding_function = EmbeddingRegistry.build(
        collection.embedding_vendor,
        model=collection.embedding_model,
        api_key=creds.get("api_key", ""),
        api_endpoint=creds.get("api_endpoint") or collection.embedding_endpoint or "",
    )

    backend = VectorDBRegistry.get(collection.vector_db_backend)
    if backend is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Vector DB backend '{collection.vector_db_backend}' is not available."
            ),
        )

    start = time.perf_counter()
    raw_results = backend.query(
        collection_id=collection.backend_collection_id or collection_id,
        storage_path=collection.storage_path,
        query_text=query_text,
        top_k=top_k,
        embedding_function=embedding_function,
    )

    formatted = [
        {
            "similarity": r.score,
            "data": r.text,
            "metadata": dict(r.metadata or {}),
        }
        for r in raw_results
        if r.score >= threshold
    ]

    # Optional KG-RAG augmentation via the registered query plugin.
    if plugin_name == "kg_rag_query":
        try:
            from plugins.kg_rag_query import KGRAGQueryPlugin

            plugin = KGRAGQueryPlugin()
            formatted = plugin.augment(
                db=db,
                collection=collection,
                backend=backend,
                embedding_function=embedding_function,
                query_text=query_text,
                baseline_results=formatted,
                params=params,
            )
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            logger.warning(
                "KG-RAG augmentation failed for collection %s: %s",
                collection_id,
                exc,
            )
    elapsed_ms = (time.perf_counter() - start) * 1000

    return {
        "results": formatted,
        "query": query_text,
        "top_k": top_k,
        "timing": {"total_ms": elapsed_ms},
    }
