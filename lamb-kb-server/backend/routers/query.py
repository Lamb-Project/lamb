"""Vector similarity query routes."""

import logging

from database.connection import get_session
from dependencies import verify_token
from fastapi import APIRouter, Depends
from schemas.query import QueryRequest, QueryResponse, QueryResultItem
from services import query_service
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/collections",
    tags=["Query"],
    dependencies=[Depends(verify_token)],
)


@router.post("/{collection_id}/query", response_model=QueryResponse)
async def query_collection(
    collection_id: str,
    body: QueryRequest,
    db: Session = Depends(get_session),
) -> QueryResponse:
    """Run a similarity search against a collection.

    Embedding credentials are request-scoped (ADR-4) — provide them in the
    request body alongside the query text. Results include chunk text, cosine
    similarity score, and full chunk metadata (including permalink URLs for
    source citations).

    Args:
        collection_id: Target collection UUID.
        body: Query text, top-k, and optional embedding credentials.
        db: Database session.

    Returns:
        List of matching chunks with scores and metadata.
    """
    results = query_service.query_collection(db, collection_id, body)

    return QueryResponse(
        results=[
            QueryResultItem(
                text=r.text,
                score=r.score,
                metadata=r.metadata,
            )
            for r in results
        ],
        query=body.query_text,
        top_k=body.top_k,
    )
