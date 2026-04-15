"""Library Manager — FastAPI application entry point.

A document repository microservice that imports documents into a
structured, permalinkable markdown format. Part of the LAMB platform.

Terminology: Libraries IMPORT content. Knowledge Bases INGEST content.
"""

import logging
import sys
from contextlib import asynccontextmanager

import config
from database.connection import init_db
from fastapi import FastAPI
from routers import content, importing, libraries, system
from routers.importing import purge_stale_uploads
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
    purge_stale_uploads()
    recover_stale_jobs()
    await start_worker()
    logger.info("Library Manager started on port %d", config.PORT)

    yield

    # Shutdown
    await stop_worker()
    logger.info("Library Manager stopped")


# --- App ---
# Disable OpenAPI docs in production (LOG_LEVEL != DEBUG).
_docs_url = "/docs" if config.LOG_LEVEL == "DEBUG" else None

app = FastAPI(
    title="LAMB Library Manager",
    description=(
        "Document repository microservice. Imports documents into a "
        "structured, permalinkable markdown format."
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
app.include_router(libraries.router)
app.include_router(importing.router)
app.include_router(content.router)


# --- Plugin discovery ---
def _discover_plugins() -> None:
    """Import all plugin modules so they self-register via @PluginRegistry.register.

    Each plugin is imported individually in a try/except so that a missing
    optional dependency (e.g. markitdown) only disables its plugin instead
    of preventing the entire service from starting.
    """
    _plugin_modules = [
        "plugins.simple_import",
        "plugins.markitdown_import",
        "plugins.markitdown_plus_import",
        "plugins.url_import",
        "plugins.youtube_transcript_import",
    ]
    import importlib

    for module_name in _plugin_modules:
        try:
            importlib.import_module(module_name)
        except Exception:
            logger.warning(
                "Failed to load plugin module '%s' — skipping.",
                module_name,
                exc_info=True,
            )

    from plugins.base import PluginRegistry
    registered = PluginRegistry.list_plugins()
    logger.info("Discovered %d import plugins: %s",
                len(registered), [p["name"] for p in registered])
