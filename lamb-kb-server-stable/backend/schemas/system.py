from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

# Response models
class HealthResponse(BaseModel):
    """Model for health check responses"""
    status: str = Field(..., description="Status of the server", example="ok")
    version: str = Field(..., description="Server version", example="0.1.0")

class MessageResponse(BaseModel):
    """Model for basic message responses"""
    message: str = Field(..., description="Response message", example="Hello World from the Lamb Knowledge Base Server!")

class DatabaseStatusResponse(BaseModel):
    """Model for database status response"""
    sqlite_status: Dict[str, Any] = Field(..., description="Status of SQLite database")
    chromadb_status: Dict[str, Any] = Field(..., description="Status of ChromaDB database")
    collections_count: int = Field(..., description="Number of collections") 

class EmbeddingsConfigResponse(BaseModel):
    """Model for embeddings configuration response"""
    vendor: str = Field(..., description="Default embeddings vendor (e.g., 'ollama', 'local', 'openai')")
    model: str = Field(..., description="Default embeddings model name")
    api_endpoint: Optional[str] = Field(None, description="Default embeddings API endpoint")
    apikey_configured: bool = Field(..., description="Whether an API key is configured")
    apikey_masked: Optional[str] = Field(None, description="Masked API key (prefix + **** + suffix)")
    config_source: str = Field(..., description="Source of configuration: 'file' or 'env'")

class EmbeddingsConfigUpdate(BaseModel):
    """Model for updating embeddings configuration"""
    vendor: Optional[str] = Field(None, description="Embeddings vendor (e.g., 'ollama', 'local', 'openai')")
    model: Optional[str] = Field(None, description="Model name")
    api_endpoint: Optional[str] = Field(None, description="API endpoint URL")
    apikey: Optional[str] = Field(None, description="API key for the embeddings service") 