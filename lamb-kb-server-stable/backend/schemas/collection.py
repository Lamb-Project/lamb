"""
Pydantic schemas for Collection API.

This module defines the request and response models for the Collection API endpoints.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field


class EmbeddingsModel(BaseModel):
    """Schema for embeddings model configuration (internal use, includes sensitive data)."""
    model: str = Field(..., description="Name or path of the embeddings model")
    vendor: str = Field(..., description="Vendor of the embeddings model (e.g., 'ollama', 'local', 'openai')")
    api_endpoint: Optional[str] = Field(None, description="Custom API endpoint URL")
    apikey: Optional[str] = Field(None, description="API key for the endpoint if required")


class EmbeddingsModelSafe(BaseModel):
    """Schema for embeddings model response (SAFE - no API keys exposed to frontend)."""
    model: str = Field(..., description="Name or path of the embeddings model")
    vendor: str = Field(..., description="Vendor of the embeddings model (e.g., 'ollama', 'local', 'openai')")
    api_endpoint: Optional[str] = Field(None, description="Custom API endpoint URL")
    apikey_configured: bool = Field(False, description="Whether an API key is configured (key value hidden)")


class CollectionBase(BaseModel):
    """Base schema for collections."""
    name: str = Field(..., description="Name of the collection", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Optional description of the collection")
    visibility: str = Field("private", description="Visibility setting ('private' or 'public')")


class CollectionCreate(CollectionBase):
    """Schema for creating a new collection."""
    owner: str = Field(..., description="Owner of the collection")
    embeddings_model: Optional[EmbeddingsModel] = Field(
        None, 
        description="Optional custom embeddings model configuration"
    )


class CollectionUpdate(BaseModel):
    """Schema for updating an existing collection."""
    name: Optional[str] = Field(None, description="New name of the collection", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="New description of the collection")
    visibility: Optional[str] = Field(None, description="New visibility setting ('private' or 'public')")
    embeddings_model: Optional[EmbeddingsModel] = Field(
        None, 
        description="New embeddings model configuration"
    )


class CollectionResponse(CollectionBase):
    """Schema for collection response (SAFE - uses EmbeddingsModelSafe, no API keys exposed)."""
    id: int = Field(..., description="Unique identifier of the collection")
    owner: str = Field(..., description="Owner of the collection")
    creation_date: datetime = Field(..., description="Creation date of the collection")
    embeddings_model: EmbeddingsModelSafe = Field(..., description="Embeddings model configuration (API key hidden)")

    class Config:
        """Pydantic config for collection response."""
        from_attributes = True


class CollectionList(BaseModel):
    """Schema for list of collections response (SAFE - no API keys exposed)."""
    total: int = Field(..., description="Total number of collections matching filters")
    items: List[CollectionResponse] = Field(..., description="List of collections")


# Schema for the response when creating a collection (just the ID)
class CollectionCreateResponse(BaseModel):
    """Response schema when creating a collection, returning only the ID."""
    id: int = Field(..., description="Unique identifier of the newly created collection")
