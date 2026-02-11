import os
import uvicorn


def _uvicorn_log_level() -> str:
    level = os.getenv("KB_LOG_LEVEL", os.getenv("GLOBAL_LOG_LEVEL", "WARNING"))
    # Uvicorn accepts lower-case level names.
    return str(level).strip().lower() or "warning"


def _uvicorn_access_log_enabled() -> bool:
    val = os.getenv("UVICORN_ACCESS_LOG", "false").strip().lower()
    return val in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9090,
        reload=True,
        log_level=_uvicorn_log_level(),
        access_log=_uvicorn_access_log_enabled(),
    )
