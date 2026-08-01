"""LAMB KB Server — FastAPI application entry point.

A pluggable knowledge-base microservice that chunks, embeds, and stores
vectors for LAMB. Designed as a pure computation service: LAMB owns access
control, org configuration, and library content delivery; this server
receives text + permalinks + credentials and produces searchable vectors.

Terminology: Libraries IMPORT content. Knowledge Bases INGEST content.

The server runs on port 9092 (distinct from the legacy
``lamb-kb-server-stable/`` on 9090) so both can coexist — see ADR-2.
"""

import logging
import sys
from contextlib import asynccontextmanager

import config
from database.connection import init_db
from fastapi import FastAPI
from routers import collections, content, jobs, query, system
from tasks.worker import recover_stale_jobs, start_worker, stop_worker

# --- Logging ---
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# --- Startup checks ---
if not config.LAMB_API_TOKEN:
    logger.critical("LAMB_API_TOKEN is not set. Refusing to start.")
    sys.exit(1)


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the application."""
    # Startup
    config.ensure_directories()
    init_db()
    _discover_plugins()
    recover_stale_jobs()
    await start_worker()
    logger.info("LAMB KB Server started on port %d", config.PORT)

    yield

    # Shutdown
    await stop_worker()
    logger.info("LAMB KB Server stopped")


# --- App ---
# Disable OpenAPI docs in production (LOG_LEVEL != DEBUG).
_docs_url = "/docs" if config.LOG_LEVEL == "DEBUG" else None

app = FastAPI(
    title="LAMB KB Server",
    description=(
        "Knowledge base microservice. Handles chunking, embedding, and "
        "vector storage. Receives content + permalinks from LAMB — does "
        "not call the Library Manager directly."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=None,
)


# --- Request logging ---
@app.middleware("http")
async def log_requests(request, call_next):
    """Log every request with method, path, status, and duration."""
    import time  # noqa: PLC0415

    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "%s %s → %d (%dms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# --- Routers ---
app.include_router(system.router)
app.include_router(collections.router)
app.include_router(content.router)
app.include_router(query.router)
app.include_router(jobs.router)


# --- Plugin discovery ---
def _discover_plugins() -> None:
    """Import all plugin modules so they self-register.

    Each plugin module is imported inside a try/except so a missing optional
    dependency (e.g. ``qdrant-client``, ``sentence-transformers``) only
    disables that particular plugin instead of preventing startup.

    Plugins whose category+name env var is set to ``DISABLE`` are skipped
    at registration time regardless of whether their deps are importable.
    """
    _plugin_modules = [
        # Vector DB backends
        "plugins.vector_db.chromadb_backend",
        "plugins.vector_db.qdrant_backend",
        # Chunking strategies
        "plugins.chunking.simple",
        "plugins.chunking.hierarchical",
        "plugins.chunking.by_page",
        "plugins.chunking.by_section",
        # Embedding vendors
        "plugins.embedding.openai",
        "plugins.embedding.ollama",
        "plugins.embedding.local",
    ]
    import importlib  # noqa: PLC0415

    for module_name in _plugin_modules:
        try:
            importlib.import_module(module_name)
        except Exception:
            logger.warning(
                "Failed to load plugin module '%s' — skipping.",
                module_name,
                exc_info=True,
            )

    from plugins.base import (  # noqa: PLC0415
        ChunkingRegistry,
        EmbeddingRegistry,
        VectorDBRegistry,
    )

    logger.info(
        "Discovered plugins — vector_db: %s | chunking: %s | embedding: %s",
        [p["name"] for p in VectorDBRegistry.list_plugins()],
        [p["name"] for p in ChunkingRegistry.list_plugins()],
        [p["name"] for p in EmbeddingRegistry.list_plugins()],
    )
