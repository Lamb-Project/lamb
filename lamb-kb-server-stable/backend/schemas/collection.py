"""
Pydantic schemas for Collection API.

This module defines the request and response models for the Collection API endpoints.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, model_validator


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
    """Schema for creating a new collection.

    Supports DUAL MODE:
    - OLD MODE: Provide embeddings_model (inline configuration)
    - NEW MODE: Provide organization_external_id + optional embeddings_setup_key
    - DEFAULT MODE: Provide neither (creates default setup from env vars)
    
    VALIDATION: Cannot specify both OLD MODE and NEW MODE simultaneously.
    """
    owner: str = Field(..., description="Owner of the collection")

    # OLD MODE: Inline embeddings configuration (backward compatibility)
    embeddings_model: Optional[EmbeddingsModel] = Field(
        None,
        description="Optional custom embeddings model configuration (OLD MODE)"
    )

    # NEW MODE: Organization and setup reference
    organization_external_id: Optional[str] = Field(
        None,
        description="Organization external ID (NEW MODE)"
    )
    embeddings_setup_key: Optional[str] = Field(
        None,
        description="Embeddings setup key (NEW MODE, optional - uses default if omitted)"
    )
    
    @model_validator(mode='after')
    def validate_mode_exclusivity(self):
        """Ensure OLD MODE and NEW MODE are mutually exclusive."""
        has_old_mode = self.embeddings_model is not None
        has_new_mode = self.organization_external_id is not None
        
        if has_old_mode and has_new_mode:
            raise ValueError(
                "Cannot specify both embeddings_model (OLD MODE) and "
                "organization_external_id (NEW MODE). Choose one mode or the other."
            )
        return self


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
    """Schema for collection response (SAFE - uses EmbeddingsModelSafe, no API keys exposed).

    CRITICAL: embeddings_model field is ALWAYS present for backward compatibility.
    For collections using NEW MODE, embeddings_model is synthesized from the setup.
    """
    id: int = Field(..., description="Unique identifier of the collection")
    owner: str = Field(..., description="Owner of the collection")
    creation_date: datetime = Field(..., description="Creation date of the collection")
    embeddings_model: EmbeddingsModelSafe = Field(..., description="Embeddings model configuration (API key hidden)")

    # NEW MODE fields (optional)
    embeddings_setup: Optional[Dict[str, Any]] = Field(None, description="Embeddings setup reference (if using NEW MODE)")
    organization_id: Optional[int] = Field(None, description="Organization ID (if using NEW MODE)")

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


class EmbeddingsModelPartial(BaseModel):
    """Schema for partial embeddings model updates (all fields optional)."""
    model: Optional[str] = Field(None, description="Name or path of the embeddings model")
    vendor: Optional[str] = Field(None, description="Vendor of the embeddings model (e.g., 'ollama', 'local', 'openai')")
    api_endpoint: Optional[str] = Field(None, description="Custom API endpoint URL")
    apikey: Optional[str] = Field(None, description="API key for the endpoint if required")


class BulkUpdateEmbeddingsRequest(BaseModel):
    """Schema for bulk updating embeddings API key for all collections of an owner."""
    embeddings_model: EmbeddingsModelPartial = Field(
        ...,
        description="New embeddings model configuration (only apikey will be updated)"
    )


class BulkUpdateEmbeddingsResponse(BaseModel):
    """Schema for bulk update response."""
    total: int = Field(..., description="Total number of collections for the owner")
    updated: int = Field(..., description="Number of collections successfully updated")
    failed: int = Field(..., description="Number of collections that failed to update")
    collections: List[Dict[str, Any]] = Field(..., description="List of updated collection IDs and names")
    error: Optional[str] = Field(None, description="Error message if the operation failed")
