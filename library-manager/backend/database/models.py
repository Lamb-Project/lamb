"""SQLAlchemy ORM models for the Library Manager database."""

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class Organization(Base):
    """Lightweight org record — LAMB is the source of truth for orgs."""

    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    libraries = relationship(
        "Library", back_populates="organization", cascade="all, delete-orphan"
    )


class Library(Base):
    """A named document repository within an organization."""

    __tablename__ = "libraries"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_library_org_name"),
    )

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String, nullable=False)
    import_config = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    organization = relationship("Organization", back_populates="libraries")
    items = relationship(
        "ContentItem", back_populates="library", cascade="all, delete-orphan"
    )


class ContentItem(Base):
    """A single imported document stored in the structured repository."""

    __tablename__ = "content_items"

    id = Column(String, primary_key=True)
    library_id = Column(String, ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # 'file', 'url', 'youtube'
    original_filename = Column(String, nullable=True)
    content_type = Column(String, nullable=True)  # MIME type
    file_size = Column(Integer, nullable=True)
    source_url = Column(String, nullable=True)  # For URL/YouTube sources

    # Structured content paths (relative to CONTENT_DIR/{org}/{lib}/{item}/)
    base_path = Column(String, nullable=False)
    original_path = Column(String, nullable=True)
    full_markdown_path = Column(String, nullable=True)
    page_count = Column(Integer, nullable=False, default=0)
    image_count = Column(Integer, nullable=False, default=0)

    # Source reference (JSON)
    source_ref = Column(Text, nullable=True)

    # Permalink base: /docs/{org}/{lib}/{item}
    permalink_base = Column(String, nullable=False)

    # Full metadata.json content (JSON, includes permalinks)
    metadata_ = Column("metadata", Text, nullable=True)

    # Import details
    import_plugin = Column(String, nullable=False)
    import_params = Column(Text, nullable=True)  # JSON

    # Status tracking
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    processing_stats = Column(Text, nullable=True)  # JSON

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    library = relationship("Library", back_populates="items")
    images = relationship(
        "ContentImage", back_populates="content_item", cascade="all, delete-orphan"
    )


class ContentImage(Base):
    """An image extracted during document import."""

    __tablename__ = "content_images"

    id = Column(String, primary_key=True)
    content_item_id = Column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False
    )
    image_path = Column(String, nullable=False)
    llm_description = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    content_item = relationship("ContentItem", back_populates="images")


class ImportJob(Base):
    """Persistent record of an import task for the async worker queue.

    Jobs are written to SQLite so they survive service restarts.
    The async worker loop picks up pending jobs and processes them.
    """

    __tablename__ = "import_jobs"

    id = Column(String, primary_key=True)
    content_item_id = Column(String, nullable=False)
    library_id = Column(String, nullable=False)
    organization_id = Column(String, nullable=False)

    # Import parameters
    source_type = Column(String, nullable=False)  # 'file', 'url', 'youtube'
    plugin_name = Column(String, nullable=False)
    plugin_params = Column(Text, nullable=True)  # JSON
    # API keys are held in memory only (tasks.worker._job_api_keys dict),
    # never persisted to this table.

    # Source data
    source_path = Column(String, nullable=True)  # Local file path (for file uploads)
    source_url = Column(String, nullable=True)  # URL (for url/youtube imports)
    title = Column(String, nullable=False)

    # Status
    status = Column(String, nullable=False, default="pending")
    # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


# Indexes for common query patterns
Index("idx_content_items_library", ContentItem.library_id)
Index("idx_content_items_org", ContentItem.organization_id)
Index("idx_content_items_status", ContentItem.status)
Index("idx_content_images_item", ContentImage.content_item_id)
Index("idx_import_jobs_status", ImportJob.status)
Index("idx_import_jobs_item", ImportJob.content_item_id)
