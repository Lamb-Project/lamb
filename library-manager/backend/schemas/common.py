"""Shared Pydantic schemas used across multiple routers."""

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    limit: int = Field(20, ge=1, le=100, description="Max items to return.")
    offset: int = Field(0, ge=0, description="Number of items to skip.")


class MessageResponse(BaseModel):
    """Generic response carrying a human-readable message."""

    message: str
