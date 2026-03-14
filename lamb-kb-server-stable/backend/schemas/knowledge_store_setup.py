"""
Pydantic schemas for knowledge store setup management.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any


class KnowledgeStoreSetupCreate(BaseModel):
    """Schema for creating a new knowledge store setup."""
    name: str
    setup_key: str
    description: Optional[str] = None
    plugin_type: str = "chromadb"
    plugin_config: Optional[Dict[str, Any]] = None
    # Legacy shorthand fields (used to build plugin_config for chromadb)
    vendor: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    is_default: bool = False


class KnowledgeStoreSetupResponse(BaseModel):
    """Schema for knowledge store setup response."""
    id: int
    name: str
    setup_key: str
    plugin_type: str
    plugin_config_summary: Optional[Dict[str, Any]] = None
    is_default: bool
    is_active: bool
    api_key_configured: bool
    collections_count: int = 0

    class Config:
        from_attributes = True


class KnowledgeStoreSetupAvailable(BaseModel):
    """Schema for available setups (for collection creation)."""
    setup_key: str
    name: str
    description: Optional[str]
    plugin_type: str
    is_default: bool

    class Config:
        from_attributes = True


class KnowledgeStoreSetupUpdate(BaseModel):
    """Schema for updating a knowledge store setup."""
    name: Optional[str] = None
    description: Optional[str] = None
    plugin_config: Optional[Dict[str, Any]] = None
    # Legacy shorthand fields
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    vendor: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
