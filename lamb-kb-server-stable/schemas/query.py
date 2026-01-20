"""
Schemas for query requests and responses.

This module defines Pydantic models for query operations.
"""

from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Query request schema."""
    
    query_text: str = Field(..., description="Text to query for")
    top_k: int = Field(5, description="Number of results to return")
    threshold: float = Field(0.0, description="Minimum similarity threshold (0-1)")
    plugin_params: Dict[str, Any] = Field(default_factory=dict, description="Additional plugin-specific parameters")


class QueryResult(BaseModel):
    """Single query result item."""
    
    similarity: float = Field(..., description="Similarity score (0-1)")
    data: str = Field(..., description="Document content")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")


class QueryResponse(BaseModel):
    """Query response schema."""
    
    results: List[QueryResult] = Field(..., description="List of query results")
    count: int = Field(..., description="Number of results returned")
    timing: Dict[str, float] = Field(..., description="Timing information for the query")
    query: str = Field(..., description="Original query text")


class QueryPluginInfo(BaseModel):
    """Information about a query plugin."""
    
    name: str = Field(..., description="Plugin name")
    description: str = Field(..., description="Plugin description")
    parameters: Dict[str, Dict[str, Any]] = Field(..., description="Plugin parameters")
