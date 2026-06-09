"""System endpoints: health check and plugin capability listings."""

import logging

from database.connection import get_session_direct
from dependencies import verify_token
from fastapi import APIRouter, Depends
from plugins.base import ChunkingRegistry, EmbeddingRegistry, VectorDBRegistry
from sqlalchemy import text
from tasks.worker import is_worker_running

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


@router.get("/health")
async def health() -> dict:
    """Health check endpoint.

    Does NOT require authentication so monitoring systems can reach it
    without a service token.

    Checks:
        - Database connectivity (``SELECT 1``).
        - Worker loop running status.

    Returns:
        Service status, version, and per-component health.
    """
    db_ok = False
    try:
        db = get_session_direct()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        db_ok = True
    except Exception:
        logger.exception("Health check: database connectivity failed")

    worker_ok = is_worker_running()

    overall = "ok" if (db_ok and worker_ok) else "degraded"
    return {
        "status": overall,
        "service": "kb-server",
        "version": "1.0.0",
        "checks": {
            "database": "ok" if db_ok else "error",
            "worker": "ok" if worker_ok else "error",
        },
    }


@router.get("/backends", dependencies=[Depends(verify_token)])
async def list_backends() -> dict:
    """List all registered vector DB backends with their parameter schemas.

    Returns:
        Dict with ``backends`` list.
    """
    return {"backends": VectorDBRegistry.list_plugins()}


@router.get("/chunking-strategies", dependencies=[Depends(verify_token)])
async def list_chunking_strategies() -> dict:
    """List all registered chunking strategies with their parameter schemas.

    Returns:
        Dict with ``strategies`` list.
    """
    return {"strategies": ChunkingRegistry.list_plugins()}


@router.get("/embedding-vendors", dependencies=[Depends(verify_token)])
async def list_embedding_vendors() -> dict:
    """List all registered embedding vendors with their parameter schemas.

    Returns:
        Dict with ``vendors`` list.
    """
    return {"vendors": EmbeddingRegistry.list_plugins()}
