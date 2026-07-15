"""Business logic for vector similarity queries."""

import logging

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

    logger.debug(
        "Query on collection %s returned %d results for '%s'",
        collection_id,
        len(results),
        req.query_text[:80],
    )
    return results
