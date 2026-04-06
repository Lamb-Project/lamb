"""Shared fixtures for Library Manager tests.

Provides an in-process async test client (httpx + FastAPI TestClient pattern)
with a fresh temporary database for each test session.
"""

import os
import shutil
import sys
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

# Set environment BEFORE importing the app — config reads at import time.
_TEST_DIR = tempfile.mkdtemp(prefix="lm-test-")
os.environ["LAMB_API_TOKEN"] = "test-token"
os.environ["DATA_DIR"] = _TEST_DIR
os.environ["LOG_LEVEL"] = "WARNING"

# Add backend and tests directories to sys.path.
_TESTS_DIR = os.path.dirname(__file__)
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from database.connection import init_db  # noqa: E402
from main import app  # noqa: E402

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    """Initialize the database and discover plugins for the test session."""
    from config import ensure_directories  # noqa: PLC0415
    from main import _discover_plugins  # noqa: PLC0415
    ensure_directories()
    init_db()
    _discover_plugins()

    from youtube_cache import install_youtube_cache  # noqa: PLC0415
    install_youtube_cache()

    yield
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


@pytest.fixture
async def client():
    """Provide an async httpx client with the background worker running.

    Starts the import worker so async jobs are processed, and stops it
    after the test.

    Yields:
        An ``AsyncClient`` that sends requests in-process (no network).
    """
    from tasks.worker import start_worker, stop_worker  # noqa: PLC0415

    await start_worker()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await stop_worker()


@pytest.fixture
async def library(client: AsyncClient) -> dict:
    """Create a test library and return its metadata.

    Yields:
        Dict with ``id``, ``organization_id``, ``name``.
    """
    import uuid  # noqa: PLC0415

    lib_id = f"lib-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/libraries",
        headers=AUTH_HEADERS,
        json={
            "id": lib_id,
            "organization_id": "org-test",
            "name": f"Test Library {lib_id[-8:]}",
        },
    )
    assert resp.status_code == 201
    return resp.json()
