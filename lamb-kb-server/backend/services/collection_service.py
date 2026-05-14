"""Business logic for collection CRUD operations."""

import json
import logging
import shutil
from uuid import uuid4

from config import STORAGE_DIR
from database.models import Collection
from fastapi import HTTPException, status
from plugins.base import ChunkingRegistry, EmbeddingRegistry, VectorDBRegistry
from plugins.chunking._common import validate_chunking_params
from schemas.collection import CreateCollectionRequest, UpdateCollectionRequest
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _validate_plugins(req: CreateCollectionRequest) -> None:
    """Raise 400/422 if any plugin referenced in the request is not registered
    or if ``chunking_params`` contains keys unknown to the chosen strategy."""
    errors = []
    if not ChunkingRegistry.is_registered(req.chunking_strategy):
        errors.append(
            f"Chunking strategy '{req.chunking_strategy}' is not registered. "
            f"Available: {[p['name'] for p in ChunkingRegistry.list_plugins()]}"
        )
    if not VectorDBRegistry.is_registered(req.vector_db_backend):
        errors.append(
            f"Vector DB backend '{req.vector_db_backend}' is not registered. "
            f"Available: {[p['name'] for p in VectorDBRegistry.list_plugins()]}"
        )
    if not EmbeddingRegistry.is_registered(req.embedding.vendor):
        errors.append(
            f"Embedding vendor '{req.embedding.vendor}' is not registered. "
            f"Available: {[p['name'] for p in EmbeddingRegistry.list_plugins()]}"
        )
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=" | ".join(errors),
        )

    # Validate chunking_params against the chosen strategy's allow-list.
    # Only reached when the strategy is registered (errors guard above).
    if req.chunking_params:
        strategy = ChunkingRegistry.get(req.chunking_strategy)
        try:
            validate_chunking_params(strategy, req.chunking_params)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc


def create_collection(db: Session, req: CreateCollectionRequest) -> Collection:
    """Create a new collection.

    Steps:
        1. Validate plugins are registered.
        2. Check uniqueness of (organization_id, name).
        3. Generate collection_id if not provided.
        4. Create storage directory.
        5. Build embedding function and create the vector DB collection.
        6. Persist the Collection row.
        7. On failure after step 4: clean up storage dir and re-raise.

    Args:
        db: Database session.
        req: Validated creation request.

    Returns:
        The newly created Collection row.

    Raises:
        HTTPException: 400 for invalid plugin names, 409 for duplicate name.
    """
    _validate_plugins(req)

    # Uniqueness check: (organization_id, name)
    existing = (
        db.query(Collection)
        .filter(
            Collection.organization_id == req.organization_id,
            Collection.name == req.name,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A collection named '{req.name}' already exists in "
                f"organization '{req.organization_id}'."
            ),
        )

    collection_id = req.id or uuid4().hex
    storage_path = str(STORAGE_DIR / req.organization_id / collection_id)

    # Some vector backends (e.g. ChromaDB 1.5+) require collection names of
    # 3-512 characters from [a-zA-Z0-9._-], starting and ending with an
    # alphanumeric. Prefixing with "kb_" makes even short user-supplied IDs
    # valid and also keeps backend names namespaced if a backend is shared
    # across organisations at the infrastructure layer.
    backend_name = f"kb_{collection_id}"

    # Create storage directory before touching the vector backend.
    import os  # noqa: PLC0415

    os.makedirs(storage_path, exist_ok=True)

    try:
        # Build embedding function (no credentials at creation time — this is
        # usually a no-op against the embedding backend).
        embedding_function = EmbeddingRegistry.build(
            req.embedding.vendor,
            model=req.embedding.model,
            api_endpoint=req.embedding.api_endpoint,
        )

        # Create the collection inside the vector DB backend.
        backend = VectorDBRegistry.get(req.vector_db_backend)
        backend.create_collection(
            collection_id=backend_name,
            storage_path=storage_path,
            embedding_function=embedding_function,
        )
        backend_collection_id = backend_name

        # Persist metadata row.
        collection = Collection(
            id=collection_id,
            organization_id=req.organization_id,
            name=req.name,
            description=req.description,
            chunking_strategy=req.chunking_strategy,
            chunking_params=json.dumps(req.chunking_params),
            embedding_vendor=req.embedding.vendor,
            embedding_model=req.embedding.model,
            embedding_endpoint=req.embedding.api_endpoint or None,
            vector_db_backend=req.vector_db_backend,
            backend_collection_id=backend_collection_id,
            storage_path=storage_path,
            status="ready",
            document_count=0,
            chunk_count=0,
        )
        db.add(collection)
        db.commit()
        db.refresh(collection)

    except HTTPException:
        shutil.rmtree(storage_path, ignore_errors=True)
        raise
    except Exception:
        shutil.rmtree(storage_path, ignore_errors=True)
        raise

    logger.info(
        "Created collection %s ('%s') in org %s",
        collection_id,
        req.name,
        req.organization_id,
    )
    return collection


def get_collection(db: Session, collection_id: str) -> Collection:
    """Fetch a collection by ID.

    Args:
        db: Database session.
        collection_id: Primary key.

    Returns:
        The Collection row.

    Raises:
        HTTPException: 404 if not found.
    """
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_id}' not found.",
        )
    return collection


def list_collections(
    db: Session,
    organization_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Collection], int]:
    """List collections, optionally filtered by organization.

    Args:
        db: Database session.
        organization_id: Optional filter.
        limit: Max rows to return.
        offset: Number of rows to skip.

    Returns:
        Tuple of (list of Collection rows, total matching count).
    """
    query = db.query(Collection)
    if organization_id is not None:
        query = query.filter(Collection.organization_id == organization_id)

    total = query.count()
    rows = query.order_by(Collection.created_at.desc()).offset(offset).limit(limit).all()
    return rows, total


def update_collection(
    db: Session, collection_id: str, req: UpdateCollectionRequest
) -> Collection:
    """Update mutable fields (name, description, chunking_params) of a collection.

    Strategy, embedding vendor/model, and vector_db_backend remain immutable
    (ADR-3) — changing those would require re-embedding every existing chunk.
    ``chunking_params`` updates apply only to content ingested AFTER the
    update; existing chunks keep their original parameters.

    Args:
        db: Database session.
        collection_id: Primary key.
        req: Update request.

    Returns:
        Updated Collection row.

    Raises:
        HTTPException: 404 if not found, 409 if name already taken in the org,
            422 if chunking_params are out of range or contain unknown keys.
    """
    collection = get_collection(db, collection_id)

    if req.name is not None and req.name != collection.name:
        # Check uniqueness of new name within org.
        conflict = (
            db.query(Collection)
            .filter(
                Collection.organization_id == collection.organization_id,
                Collection.name == req.name,
                Collection.id != collection_id,
            )
            .first()
        )
        if conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A collection named '{req.name}' already exists in "
                    f"organization '{collection.organization_id}'."
                ),
            )
        collection.name = req.name

    if req.description is not None:
        collection.description = req.description

    if req.chunking_params is not None:
        # Validate against the (immutable) chunking strategy's declared params
        from plugins.chunking._common import validate_chunking_params  # noqa: PLC0415
        from plugins.base import ChunkingRegistry  # noqa: PLC0415

        strategy = ChunkingRegistry.get(collection.chunking_strategy)
        try:
            validate_chunking_params(strategy, req.chunking_params)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        import json  # noqa: PLC0415
        collection.chunking_params = json.dumps(req.chunking_params)

    db.commit()
    db.refresh(collection)

    logger.info("Updated collection %s", collection_id)
    return collection


def delete_collection(db: Session, collection_id: str) -> None:
    """Delete a collection and all associated vectors and storage.

    Deletion order:
        1. Fetch collection — raise 404 if missing.
        2. Call vector DB backend to drop the collection.
        3. Delete the DB row and commit.
        4. Remove the storage directory from disk.

    This order ensures the DB is authoritative: if the process crashes
    between step 3 and 4, the directory becomes an orphan (harmless) rather
    than the DB believing the collection still exists.

    Args:
        db: Database session.
        collection_id: Primary key.

    Raises:
        HTTPException: 404 if not found.
    """
    collection = get_collection(db, collection_id)
    storage_path = collection.storage_path

    # Step 2: drop vectors from the backend. Use the stored
    # backend_collection_id (with its "kb_" prefix) so the backend finds
    # the right collection name.
    backend_name = collection.backend_collection_id or f"kb_{collection_id}"
    try:
        backend = VectorDBRegistry.get(collection.vector_db_backend)
        if backend is not None:
            backend.delete_collection(
                collection_id=backend_name,
                storage_path=storage_path,
            )
    except Exception:
        logger.exception(
            "Vector backend delete failed for collection %s — proceeding with DB delete",
            collection_id,
        )

    # Step 3: remove DB row first.
    db.delete(collection)
    db.commit()

    # Step 4: clean up storage directory.
    shutil.rmtree(storage_path, ignore_errors=True)

    logger.info("Deleted collection %s", collection_id)
