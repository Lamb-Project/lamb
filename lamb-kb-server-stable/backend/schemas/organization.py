"""
Pydantic schemas for organization management.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class OrganizationCreate(BaseModel):
    """Schema for creating or updating an organization."""
    external_id: str
    name: str


class OrganizationResponse(BaseModel):
    """Schema for organization response."""
    id: int
    external_id: str
    name: str
    created_at: datetime
    setups_count: Optional[int] = 0
    collections_count: Optional[int] = 0

    class Config:
        from_attributes = True
