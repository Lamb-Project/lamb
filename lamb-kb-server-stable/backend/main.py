import os
import json
from typing import Dict, Any, List, Optional

import logging
import sys


# --- Logging configuration ---
_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
_effective_level = os.getenv("KB_LOG_LEVEL", os.getenv("GLOBAL_LOG_LEVEL", "WARNING")).upper().strip()
if _effective_level not in _LOG_LEVELS:
    _effective_level = "WARNING"

logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, _effective_level),
    format="%(levelname)s: %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger("lamb-kb")

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load the environment variables from .env file
    load_dotenv()
    logger.debug("Environment variables loaded from .env file")
    logger.debug("EMBEDDINGS_VENDOR=%s", os.getenv("EMBEDDINGS_VENDOR"))
    logger.debug("EMBEDDINGS_MODEL=%s", os.getenv("EMBEDDINGS_MODEL"))
except ImportError:
    logger.warning("python-dotenv not installed; environment variables must be set manually")

from fastapi import Depends, FastAPI, HTTPException, status, Query, File, Form, UploadFile, BackgroundTasks
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Database imports
from database.connection import init_databases, get_db, get_chroma_client
from database.models import Visibility, FileRegistry, FileStatus
from database.service import CollectionService
from schemas.collection import (
    CollectionUpdate,
    EmbeddingsModel
)

# Import ingestion modules
from plugins.base import discover_plugins
from services.ingestion import IngestionService
from services.query import QueryService
from schemas.ingestion import (
    IngestionPluginInfo,
    IngestFileResponse,
    IngestURLResponse,
)

# Import query modules
from schemas.query import (
    QueryPluginInfo
)

# Get API key from environment variable or use default
API_KEY = os.getenv("LAMB_API_KEY", "0p3n-w3bu!")

# Get default embeddings model configuration from environment variables
# Default to using Ollama with nomic-embed-text model
# For OpenAI models, the environment variables should be set accordingly
DEFAULT_EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "nomic-embed-text")
DEFAULT_EMBEDDINGS_VENDOR = os.getenv("EMBEDDINGS_VENDOR", "ollama")  # 'ollama', 'local', or 'openai'
DEFAULT_EMBEDDINGS_APIKEY = os.getenv("EMBEDDINGS_APIKEY", "")
# Default endpoint for Ollama
DEFAULT_EMBEDDINGS_ENDPOINT = os.getenv("EMBEDDINGS_ENDPOINT", "http://localhost:11434/api/embeddings")

# Initialize FastAPI app with detailed documentation
app = FastAPI(
    title="Lamb Knowledge Base Server",
    description="""A dedicated knowledge base server designed to provide robust vector database functionality 
    for the LAMB project and to serve as a Model Context Protocol (MCP) server.
    
    ## Authentication
    
    All API endpoints are secured with Bearer token authentication. The token must match 
    the `LAMB_API_KEY` environment variable (default: `0p3n-w3bu!`).
    
    Example:
    ```
    curl -H 'Authorization: Bearer 0p3n-w3bu!' http://localhost:9090/
    ```
    
    ## Features
    
    - Knowledge base management for LAMB Learning Assistants
    - Vector database services using ChromaDB
    - API access for the LAMB project
    - Model Context Protocol (MCP) compatibility
    """,
    version="0.1.0",
    contact={
        "name": "LAMB Project Team",
    },
    license_info={
        "name": "GNU General Public License v3.0",
        "url": "https://www.gnu.org/licenses/gpl-3.0.en.html"
    },
)

# Import shared dependencies
from dependencies import verify_token

# Import routers
from routers import system, collections
from routers import ingestion_status

# Initialize databases on startup
@app.on_event("startup")
async def startup_event():
    """Initialize databases and perform sanity checks on startup."""
    logger.info("Initializing databases...")
    init_status = init_databases()
    
    if init_status["errors"]:
        for error in init_status["errors"]:
            logger.error("%s", error)
    else:
        logger.info("Databases initialized successfully.")
    
    # Run database migrations
    logger.info("Checking database migrations...")
    try:
        from database.migrations.migration_add_ingestion_tracking import check_migration_status, run_migration
        migration_status = check_migration_status()
        if not migration_status.get("applied"):
            logger.info("Running migration: Add Ingestion Tracking Fields...")
            run_migration()
            logger.info("Migration completed.")
        else:
            logger.info("All migrations up to date.")
    except Exception as e:
        logger.warning("Migration check failed: %s", e)
    
    # Discover ingestion plugins
    logger.info("Discovering ingestion plugins...")
    discover_plugins("plugins")
    logger.info("Found %d ingestion plugins", len(IngestionService.list_plugins()))
    
    # Ensure static directory exists
    IngestionService._ensure_dirs()

# Include routers
app.include_router(system.router)
app.include_router(collections.router)
app.include_router(ingestion_status.router)

# Configure static files
static_dir = IngestionService.STATIC_DIR
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Add CORS middleware
# Minimal CORS: wildcard origins, no credentials (so '*' is valid with browsers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # allow_credentials omitted (defaults False)
)


# Ingestion Plugin Endpoints

@app.get(
    "/config/ingestion",
    summary="Get ingestion configuration",
    description="""Get configuration values for ingestion monitoring.
    
    Returns configuration such as:
    - refresh_rate: How often (in seconds) the frontend should poll job status
    
    Example:
    ```bash
    curl -X GET 'http://localhost:9090/config/ingestion'
    ```
    """,
    tags=["Configuration"],
    responses={
        200: {"description": "Configuration values"}
    }
)
async def get_ingestion_config():
    """Get ingestion configuration values.
    
    Returns:
        Dictionary with configuration values
    """
    return {
        "refresh_rate": int(os.getenv("INGESTION_JOB_REFRESH_RATE", "3"))
    }


@app.get(
    "/ingestion/plugins",
    response_model=List[IngestionPluginInfo],
    summary="List ingestion plugins",
    description="""List all available document ingestion plugins.
    
    Example:
    ```bash
    curl -X GET 'http://localhost:9090/ingestion/plugins' \
      -H 'Authorization: Bearer 0p3n-w3bu!'
    ```
    """,
    tags=["Ingestion"],
    responses={
        200: {"description": "List of available ingestion plugins"},
        401: {"description": "Unauthorized - Invalid or missing authentication token"}
    }
)
async def list_ingestion_plugins(token: str = Depends(verify_token)):
    """List all available document ingestion plugins.
    
    Returns:
        List of plugin information objects
    """
    return IngestionService.list_plugins()



@app.get(
    "/files/{file_id}/content",
    summary="Get file content",
    description="Get the content of a file from the collection",
    tags=["Files"],
    responses={
        200: {"description": "File content retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication token"},
        404: {"description": "File not found"},
        500: {"description": "Server error"}
    }
)
async def get_file_content(
    file_id: int,
    token: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get the content of a file."""
    from services.collections import CollectionsService
    
    try:
        return CollectionsService.get_file_content(file_id, db)
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        print(f"Error retrieving file content: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve file content: {str(e)}"
        )
