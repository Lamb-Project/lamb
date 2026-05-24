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
def _discover_plugins(package: str = "plugins") -> None:
    """Auto-discover and import every plugin module under ``package``.

    Recursively walks the package's filesystem path with ``pkgutil.iter_modules``
    so plugins organised into category subpackages
    (``plugins/vector_db/``, ``plugins/chunking/``, ``plugins/embedding/``,
    and any future categories) are loaded with zero code changes here — drop
    a new ``.py`` file in any of these folders and it is picked up at startup.

    Each module is imported inside its own try/except: a missing optional
    dependency (e.g. ``qdrant-client``, ``sentence-transformers``) only
    disables that single plugin instead of blocking startup. Plugins whose
    category+name env var is set to ``DISABLE`` are skipped at registration
    time by the registry decorator regardless of import success.

    Skipped names:
      - ``base`` — abstract base module, not a plugin.
      - Anything starting with ``_`` — private helpers (e.g. ``_common``).
    """
    import importlib  # noqa: PLC0415
    import pkgutil  # noqa: PLC0415

    try:
        pkg = importlib.import_module(package)
    except Exception:
        logger.exception("Plugin package '%s' could not be imported.", package)
        return

    failed: list[tuple[str, str]] = []

    for _finder, name, is_pkg in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        short_name = name.rsplit(".", 1)[-1]
        if short_name.startswith("_") or short_name == "base":
            continue
        if is_pkg:
            _discover_plugins(name)
            continue
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 — best-effort plugin discovery
            failed.append((name, f"{type(exc).__name__}: {exc}"))
            logger.warning(
                "Failed to load plugin module '%s' — skipping.",
                name,
                exc_info=True,
            )

    # Only emit the load summary at the top-level call site.
    if package != "plugins":
        return

    from plugins.base import (  # noqa: PLC0415
        ChunkingRegistry,
        EmbeddingRegistry,
        VectorDBRegistry,
    )

    embedding_names = [p["name"] for p in EmbeddingRegistry.list_plugins()]
    # Defect D4 (lifecycle 2026-05-03): emit a one-line per-category INFO
    # summary of which embedding plugins successfully registered. This makes
    # missing optional packages (e.g. the ``ollama`` extra) visible at
    # startup rather than at first request — when the failure mode is a
    # confusing 500 from /add-content. The corresponding warnings above
    # remain the source of truth for *why* a plugin failed.
    logger.info(
        "Plugin load summary — embedding loaded=%s | "
        "vector_db loaded=%s | chunking loaded=%s | failed_modules=%s",
        embedding_names,
        [p["name"] for p in VectorDBRegistry.list_plugins()],
        [p["name"] for p in ChunkingRegistry.list_plugins()],
        [name for name, _ in failed] or "none",
    )

    logger.info(
        "Discovered plugins — vector_db: %s | chunking: %s | embedding: %s",
        [p["name"] for p in VectorDBRegistry.list_plugins()],
        [p["name"] for p in ChunkingRegistry.list_plugins()],
        embedding_names,
    )
