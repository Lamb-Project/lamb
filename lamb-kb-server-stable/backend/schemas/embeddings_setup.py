"""
Pydantic schemas for embeddings setup management.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class EmbeddingsSetupCreate(BaseModel):
    """Schema for creating a new embeddings setup."""
    name: str
    setup_key: str
    description: Optional[str] = None
    vendor: str
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    model_name: str
    embedding_dimensions: int
    is_default: bool = False


class EmbeddingsSetupResponse(BaseModel):
    """Schema for embeddings setup response."""
    id: int
    name: str
    setup_key: str
    vendor: str
    model_name: str
    embedding_dimensions: int
    is_default: bool
    is_active: bool
    api_key_configured: bool
    collections_count: int = 0

    class Config:
        from_attributes = True


class EmbeddingsSetupAvailable(BaseModel):
    """Schema for available embeddings setups (for collection creation)."""
    setup_key: str
    name: str
    description: Optional[str]
    model_name: str
    embedding_dimensions: int
    is_default: bool

    class Config:
        from_attributes = True


class EmbeddingsSetupUpdate(BaseModel):
    """Schema for updating an embeddings setup."""
    name: Optional[str] = None
    description: Optional[str] = None
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    vendor: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
