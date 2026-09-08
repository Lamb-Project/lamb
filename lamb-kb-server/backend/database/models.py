"""SQLAlchemy ORM models for the KB Server metadata database.

Two tables track the service's state:

* ``collections`` — one row per knowledge base. The ``store_setup`` columns
  (chunking strategy, embedding vendor/model, vector DB backend) are locked
  at creation time (ADR-3).
* ``ingestion_jobs`` — persistent queue of async add-content operations.
  Embedding credentials are NEVER stored here — they live in memory only
  (see ``tasks/worker.py``), honoring ADR-4.

No vector payloads are stored in this DB; those live in the vector backend
under ``DATA_DIR/storage/{org_id}/{collection_id}/``.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class Collection(Base):
    """A knowledge base — a configured collection of vectors.

    The store setup columns (chunking + embedding + vector DB backend) are
    immutable after creation. Re-chunking or re-embedding would make the
    vectors inconsistent (ADR-3), so we simply refuse to change them.
    """

    __tablename__ = "collections"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_collection_org_name"),
    )

    id = Column(String, primary_key=True)
    organization_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # --- Locked store setup (immutable, ADR-3) ---
    chunking_strategy = Column(String, nullable=False)
    chunking_params = Column(Text, nullable=True)  # JSON
    embedding_vendor = Column(String, nullable=False)
    embedding_model = Column(String, nullable=False)
    embedding_endpoint = Column(String, nullable=True)
    vector_db_backend = Column(String, nullable=False)

    # Identifier the backend uses internally (e.g. ChromaDB collection name
    # or UUID). Stored separately from ``id`` so backend renames stay opaque
    # to API clients.
    backend_collection_id = Column(String, nullable=True)

    # Relative path (under STORAGE_DIR) for this collection's persistent data.
    storage_path = Column(String, nullable=False)

    # --- Status tracking ---
    status = Column(String, nullable=False, default="ready")
    # ready / error
    error_message = Column(Text, nullable=True)

    # --- Aggregate counters ---
    document_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )


class IngestionJob(Base):
    """Persistent record of an async add-content task for the worker queue.

    Jobs are written to SQLite so they survive service restarts. Stale
    ``processing`` jobs are reset to ``pending`` (or marked failed if they
    exceeded retry attempts) when the service boots.

    Embedding credentials are held in memory (``tasks/worker._job_api_keys``)
    and never persisted here — losing them on restart is intentional (ADR-4).
    """

    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True)
    collection_id = Column(String, nullable=False)
    organization_id = Column(String, nullable=False)

    # --- Payload reference ---
    # Full document payload (list[dict]) serialized to JSON. Kept here so the
    # worker can re-read it after a restart. Does NOT include credentials.
    documents_json = Column(Text, nullable=False)

    # --- Progress counters ---
    documents_total = Column(Integer, nullable=False, default=0)
    documents_processed = Column(Integer, nullable=False, default=0)
    chunks_created = Column(Integer, nullable=False, default=0)

    # --- Status ---
    status = Column(String, nullable=False, default="pending")
    # pending / processing / completed / failed / cancelled
    error_message = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)

    # --- Timestamps ---
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


# --- Indexes for common query patterns ---
Index("idx_collections_org", Collection.organization_id)
Index("idx_collections_status", Collection.status)
Index("idx_ingestion_jobs_status", IngestionJob.status)
Index(
    "idx_ingestion_jobs_status_created",
    IngestionJob.status,
    IngestionJob.created_at,
)
Index("idx_ingestion_jobs_collection", IngestionJob.collection_id)
