"""Application configuration loaded from environment variables.

All configuration is centralized here. Other modules import from this file
rather than reading os.environ directly.

The KB Server has three distinct plugin families (vector DBs, chunking
strategies, embedding vendors), each gated by a simple ENABLE/DISABLE env
var. Defaults are ENABLE for everything that has its dependencies installed;
plugin registration is skipped gracefully for anything that fails to import.
"""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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


# --- KG-RAG (optional graph augmentation) ---
# When ``KG_RAG_ENABLED=true`` the server exposes ``/graph`` and ``/benchmarks``
# routers and the ``kg_rag_query`` query plugin path. Per-request OpenAI
# credentials are preferred over a permanent ``KG_RAG_OPENAI_API_KEY``; the
# env var remains supported as a fallback for ingestion-time extraction when
# the API caller did not supply one.


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError:
        logger.warning(
            "Invalid integer for %s=%s. Using default %s.", name, value, default
        )
        return default
    return max(minimum, min(maximum, parsed))


def get_kg_rag_config() -> dict[str, Any]:
    """Read the KG-RAG configuration from the environment.

    KG-RAG is disabled by default. The graph pipeline is intentionally
    environment-driven so existing deployments keep their current vector
    ingestion/query behavior unless they opt in explicitly.

    The ``openai_api_key`` field is the *fallback* extraction key. Where the
    API caller can pass a per-request credential (graph migration, benchmark,
    KG-RAG query) the per-request value takes precedence (ADR-4).
    """
    enabled = _env_bool("KG_RAG_ENABLED", False)
    chat_model = os.getenv("KG_RAG_CHAT_MODEL") or os.getenv(
        "OPENAI_CHAT_MODEL", "gpt-4o-mini"
    )

    return {
        "enabled": enabled,
        "index_on_ingest": _env_bool("KG_RAG_INDEX_ON_INGEST", True),
        "openai_api_key": (
            os.getenv("KG_RAG_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        ),
        "chat_model": chat_model,
        "extraction_model": (
            os.getenv("KG_RAG_EXTRACTION_MODEL")
            or os.getenv("OPENAI_EXTRACTION_MODEL")
            or chat_model
        ),
        "neo4j_uri": os.getenv("KG_RAG_NEO4J_URI") or os.getenv("NEO4J_URI", ""),
        "neo4j_user": (
            os.getenv("KG_RAG_NEO4J_USER") or os.getenv("NEO4J_USER", "neo4j")
        ),
        "neo4j_password": (
            os.getenv("KG_RAG_NEO4J_PASSWORD") or os.getenv("NEO4J_PASSWORD", "")
        ),
        "graph_depth": _env_int("KG_RAG_GRAPH_DEPTH", 2, 1, 4),
        "limit_factor": _env_int("KG_RAG_LIMIT_FACTOR", 4, 1, 20),
        "extraction_max_workers": _env_int(
            "KG_RAG_EXTRACTION_MAX_WORKERS", 4, 1, 16
        ),
        # Per-request OpenAI timeout. Default 60s is generous for the
        # extraction prompt; raise it for very large chunks, lower it if
        # you want ingestion to fail fast.
        "openai_timeout_seconds": _env_int(
            "KG_RAG_OPENAI_TIMEOUT_SECONDS", 60, 5, 600
        ),
    }


KG_RAG_ENABLED: bool = _env_bool("KG_RAG_ENABLED", False)


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
