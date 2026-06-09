"""Pydantic schemas for ingestion job status."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobStatusResponse(BaseModel):
    """Full view of an ingestion job row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    collection_id: str
    status: str
    documents_total: int
    documents_processed: int
    chunks_created: int
    error_message: str | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
