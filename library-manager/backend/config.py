"""Application configuration loaded from environment variables.

All configuration is centralized here. Other modules import from this file
rather than reading os.environ directly.
"""

import os
from pathlib import Path

# --- Server ---
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "9091"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# --- Authentication ---
# Single bearer token that LAMB sends with every request.
# If it matches, the request is trusted entirely.
LAMB_API_TOKEN: str = os.getenv("LAMB_API_TOKEN", "")

# --- Storage ---
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
CONTENT_DIR: Path = DATA_DIR / "content"
DB_PATH: Path = DATA_DIR / "library-manager.db"

# --- Task processing ---
MAX_CONCURRENT_IMPORTS: int = int(os.getenv("MAX_CONCURRENT_IMPORTS", "3"))
IMPORT_TASK_TIMEOUT_SECONDS: int = int(os.getenv("IMPORT_TASK_TIMEOUT_SECONDS", "600"))

# --- Plugin governance ---
# PLUGIN_<NAME>=DISABLE|SIMPLIFIED|ADVANCED  (default: ADVANCED)
# Read dynamically by the plugin registry; no static config here.

# --- Upload limits ---
MAX_UPLOAD_SIZE_BYTES: int = int(
    os.getenv("MAX_UPLOAD_SIZE_BYTES", str(500 * 1024 * 1024))
)
MAX_ZIP_IMPORT_SIZE_BYTES: int = int(
    os.getenv("MAX_ZIP_IMPORT_SIZE_BYTES", str(200 * 1024 * 1024))
)

# --- Permalink base ---
# The prefix used when constructing permalink URLs in metadata.json.
# LAMB proxies /docs/{org}/{lib}/{item}/... to this service.
PERMALINK_PREFIX: str = os.getenv("PERMALINK_PREFIX", "/docs")


def ensure_directories() -> None:
    """Create required directories if they do not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
