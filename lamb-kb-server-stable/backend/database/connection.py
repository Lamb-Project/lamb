"""
Database connection module for SQLite and ChromaDB.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Union, Callable

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction, OllamaEmbeddingFunction
from sqlalchemy import create_engine, inspect, text, event
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Collection, Visibility

# Database paths
DATA_DIR = Path(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))) / "data"
SQLITE_DB_PATH = DATA_DIR / "lamb-kb-server.db"
CHROMA_DB_PATH = DATA_DIR / "chromadb"

# Ensure the directories exist
DATA_DIR.mkdir(exist_ok=True)
CHROMA_DB_PATH.mkdir(exist_ok=True)

# Create SQLite engine
SQLALCHEMY_DATABASE_URL = f"sqlite:///{SQLITE_DB_PATH}"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=20,        # Increased from default 5 to support higher concurrency
    max_overflow=30,     # Increased from default 10 to support 50+ concurrent requests
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600    # Recycle connections after 1 hour
)

# Enable WAL mode for better concurrency
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL mode and other optimizations for SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
    cursor.execute("PRAGMA cache_size=-64000")   # 64MB cache
    cursor.execute("PRAGMA temp_store=MEMORY")   # Store temp tables in memory
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create ChromaDB client
chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH),
    settings=ChromaSettings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)


def get_embedding_function_by_params(vendor: str, model_name: str, api_key: str = "", api_endpoint: str = ""):
    """Get an embedding function based on vendor and model parameters."""
    vendor = vendor.lower()

    if vendor in ("ollama", "local"):
        return OllamaEmbeddingFunction(
            url=api_endpoint or "http://localhost:11434",
            model_name=model_name
        )

    elif vendor == "openai":
        # Fall back to EMBEDDINGS_APIKEY from .env if api_key is not provided
        if not api_key:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("EMBEDDINGS_APIKEY", "")

        kwargs = {"api_key": api_key, "model_name": model_name}
        if api_endpoint:
            # If api_endpoint ends with '/embeddings', strip it for OpenAIEmbeddingFunction
            if api_endpoint.endswith("/embeddings"):
                api_endpoint = api_endpoint[:-len("/embeddings")]
            kwargs["api_base"] = api_endpoint
        return OpenAIEmbeddingFunction(**kwargs)

    else:
        raise ValueError(f"Unsupported embedding vendor: {vendor}")


def get_db() -> Session:
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_chroma_client() -> chromadb.PersistentClient:
    """Get the ChromaDB client."""
    return chroma_client


def init_sqlite_db() -> None:
    """Initialize the SQLite database."""
    Base.metadata.create_all(bind=engine)


def get_embedding_function(collection_id_or_obj: Union[int, Collection, Dict[str, Any]]) -> Callable:
    """
    Get the embedding function for a collection.
    Handles both old mode (inline config) and new mode (setup reference).
    """
    from .models import EmbeddingsSetup

    db = next(get_db())

    try:
        # Resolve to Collection object
        if isinstance(collection_id_or_obj, dict):
            # Check if dict has embeddings_model directly
            if 'embeddings_model' in collection_id_or_obj and collection_id_or_obj['embeddings_model']:
                embedding_config = collection_id_or_obj['embeddings_model']
                return get_embedding_function_by_params(
                    embedding_config.get("vendor"),
                    embedding_config.get("model"),
                    embedding_config.get("apikey"),
                    embedding_config.get("api_endpoint")
                )
            # Otherwise fetch collection from DB
            collection_id = collection_id_or_obj.get('id')
            if not collection_id:
                raise ValueError("Collection dictionary must contain an 'id' field")
            collection = db.query(Collection).filter(Collection.id == collection_id).first()
        elif isinstance(collection_id_or_obj, Collection):
            collection = collection_id_or_obj
        elif isinstance(collection_id_or_obj, int):
            collection = db.query(Collection).filter(Collection.id == collection_id_or_obj).first()
        else:
            raise ValueError(f"Expected Collection object, dictionary or ID")

        if not collection:
            raise ValueError(f"Collection not found")

        # Check if using NEW MODE (setup reference)
        if hasattr(collection, 'embeddings_setup_id') and collection.embeddings_setup_id:
            # NEW MODE: Get config from setup
            setup = db.query(EmbeddingsSetup).filter(EmbeddingsSetup.id == collection.embeddings_setup_id).first()
            if not setup:
                raise ValueError(f"Embeddings setup {collection.embeddings_setup_id} not found")

            # Decrypt API key if encrypted
            from utils.encryption import decrypt_api_key
            decrypted_key = decrypt_api_key(setup.api_key) if setup.api_key else ""
            
            return get_embedding_function_by_params(
                vendor=setup.vendor,
                model_name=setup.model_name,
                api_key=decrypted_key,
                api_endpoint=setup.api_endpoint or ""
            )
        else:
            # OLD MODE: Use inline config
            if not collection.embeddings_model:
                raise ValueError(f"Collection has no embeddings configuration")

            embedding_config = json.loads(collection.embeddings_model) if isinstance(
                collection.embeddings_model, str) else collection.embeddings_model

            return get_embedding_function_by_params(
                embedding_config.get("vendor"),
                embedding_config.get("model"),
                embedding_config.get("apikey"),
                embedding_config.get("api_endpoint")
            )

    finally:
        db.close()


def check_sqlite_schema() -> bool:
    """Check if the SQLite database schema is compatible."""
    inspector = inspect(engine)

    if "collections" not in inspector.get_table_names():
        return True

    collection_columns = {col["name"]
                          for col in inspector.get_columns("collections")}
    required_columns = {"id", "name", "description",
                        "creation_date", "owner", "visibility", "embeddings_model"}

    return required_columns.issubset(collection_columns)


def run_migrations() -> Dict[str, Any]:
    """
    Run database migrations to add new columns.

    This function safely adds new columns to existing tables without
    affecting existing data. It checks if columns exist before adding them.

    Returns:
        Dictionary with migration results and any errors
    """
    migration_results = {
        "migrations_run": [],
        "errors": []
    }

    inspector = inspect(engine)

    # Check if file_registry table exists
    if "file_registry" not in inspector.get_table_names():
        return migration_results  # Table will be created by create_all()

    # Get existing columns in file_registry
    existing_columns = {col["name"]
                        for col in inspector.get_columns("file_registry")}

    # Migration: Add processing_stats column (Jan 2026)
    if "processing_stats" not in existing_columns:
        try:
            with engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE file_registry ADD COLUMN processing_stats TEXT DEFAULT NULL"
                ))
                conn.commit()
            migration_results["migrations_run"].append({
                "migration": "add_processing_stats_column",
                "table": "file_registry",
                "status": "success",
                "description": "Added processing_stats JSON column for detailed ingestion statistics"
            })
            print(
                "INFO: [migration] Added processing_stats column to file_registry table")
        except Exception as e:
            error_msg = f"Failed to add processing_stats column: {str(e)}"
            migration_results["errors"].append(error_msg)
            print(f"ERROR: [migration] {error_msg}")

    return migration_results


def init_databases() -> Dict[str, Any]:
    """Initialize all databases and perform sanity checks.

    This function:
    1. Checks schema compatibility
    2. Creates tables if they don't exist
    3. Runs any pending migrations
    4. Initializes ChromaDB

    Returns:
        Dictionary with initialization status and any errors
    """
    status = {
        "sqlite_initialized": False,
        "sqlite_schema_valid": False,
        "chromadb_initialized": False,
        "migrations": {},
        "errors": []
    }

    try:
        status["sqlite_schema_valid"] = check_sqlite_schema()

        if not status["sqlite_schema_valid"]:
            status["errors"].append("SQLite schema is not compatible")

        # Create tables first
        init_sqlite_db()
        status["sqlite_initialized"] = True

        # Run migrations after tables exist
        migration_results = run_migrations()
        status["migrations"] = migration_results
        if migration_results.get("errors"):
            status["errors"].extend(migration_results["errors"])

        status["chromadb_collections"] = len(chroma_client.list_collections())
        status["chromadb_initialized"] = True

        # Log migration summary
        if migration_results.get("migrations_run"):
            print(
                f"INFO: [init] Ran {len(migration_results['migrations_run'])} database migrations")

    except Exception as e:
        status["errors"].append(f"Error initializing databases: {str(e)}")

    return status
