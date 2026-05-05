"""Collection CRUD routes."""

import logging

from database.connection import get_session
from dependencies import verify_token
from fastapi import APIRouter, Depends, Query, status
from schemas.collection import (
    CollectionListResponse,
    CollectionResponse,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from services import collection_service
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/collections",
    tags=["Collections"],
    dependencies=[Depends(verify_token)],
)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CollectionResponse)
async def create_collection(
    body: CreateCollectionRequest,
    db: Session = Depends(get_session),
) -> CollectionResponse:
    """Create a new collection.

    The ``id`` field is optional — if omitted, the server generates a UUID.
    Store setup (chunking strategy, embedding vendor/model, vector DB backend)
    is locked at creation time and cannot be changed later (ADR-3).

    Args:
        body: Collection creation payload.
        db: Database session.

    Returns:
        The created collection.
    """
    collection = collection_service.create_collection(db, body)
    return CollectionResponse.from_orm_row(collection)


@router.get("", response_model=CollectionListResponse)
async def list_collections(
    organization_id: str | None = Query(default=None, description="Filter by organization ID."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> CollectionListResponse:
    """List collections, optionally filtered by organization.

    Args:
        organization_id: Optional org filter.
        limit: Max results (1–200).
        offset: Skip count.
        db: Database session.

    Returns:
        Paginated list of collections.
    """
    rows, total = collection_service.list_collections(db, organization_id, limit, offset)
    return CollectionListResponse(
        collections=[CollectionResponse.from_orm_row(r) for r in rows],
        total=total,
    )


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    db: Session = Depends(get_session),
) -> CollectionResponse:
    """Get a collection by ID.

    Args:
        collection_id: Collection UUID.
        db: Database session.

    Returns:
        Collection details.
    """
    collection = collection_service.get_collection(db, collection_id)
    return CollectionResponse.from_orm_row(collection)


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    body: UpdateCollectionRequest,
    db: Session = Depends(get_session),
) -> CollectionResponse:
    """Update mutable collection fields (name and/or description).

    Store setup is immutable (ADR-3). Attempting to rename to a name already
    taken within the same organization returns 409.

    Args:
        collection_id: Collection UUID.
        body: Fields to update.
        db: Database session.

    Returns:
        Updated collection.
    """
    collection = collection_service.update_collection(db, collection_id, body)
    return CollectionResponse.from_orm_row(collection)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: str,
    db: Session = Depends(get_session),
) -> None:
    """Delete a collection and all its vectors.

    The vector DB backend collection is removed first, then the metadata row,
    then the storage directory.

    Args:
        collection_id: Collection UUID.
        db: Database session.
    """
    collection_service.delete_collection(db, collection_id)
