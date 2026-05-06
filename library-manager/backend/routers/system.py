"""System endpoints: health check and plugin listing."""

from database.connection import get_session_direct
from dependencies import verify_token
from fastapi import APIRouter, Depends
from plugins.base import PluginRegistry
from sqlalchemy import text
from tasks.worker import is_worker_running

router = APIRouter(tags=["System"])


@router.get("/health")
async def health() -> dict:
    """Health check endpoint.

    Verifies database connectivity and worker status in addition to
    basic HTTP liveness.

    Returns:
        Service status, version, and component health.
    """
    db_ok = False
    try:
        db = get_session_direct()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        pass

    worker_ok = is_worker_running()

    status = "ok" if (db_ok and worker_ok) else "degraded"
    return {
        "status": status,
        "service": "library-manager",
        "version": "1.0.0",
        "checks": {
            "database": "ok" if db_ok else "error",
            "worker": "ok" if worker_ok else "error",
        },
    }


@router.get("/plugins", dependencies=[Depends(verify_token)])
async def list_plugins() -> dict:
    """List all registered import plugins with their parameters.

    Returns:
        Dict containing the list of available plugins.
    """
    return {"plugins": PluginRegistry.list_plugins()}
