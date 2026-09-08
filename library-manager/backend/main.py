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
from routers import capabilities, content, folders, importing, libraries, system
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
# Order matters for the capability routes — see routers/capabilities.py.
app.include_router(capabilities.raw_router)  # before content.router
app.include_router(capabilities.registry_router)  # /capabilities
# capabilities.item_router exposes ``/items/{id}/content/{capability}`` and
# MUST be registered before content.router so the new renderer-shaped
# capability responses (per-page JSON, image metadata JSON) take precedence
# over the legacy literal ``/content/pages`` / ``/content/images`` endpoints
# in content.router (which returned bare filename lists and broke the
# PagesRenderer / ImagesRenderer in the frontend). The legacy single-page
# route ``/content/pages/{page}`` and image-bytes route
# ``/content/images/{image_name}`` still work because they have extra
# segments the wildcard route doesn't match.
app.include_router(capabilities.item_router)  # before content.router
app.include_router(content.router)
app.include_router(folders.router)


# --- Plugin discovery ---
def _discover_plugins(package: str = "plugins") -> None:
    """Auto-discover and import every plugin module under ``package``.

    Recursively walks the package's filesystem path with ``pkgutil.iter_modules``
    and imports every non-dunder, non-private module so each plugin can
    self-register via its ``@PluginRegistry.register`` decorator. Subpackages
    are recursed into so plugin folders may use sub-directories (e.g.
    ``plugins/content_handlers/``).

    Modules are imported individually inside try/except: one broken plugin
    (missing optional dep, syntax error, etc.) must NOT prevent the rest
    from loading or block service startup.

    Skipped names:
      - ``base`` — the abstract base module, not a plugin.
      - Anything starting with ``_`` — private helpers (e.g. ``_common``).
      - ``__pycache__`` etc. — handled implicitly by ``pkgutil.iter_modules``.

    Env-var governance (``PLUGIN_{NAME}=DISABLE`` and friends) is unchanged:
    the registry decorator reads the env var keyed on the plugin's ``name``
    attribute at registration time. This function only ensures the module
    gets imported.
    """
    import importlib  # noqa: PLC0415
    import pkgutil  # noqa: PLC0415

    try:
        pkg = importlib.import_module(package)
    except Exception:
        logger.exception("Plugin package '%s' could not be imported.", package)
        return

    for _finder, name, is_pkg in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        short_name = name.rsplit(".", 1)[-1]
        if short_name.startswith("_") or short_name == "base":
            continue
        if is_pkg:
            _discover_plugins(name)
            continue
        try:
            importlib.import_module(name)
        except Exception:
            logger.warning(
                "Failed to load plugin module '%s' — skipping.",
                name,
                exc_info=True,
            )

    # Only emit the summary at the top-level call site.
    if package == "plugins":
        from plugins.base import PluginRegistry  # noqa: PLC0415

        registered = PluginRegistry.list_plugins()
        logger.info(
            "Discovered %d import plugins: %s", len(registered), [p["name"] for p in registered]
        )
