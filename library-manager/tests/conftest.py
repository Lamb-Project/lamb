"""Root test configuration for the Library Manager suite.

This module runs **before the application is imported** so it can fix the
environment the app reads at import time (``config.py`` freezes
``DATA_DIR``, ``LAMB_API_TOKEN`` etc. into module-level constants the moment
it is imported).

Responsibilities that belong to *every* tier live here:

* Set a deterministic, env-independent environment (token, temp data dir).
* Put ``backend/`` and ``tests/`` on ``sys.path`` (no editable install needed).
* Initialise the database + discover plugins once per session.
* Install the offline YouTube transcript cache.
* **Auto-tag** every collected test with its tier marker (``unit`` /
  ``integration`` / ``e2e``) based on the directory it lives in, so
  ``pytest -m unit`` works with zero per-test decoration.

Tier-specific fixtures (the ASGI ``client``, the uvicorn subprocess, …) live
in the per-tier ``conftest.py`` files under ``unit/``, ``integration/`` and
``e2e/``.
"""

import os
import shutil
import sys
import tempfile

import pytest

# --- Environment must be set BEFORE importing the app (config reads at import) ---
_TEST_DIR = tempfile.mkdtemp(prefix="lm-test-")
os.environ["LAMB_API_TOKEN"] = "test-token"
os.environ["DATA_DIR"] = _TEST_DIR
os.environ.setdefault("LOG_LEVEL", "WARNING")

# --- Make backend/ and tests/ importable as top-level packages ---
_TESTS_DIR = os.path.dirname(__file__)
_BACKEND_DIR = os.path.join(_TESTS_DIR, "..", "backend")
for _p in (_TESTS_DIR, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Imported after sys.path is configured. ``_helpers`` is dependency-light
# (no app imports at module scope); ``init_db`` is used by the session fixture.
from database.connection import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_session():
    """Initialise the database and discover plugins once for the whole run.

    Mirrors the production startup sequence (``ensure_directories`` →
    ``init_db`` → ``_discover_plugins``) plus the offline YouTube cache so
    no test ever hits the network for a transcript. Tears down the temp data
    directory at the end of the session.
    """
    from config import ensure_directories  # noqa: PLC0415
    from main import _discover_plugins  # noqa: PLC0415

    ensure_directories()
    init_db()
    _discover_plugins()

    from youtube_cache import install_youtube_cache  # noqa: PLC0415

    install_youtube_cache()

    yield

    # Quiesce any lingering import-worker threads before removing the data
    # directory. ``stop_worker`` shuts the executor down with ``wait=False``
    # (correct for production fast-shutdown), so a thread from the last
    # worker-backed test can still be mid-commit at session end and would
    # otherwise log a spurious "unable to open database file" after the dir
    # is gone. Draining here keeps the run's output clean.
    try:
        from tasks import worker  # noqa: PLC0415

        worker._running = False
        if worker._executor is not None:
            worker._executor.shutdown(wait=True, cancel_futures=True)
    except Exception:
        pass

    shutil.rmtree(_TEST_DIR, ignore_errors=True)


def pytest_collection_modifyitems(config, items):
    """Auto-tag each test with its tier marker based on its directory.

    A test under ``tests/unit/`` gets ``@pytest.mark.unit`` for free, and so
    on. This keeps marker assignment impossible to forget and lets
    ``pytest -m integration`` select a tier without any decorator drift.
    """
    for item in items:
        path = str(item.fspath).replace(os.sep, "/")
        if "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
        elif "/tests/e2e/" in path:
            item.add_marker(pytest.mark.e2e)
