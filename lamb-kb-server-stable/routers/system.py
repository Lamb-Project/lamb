import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from database.connection import get_db, init_databases, get_chroma_client
from database.models import Collection
from schemas.system import MessageResponse, HealthResponse, DatabaseStatusResponse, EmbeddingsConfigResponse, EmbeddingsConfigUpdate
from dependencies import verify_token
import config as config_module

router = APIRouter()


# Root endpoint with enhanced documentation
@router.get(
    "/", 
    response_model=MessageResponse,
    summary="Root endpoint",
    description="""Returns a welcome message to confirm the server is running.
    
    Example:
    ```bash
    curl -X GET 'http://localhost:9090/' \
      -H 'Authorization: Bearer 0p3n-w3bu!'
    ```
    """,
    tags=["System"],
    responses={
        200: {"description": "Successful response with welcome message"},
        401: {"description": "Unauthorized - Invalid or missing authentication token"}
    }
)
async def root(token: str = Depends(verify_token)):
    """Root endpoint that returns a welcome message.
    
    This endpoint is primarily used to verify the server is running and authentication is working correctly.
    
    Returns:
        A dictionary containing a welcome message
    """
    return {"message": "Hello World from the Lamb Knowledge Base Server!"}


# Health check endpoint
@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="""Check the health status of the server.
    
    Example:
    ```bash
    curl -X GET 'http://localhost:9090/health'
    ```
    """,
    tags=["System"],
    responses={
        200: {"description": "Server is healthy and running"}
    }
)
async def health_check():
    """Health check endpoint that does not require authentication.
    
    This endpoint can be used to verify the server is running without requiring authentication.
    
    Returns:
        A dictionary containing the server status and version
    """
    return {"status": "ok", "version": "0.1.0"}


# Database status endpoint
@router.get(
    "/database/status",
    response_model=DatabaseStatusResponse,
    summary="Database status",
    description="""Check the status of all databases.
    
    Example:
    ```bash
    curl -X GET 'http://localhost:9090/database/status' \
      -H 'Authorization: Bearer 0p3n-w3bu!'
    ```
    """,
    tags=["Database"],
    responses={
        200: {"description": "Database status information"},
        401: {"description": "Unauthorized - Invalid or missing authentication token"}
    }
)
async def database_status(token: str = Depends(verify_token), db: Session = Depends(get_db)):
    """Get the status of the SQLite and ChromaDB databases.
    
    Returns:
        A dictionary with database status information
    """
    # Re-initialize databases to get fresh status
    db_status = init_databases()
    
    # Count collections in SQLite
    collections_count = db.query(Collection).count()
    
    # Get ChromaDB collections
    chroma_client = get_chroma_client()
    chroma_collections = chroma_client.list_collections()
    
    return {
        "sqlite_status": {
            "initialized": db_status["sqlite_initialized"],
            "schema_valid": db_status["sqlite_schema_valid"],
            "errors": db_status.get("errors", [])
        },
        "chromadb_status": {
            "initialized": db_status["chromadb_initialized"],
            "collections_count": len(chroma_collections)
        },
        "collections_count": collections_count
    }


# Embeddings configuration endpoint
@router.get(
    "/config/embeddings",
    response_model=EmbeddingsConfigResponse,
    summary="Get embeddings configuration",
    description="""Get the server's default embeddings configuration.
    
Returns the default embeddings model, vendor, API endpoint, and whether an API key is configured.
The API key value is masked for security (only shows first 4 and last 4 characters).
Configuration can come from environment variables or a config file (config file takes precedence).

Example:
```bash
curl -X GET 'http://localhost:9090/config/embeddings' \
  -H 'Authorization: Bearer 0p3n-w3bu!'
```

Example Response:
```json
{
  "vendor": "openai",
  "model": "text-embedding-3-small",
  "api_endpoint": "https://api.openai.com/v1/embeddings",
  "apikey_configured": true,
  "apikey_masked": "sk-proj-********************************OuIbNA",
  "config_source": "env"
}
```
    """,
    tags=["Configuration"],
    responses={
        200: {"description": "Embeddings configuration"},
        401: {"description": "Unauthorized - Invalid or missing authentication token"}
    }
)
async def get_embeddings_config(token: str = Depends(verify_token)):
    """Get the server's default embeddings configuration.
    
    Returns the default embeddings model settings from config file or environment variables,
    with the API key masked for security.
    
    Returns:
        A dictionary containing the embeddings configuration
    """
    # Get embeddings configuration (config file overrides env vars)
    embeddings_config = config_module.get_embeddings_config()
    
    vendor = embeddings_config["vendor"]
    model = embeddings_config["model"]
    api_endpoint = embeddings_config["api_endpoint"]
    apikey = embeddings_config["apikey"]
    
    # Check if configuration is from file or env
    config_source = "file" if config_module.has_embeddings_config() else "env"
    
    # Mask the API key: show first 4 chars, 32 asterisks, last 4 chars
    apikey_masked = None
    apikey_configured = bool(apikey)
    
    if apikey and len(apikey) > 8:
        prefix = apikey[:4]
        suffix = apikey[-4:]
        apikey_masked = f"{prefix}{'*' * 32}{suffix}"
    elif apikey:
        # If key is too short, just show asterisks
        apikey_masked = "*" * len(apikey)
    
    # For non-OpenAI vendors, don't return api_endpoint unless it's customized
    if vendor.lower() in ("ollama", "local") and api_endpoint == "http://localhost:11434/api/embeddings":
        api_endpoint = None
    
    return {
        "vendor": vendor,
        "model": model,
        "api_endpoint": api_endpoint,
        "apikey_configured": apikey_configured,
        "apikey_masked": apikey_masked,
        "config_source": config_source
    }


# Update embeddings configuration endpoint
@router.put(
    "/config/embeddings",
    response_model=MessageResponse,
    summary="Update embeddings configuration",
    description="""Update the server's default embeddings configuration.
    
This overrides the environment variables and persists the configuration to a file.
Only the fields provided in the request will be updated; other fields remain unchanged.
To reset to environment variables, send an empty request body {}.

Example:
```bash
curl -X PUT 'http://localhost:9090/config/embeddings' \
  -H 'Authorization: Bearer 0p3n-w3bu!' \
  -H 'Content-Type: application/json' \
  -d '{
    "vendor": "openai",
    "model": "text-embedding-3-small",
    "api_endpoint": "https://api.openai.com/v1/embeddings",
    "apikey": "sk-proj-new-key-here"
  }'
```

Example Response:
```json
{
  "message": "Embeddings configuration updated successfully"
}
```
    """,
    tags=["Configuration"],
    responses={
        200: {"description": "Configuration updated successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication token"},
        500: {"description": "Failed to save configuration"}
    }
)
async def update_embeddings_config(
    config: EmbeddingsConfigUpdate,
    token: str = Depends(verify_token)
):
    """Update the server's default embeddings configuration.
    
    Only updates the fields that are provided (not None). The configuration
    is persisted to a file and overrides environment variables.
    
    Args:
        config: Embeddings configuration updates (all fields optional)
        
    Returns:
        A message indicating success or failure
    """
    try:
        # Update the configuration (only provided fields)
        success = config_module.update_embeddings_config(
            vendor=config.vendor,
            model=config.model,
            api_endpoint=config.api_endpoint,
            apikey=config.apikey
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to save configuration to file"
            )
        
        return {"message": "Embeddings configuration updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {str(e)}"
        )


# Reset embeddings configuration endpoint
@router.delete(
    "/config/embeddings",
    response_model=MessageResponse,
    summary="Reset embeddings configuration",
    description="""Reset the server's embeddings configuration to use environment variables.
    
This removes the persisted configuration file, causing the system to fall back to
environment variables (EMBEDDINGS_VENDOR, EMBEDDINGS_MODEL, EMBEDDINGS_ENDPOINT, EMBEDDINGS_APIKEY).

Example:
```bash
curl -X DELETE 'http://localhost:9090/config/embeddings' \
  -H 'Authorization: Bearer 0p3n-w3bu!'
```

Example Response:
```json
{
  "message": "Embeddings configuration reset to environment variables"
}
```
    """,
    tags=["Configuration"],
    responses={
        200: {"description": "Configuration reset successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication token"},
        500: {"description": "Failed to reset configuration"}
    }
)
async def reset_embeddings_config(token: str = Depends(verify_token)):
    """Reset the server's embeddings configuration to use environment variables.
    
    Removes the persisted configuration file, causing the system to fall back
    to environment variables.
    
    Returns:
        A message indicating success or failure
    """
    try:
        success = config_module.reset_embeddings_config()
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to reset configuration"
            )
        
        return {"message": "Embeddings configuration reset to environment variables"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset configuration: {str(e)}"
        ) 