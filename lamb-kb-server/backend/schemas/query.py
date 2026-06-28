"""Pydantic schemas for vector similarity queries."""

from typing import Any

from pydantic import BaseModel, Field

from schemas.content import EmbeddingCredentials


class QueryRequest(BaseModel):
    """Body for ``POST /collections/{collection_id}/query``."""

    query_text: str = Field(..., min_length=1, description="Text to search for.")
    top_k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum number of results to return.",
    )
    embedding_credentials: EmbeddingCredentials = Field(
        default_factory=EmbeddingCredentials,
        description="Request-scoped credentials for the embedding vendor.",
    )


class QueryResultItem(BaseModel):
    """One result from a similarity search."""

    text: str
    score: float = Field(..., description="Cosine similarity score in [0, 1].")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Chunk metadata including source_item_id and permalink URLs.",
    )


class QueryResponse(BaseModel):
    """Response body for a query request."""

    results: list[QueryResultItem]
    query: str
    top_k: int
