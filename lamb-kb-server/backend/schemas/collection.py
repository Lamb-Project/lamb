"""Pydantic schemas for collection CRUD operations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# --- Sub-models ---


class EmbeddingConfig(BaseModel):
    """Describes the collection-level embedding setup.

    Credentials (api_key) are NOT included here — they are request-scoped
    and held in memory only (ADR-4).
    """

    vendor: str = Field(..., description="Embedding vendor name (e.g. 'openai', 'ollama').")
    model: str = Field(..., description="Model identifier (e.g. 'text-embedding-3-small').")
    api_endpoint: str = Field(
        default="",
        description="Optional override for the vendor's API base URL.",
    )


# --- Requests ---


class CreateCollectionRequest(BaseModel):
    """Body for ``POST /collections``."""

    id: str | None = Field(
        default=None,
        description="LAMB-generated UUID. If omitted, the server generates one.",
    )
    organization_id: str = Field(..., description="Owning organization ID.")
    name: str = Field(..., min_length=1, description="Human-readable collection name.")
    description: str | None = Field(default=None, description="Optional description.")
    chunking_strategy: str = Field(
        ..., description="Registered chunking strategy name (e.g. 'simple', 'by_page')."
    )
    chunking_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Strategy-specific parameters (chunk_size, overlap, ...).",
    )
    embedding: EmbeddingConfig = Field(..., description="Embedding vendor and model configuration.")
    vector_db_backend: str = Field(
        default="chromadb",
        description="Registered vector DB backend name.",
    )


class UpdateCollectionRequest(BaseModel):
    """Body for ``PUT /collections/{collection_id}``.

    Only ``name`` and ``description`` are mutable. Store setup is locked
    at creation time (ADR-3).
    """

    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None)


# --- Responses ---


class CollectionResponse(BaseModel):
    """Full collection view returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    description: str | None
    chunking_strategy: str
    chunking_params: dict[str, Any]
    embedding: EmbeddingConfig
    vector_db_backend: str
    status: str
    document_count: int
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_row(cls, row: Any) -> "CollectionResponse":
        """Build a CollectionResponse from an ORM Collection row.

        The ORM row stores embedding fields flat; this factory assembles the
        nested ``EmbeddingConfig`` object.
        """
        import json  # noqa: PLC0415

        return cls(
            id=row.id,
            organization_id=row.organization_id,
            name=row.name,
            description=row.description,
            chunking_strategy=row.chunking_strategy,
            chunking_params=json.loads(row.chunking_params or "{}"),
            embedding=EmbeddingConfig(
                vendor=row.embedding_vendor,
                model=row.embedding_model,
                api_endpoint=row.embedding_endpoint or "",
            ),
            vector_db_backend=row.vector_db_backend,
            status=row.status,
            document_count=row.document_count,
            chunk_count=row.chunk_count,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class CollectionListResponse(BaseModel):
    """Paginated list of collections."""

    collections: list[CollectionResponse]
    total: int
