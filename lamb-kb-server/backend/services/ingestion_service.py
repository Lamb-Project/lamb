"""Business logic for queuing and executing ingestion jobs."""

import json
import logging
from uuid import uuid4

from database.models import Collection, IngestionJob
from fastapi import HTTPException, status
from plugins.base import (
    ChunkingRegistry,
    DocumentInput,
    EmbeddingRegistry,
    VectorDBRegistry,
)
from plugins.chunking._common import validate_chunking_params
from schemas.content import AddContentRequest
from sqlalchemy.orm import Session
from tasks.worker import store_credentials

logger = logging.getLogger(__name__)

# How many documents to process before committing progress counters.
_COMMIT_BATCH_SIZE = 5


def queue_add_content(
    db: Session, collection_id: str, req: AddContentRequest
) -> IngestionJob:
    """Queue an add-content request as a persistent ingestion job.

    Credentials are stored in memory only (ADR-4) and are never written to
    the DB row. The worker will pop them when it picks up the job.

    Steps:
        1. Fetch collection; raise 404 if missing.
        2. Guard against empty documents list.
        3. Serialize documents (without credentials) to JSON.
        4. Persist IngestionJob row.
        5. Store credentials in memory via tasks.worker.
        6. Return the job row.

    Args:
        db: Database session.
        collection_id: Target collection primary key.
        req: Validated add-content request.

    Returns:
        The newly created IngestionJob row.

    Raises:
        HTTPException: 404 if collection not found, 400 if documents is empty.
    """
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_id}' not found.",
        )

    if not req.documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="documents list must not be empty.",
        )

    # Serialize documents payload (credentials deliberately excluded).
    docs_list = [
        {
            "source_item_id": doc.source_item_id,
            "title": doc.title,
            "text": doc.text,
            "permalinks": doc.permalinks.model_dump(),
            "pages": [p.model_dump() for p in doc.pages],
            "extra_metadata": doc.extra_metadata,
        }
        for doc in req.documents
    ]

    job = IngestionJob(
        id=uuid4().hex,
        collection_id=collection_id,
        organization_id=collection.organization_id,
        documents_json=json.dumps(docs_list),
        status="pending",
        documents_total=len(req.documents),
        documents_processed=0,
        chunks_created=0,
        attempts=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Store credentials in memory — never persisted (ADR-4).
    creds = req.embedding_credentials
    store_credentials(
        job.id,
        {"api_key": creds.api_key, "api_endpoint": creds.api_endpoint},
    )

    logger.info(
        "Queued ingestion job %s for collection %s (%d documents)",
        job.id,
        collection_id,
        len(req.documents),
    )
    return job


def execute_ingestion_job(
    db: Session,
    job: IngestionJob,
    collection: Collection,
    credentials: dict,
) -> None:
    """Execute a single ingestion job in the worker thread pool.

    Called by ``tasks.worker._process_job_sync`` in a separate thread.
    Modifies ``job`` and ``collection`` in place; the worker commits final
    status after this function returns.

    Steps:
        1. Parse documents JSON from the job row.
        2. Build embedding function with request-scoped credentials.
        3. Load chunking strategy and vector DB backend.
        4. For each document: chunk → embed+store → update progress.
        5. Update collection aggregate counters.

    Args:
        db: Database session (caller-owned, worker closes it).
        job: The IngestionJob ORM row (status already set to 'processing').
        collection: The owning Collection ORM row.
        credentials: Embedding credentials dict popped from memory by worker.

    Raises:
        Any exception raised by the plugins — propagates to worker for
        failure recording. Do NOT catch-and-ignore here.
    """
    docs_list: list[dict] = json.loads(job.documents_json or "[]")

    # Build embedding function with request-scoped credentials.
    embedding_function = EmbeddingRegistry.build(
        collection.embedding_vendor,
        model=collection.embedding_model,
        api_key=credentials.get("api_key", ""),
        api_endpoint=(
            credentials.get("api_endpoint") or collection.embedding_endpoint or ""
        ),
    )

    # Load chunking strategy and its stored params.
    strategy = ChunkingRegistry.get(collection.chunking_strategy)
    if strategy is None:
        raise RuntimeError(
            f"Chunking strategy '{collection.chunking_strategy}' is not available. "
            "Was it disabled after collection creation?"
        )
    chunking_params: dict = json.loads(collection.chunking_params or "{}")
    # Defense-in-depth: params were validated at collection-create time, but a
    # direct DB write or migration could bypass that. Fail loudly here rather
    # than silently dropping unknown keys.
    if chunking_params:
        try:
            validate_chunking_params(strategy, chunking_params)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

    # Load vector DB backend.
    backend = VectorDBRegistry.get(collection.vector_db_backend)
    if backend is None:
        raise RuntimeError(
            f"Vector DB backend '{collection.vector_db_backend}' is not available. "
            "Was it disabled after collection creation?"
        )

    total_chunks_added = 0

    for i, doc_dict in enumerate(docs_list):
        # Build the plugin dataclass from the serialized payload.
        doc_input = DocumentInput(
            source_item_id=doc_dict["source_item_id"],
            title=doc_dict["title"],
            text=doc_dict["text"],
            permalinks=doc_dict.get("permalinks", {}),
            pages=doc_dict.get("pages", []),
            extra_metadata=doc_dict.get("extra_metadata", {}),
        )

        chunks = strategy.chunk(doc_input, chunking_params)

        n_stored = 0
        if chunks:
            n_stored = backend.add_chunks(
                collection_id=collection.backend_collection_id or collection.id,
                storage_path=collection.storage_path,
                chunks=chunks,
                embedding_function=embedding_function,
            )

        job.documents_processed += 1
        job.chunks_created += n_stored
        total_chunks_added += n_stored

        # Commit progress every batch so partial progress is visible.
        if (i + 1) % _COMMIT_BATCH_SIZE == 0:
            db.commit()

        logger.debug(
            "Job %s: processed document %s → %d chunks",
            job.id,
            doc_dict["source_item_id"],
            n_stored,
        )

    # Update collection aggregate counters.
    collection.document_count = (collection.document_count or 0) + len(docs_list)
    collection.chunk_count = (collection.chunk_count or 0) + total_chunks_added
    db.commit()

    logger.info(
        "Job %s ingestion complete: %d documents, %d chunks added",
        job.id,
        len(docs_list),
        total_chunks_added,
    )


def delete_vectors(
    db: Session, collection_id: str, source_item_id: str
) -> int:
    """Delete all vectors for a given source item from a collection.

    Updates collection counters after deletion. document_count is decremented
    by 1 if any vectors were removed (no per-source counter exists). Counters
    are clamped at 0 to guard against drift.

    Args:
        db: Database session.
        collection_id: Target collection primary key.
        source_item_id: Source item whose vectors should be removed.

    Returns:
        Number of vectors deleted.

    Raises:
        HTTPException: 404 if collection not found.
    """
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_id}' not found.",
        )

    backend = VectorDBRegistry.get(collection.vector_db_backend)
    if backend is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Vector DB backend '{collection.vector_db_backend}' is not available."
            ),
        )

    deleted_count = backend.delete_by_source(
        collection_id=collection.backend_collection_id or collection_id,
        storage_path=collection.storage_path,
        source_item_id=source_item_id,
    )

    if deleted_count > 0:
        collection.chunk_count = max(0, (collection.chunk_count or 0) - deleted_count)
        collection.document_count = max(0, (collection.document_count or 0) - 1)
    db.commit()

    logger.info(
        "Deleted %d vectors for source_item_id '%s' from collection %s",
        deleted_count,
        source_item_id,
        collection_id,
    )
    return deleted_count
