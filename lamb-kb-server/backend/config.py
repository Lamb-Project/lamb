"""Application configuration loaded from environment variables.

All configuration is centralized here. Other modules import from this file
rather than reading os.environ directly.

The KB Server has three distinct plugin families (vector DBs, chunking
strategies, embedding vendors), each gated by a simple ENABLE/DISABLE env
var. Defaults are ENABLE for everything that has its dependencies installed;
plugin registration is skipped gracefully for anything that fails to import.
"""

import os
from pathlib import Path

# --- Server ---
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "9092"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# --- Authentication ---
# Single bearer token that LAMB sends with every request.
# If it matches, the request is trusted entirely.
LAMB_API_TOKEN: str = os.getenv("LAMB_API_TOKEN", "")

# --- Storage ---
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
# Vector stores live under DATA_DIR/storage/{org_id}/{collection_id}/ so each
# organization is isolated at the filesystem level (ADR-9).
STORAGE_DIR: Path = DATA_DIR / "storage"
DB_PATH: Path = DATA_DIR / "kb-server.db"

# --- Task processing ---
MAX_CONCURRENT_INGESTIONS: int = int(os.getenv("MAX_CONCURRENT_INGESTIONS", "3"))
INGESTION_TASK_TIMEOUT_SECONDS: int = int(
    os.getenv("INGESTION_TASK_TIMEOUT_SECONDS", "1800")
)
MAX_EMBED_CHARS: int = int(os.getenv("MAX_EMBED_CHARS", "30000"))
RESPLIT_CHUNK_SIZE: int = int(os.getenv("RESPLIT_CHUNK_SIZE", "4000"))
RESPLIT_OVERLAP: int = 200
MAX_JOB_ATTEMPTS: int = int(os.getenv("KB_MAX_JOB_ATTEMPTS", "3"))

# --- Payload limits ---
# Hard cap on add-content request bodies. Default 200 MB.
MAX_REQUEST_SIZE_BYTES: int = int(
    os.getenv("MAX_REQUEST_SIZE_BYTES", str(200 * 1024 * 1024))
)

# --- Qdrant (optional backend) ---
QDRANT_URL: str = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")


def ensure_directories() -> None:
    """Create required directories if they do not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def plugin_mode(category: str, name: str) -> str:
    """Read the ENABLE/DISABLE mode for a plugin from environment.

    The env var is ``{CATEGORY}_{NAME}``, upper-cased. Unknown or empty values
    default to ``"ENABLE"``.

    Args:
        category: Plugin category (``"VECTOR_DB"``, ``"CHUNKING"``,
            ``"EMBEDDING"``).
        name: Plugin name (e.g. ``"simple"``).

    Returns:
        ``"ENABLE"`` or ``"DISABLE"``.
    """
    env_key = f"{category.upper()}_{name.upper()}"
    value = os.getenv(env_key, "ENABLE").upper()
    if value in ("ENABLE", "DISABLE"):
        return value
    return "ENABLE"
