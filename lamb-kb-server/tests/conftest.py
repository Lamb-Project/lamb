"""Root pytest config — session setup, env vars, plugin registration.

Tier-specific fixtures live in ``tests/{unit,integration,e2e}/conftest.py``.
Shared utilities live in ``tests/_helpers.py`` and ``tests/_fakes.py``.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# --- Test environment setup (MUST happen before importing the app) ---
_TEST_DIR = tempfile.mkdtemp(prefix="kb-test-")
os.environ["LAMB_API_TOKEN"] = "test-token"  # always override so tests are env-independent
os.environ["DATA_DIR"] = _TEST_DIR
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("MAX_CONCURRENT_INGESTIONS", "2")
os.environ.setdefault("INGESTION_TASK_TIMEOUT_SECONDS", "60")
# Keep payload limit small so we can exercise 413 rejection cheaply.
os.environ.setdefault("MAX_REQUEST_SIZE_BYTES", "2048")

# Disable optional plugins that require network / heavy downloads so
# `_discover_plugins` is fast and deterministic. The unit tier overrides
# these flags inside individual tests where the real plugins must run.
os.environ.setdefault("EMBEDDING_LOCAL", "DISABLE")
os.environ.setdefault("VECTOR_DB_QDRANT", "DISABLE")

# Make backend & tests packages importable without editable install.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

# Register fake embedding BEFORE the app imports plugins.
from tests._fakes import register_fake_embedding  # noqa: E402

register_fake_embedding()

# Now it's safe to import the FastAPI app.
import main  # noqa: E402
from config import ensure_directories  # noqa: E402
from database.connection import init_db  # noqa: E402

# Re-export for tests that still reference these from tests.conftest.
from tests._helpers import AUTH_HEADERS, _poll_job  # noqa: E402, F401


@pytest.fixture(scope="session", autouse=True)
def _setup() -> None:
    """One-time session setup: init DB, discover plugins, tear down at end."""
    ensure_directories()
    init_db()
    main._discover_plugins()
    # Re-inject in case discovery touched the registry.
    register_fake_embedding()

    yield
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


def pytest_collection_modifyitems(config, items):
    """Auto-tag tests with their tier marker based on directory layout."""
    tier_for_dir = {
        "unit": "unit",
        "integration": "integration",
        "e2e": "e2e",
    }
    for item in items:
        parts = Path(str(item.fspath)).parts
        for tier_dir, marker in tier_for_dir.items():
            if tier_dir in parts:
                item.add_marker(getattr(pytest.mark, marker))
                break
