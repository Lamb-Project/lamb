"""Pydantic schemas for add-content and delete-content operations."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Sub-models ---


class PageInput(BaseModel):
    """One pre-split page supplied by LAMB for multi-page documents."""

    page_number: int
    text: str


class PermalinkInput(BaseModel):
    """Permalink URLs for each content representation of a document.

    LAMB passes these through verbatim; they are attached to every chunk
    so query results can cite their source (ADR-1). Extra keys are allowed
    so LAMB can pass future permalink variants without a schema change.
    """

    model_config = ConfigDict(extra="allow")

    original: str = Field(default="", description="URL to the original source file.")
    full_markdown: str = Field(default="", description="URL to the full-markdown rendition.")
    pages: list[str] = Field(
        default_factory=list,
        description="Per-page URLs (index matches page_number - 1).",
    )


class EmbeddingCredentials(BaseModel):
    """Request-scoped embedding credentials.

    Never persisted to disk (ADR-4). Held in memory until the worker picks
    up the ingestion job, then popped.
    """

    api_key: str = Field(default="", description="Vendor API key.")
    api_endpoint: str = Field(
        default="", description="Optional API base URL override."
    )


# --- Ingestion request ---


class DocumentInputPayload(BaseModel):
    """One document delivered by LAMB for ingestion.

    LAMB is responsible for fetching and normalizing content from the
    Library Manager before sending it here (ADR-1).
    """

    source_item_id: str = Field(
        ..., description="Stable content-item ID from LAMB / Library Manager."
    )
    title: str = Field(..., description="Document title.")
    text: str = Field(..., description="Full document text (used by most chunking strategies).")
    permalinks: PermalinkInput = Field(
        default_factory=PermalinkInput,
        description="Permalink URLs for each content representation.",
    )
    pages: list[PageInput] = Field(
        default_factory=list,
        description="Pre-split pages for the by_page chunking strategy.",
    )
    extra_metadata: dict[str, str | int | float | bool] = Field(
        default_factory=dict,
        description="Free-form metadata merged into every chunk produced from this document.",
    )

    @field_validator("extra_metadata")
    @classmethod
    def _validate_extra_metadata(
        cls, v: dict[str, Any]
    ) -> dict[str, str | int | float | bool]:
        for key, value in v.items():
            if value is None:
                raise ValueError(
                    f"extra_metadata[{key!r}] is None; ChromaDB requires non-null primitive values."
                )
            if not isinstance(value, (str, int, float, bool)):
                raise ValueError(
                    f"extra_metadata[{key!r}] has type {type(value).__name__}; "
                    f"only str, int, float, bool are allowed."
                )
        return v


class AddContentRequest(BaseModel):
    """Body for ``POST /collections/{collection_id}/add-content``."""

    documents: list[DocumentInputPayload] = Field(
        ...,
        min_length=1,
        description="One or more documents to ingest. Must be non-empty.",
    )
    embedding_credentials: EmbeddingCredentials = Field(
        default_factory=EmbeddingCredentials,
        description="Request-scoped credentials for the embedding vendor.",
    )


# --- Responses ---


class AddContentResponse(BaseModel):
    """Returned immediately after the ingestion job is queued."""

    job_id: str
    status: str
    documents_total: int


class DeleteVectorsResponse(BaseModel):
    """Returned after deleting all vectors for a given source item."""

    source_item_id: str
    deleted_count: int
