"""Content ingestion and deletion routes."""

import logging

from config import MAX_REQUEST_SIZE_BYTES
from database.connection import get_session
from dependencies import verify_token
from fastapi import APIRouter, Depends, HTTPException, Request, status
from schemas.content import AddContentRequest, AddContentResponse, DeleteVectorsResponse
from services import ingestion_service
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/collections",
    tags=["Content"],
    dependencies=[Depends(verify_token)],
)


@router.post(
    "/{collection_id}/add-content",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AddContentResponse,
)
async def add_content(
    collection_id: str,
    body: AddContentRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> AddContentResponse:
    """Queue documents for asynchronous ingestion into a collection.

    Embedding credentials are request-scoped and held in memory only (ADR-4).
    The job is processed by the background worker; poll ``GET /jobs/{job_id}``
    for status.

    Large payloads are rejected before parsing: if the ``Content-Length``
    header exceeds ``MAX_REQUEST_SIZE_BYTES`` the request is rejected with 413.

    Args:
        collection_id: Target collection UUID.
        body: Documents + optional embedding credentials.
        request: Raw FastAPI request (for Content-Length check).
        db: Database session.

    Returns:
        Job ID and initial status.
    """
    # Guard against oversized payloads using the Content-Length header.
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_REQUEST_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=(
                        f"Request body exceeds the maximum allowed size of "
                        f"{MAX_REQUEST_SIZE_BYTES} bytes."
                    ),
                )
        except ValueError:
            pass  # Malformed Content-Length header — let FastAPI handle it.

    job = ingestion_service.queue_add_content(db, collection_id, body)

    return AddContentResponse(
        job_id=job.id,
        status=job.status,
        documents_total=job.documents_total,
    )


@router.delete(
    "/{collection_id}/content/{source_item_id}",
    response_model=DeleteVectorsResponse,
)
async def delete_content(
    collection_id: str,
    source_item_id: str,
    db: Session = Depends(get_session),
) -> DeleteVectorsResponse:
    """Delete all vectors for a specific source item from a collection.

    Does not affect the Library Manager — this only removes vectors from the
    vector DB backend.

    Args:
        collection_id: Target collection UUID.
        source_item_id: Source item ID whose vectors should be removed.
        db: Database session.

    Returns:
        Source item ID and count of vectors deleted.
    """
    deleted_count = ingestion_service.delete_vectors(db, collection_id, source_item_id)
    return DeleteVectorsResponse(
        source_item_id=source_item_id,
        deleted_count=deleted_count,
    )
