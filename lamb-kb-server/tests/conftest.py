"""Pytest configuration and shared fixtures for the KB Server test suite.

The fixtures mirror the Library Manager's in-process ASGI client pattern so
every test runs against a real FastAPI instance without needing a live
server or external services (no OpenAI/Ollama calls, no network). A
deterministic fake embedding function is registered at module import time so
embedding is reproducible across runs.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest

# --- Test environment setup (MUST happen before importing the app) ---
_TEST_DIR = tempfile.mkdtemp(prefix="kb-test-")
os.environ.setdefault("LAMB_API_TOKEN", "test-token")
os.environ["DATA_DIR"] = _TEST_DIR
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["MAX_CONCURRENT_INGESTIONS"] = "2"
os.environ["INGESTION_TASK_TIMEOUT_SECONDS"] = "60"
# Keep the payload limit small in tests so we can exercise 413 rejection
# without allocating hundreds of megabytes.
os.environ["MAX_REQUEST_SIZE_BYTES"] = "2048"

# Disable optional plugins that require network / heavy downloads so
# `_discover_plugins` is fast and deterministic.
os.environ.setdefault("EMBEDDING_LOCAL", "DISABLE")
os.environ.setdefault("VECTOR_DB_QDRANT", "DISABLE")

# Make the backend package importable without editable install.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT / "tests"))

# Register a deterministic fake embedding BEFORE the app imports plugins.
from plugins.base import (  # noqa: E402
    EmbeddingFunction,
    EmbeddingRegistry,
    PluginParameter,
)


class FakeEmbedding(EmbeddingFunction):
    """Deterministic, hash-based fake embedding for tests.

    Uses SHA-256 of the input text to produce a reproducible 16-dimensional
    float vector. Good enough to exercise the full pipeline end-to-end with
    predictable similarity ordering (identical text → identical vector →
    score 1.0). No network or external model required.
    """

    name = "fake"
    description = "Deterministic fake embedding for tests"
    _dim = 16

    def __init__(
        self,
        *,
        model: str = "fake-model",
        api_key: str = "",
        api_endpoint: str = "",
    ) -> None:
        super().__init__(model=model, api_key=api_key, api_endpoint=api_endpoint)

    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in input:
            digest = hashlib.sha256(str(text).encode("utf-8")).digest()[: self._dim]
            vec = [b / 255.0 for b in digest]
            norm = (sum(v * v for v in vec)) ** 0.5 or 1.0
            vectors.append([v / norm for v in vec])
        return vectors

    @classmethod
    def class_parameters(cls) -> list[PluginParameter]:
        return [
            PluginParameter("model", "string", "Fake model name", "fake-model"),
        ]


# Force-register (bypass DISABLE checks) so "fake" is always available in tests.
EmbeddingRegistry._plugins["fake"] = FakeEmbedding

# Now it's safe to import the FastAPI app.
import main  # noqa: E402
from config import ensure_directories  # noqa: E402
from database.connection import init_db  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(scope="session", autouse=True)
def _setup() -> None:
    """One-time session setup: init DB, discover plugins, tear down at end."""
    ensure_directories()
    init_db()
    main._discover_plugins()
    # Fake embedding has to be re-injected AFTER discover in case
    # _discover_plugins re-initializes the registry (it doesn't, but be safe).
    EmbeddingRegistry._plugins["fake"] = FakeEmbedding

    yield
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """In-process ASGI client with worker lifecycle managed around each test."""
    from tasks.worker import start_worker, stop_worker  # noqa: PLC0415

    await start_worker()
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await stop_worker()


@pytest.fixture
def org_id() -> str:
    """Return a unique organization ID per test."""
    return f"org-{uuid4().hex[:8]}"


@pytest.fixture
async def collection(client: AsyncClient, org_id: str) -> dict:
    """Create a test collection and return the JSON response."""
    payload = {
        "organization_id": org_id,
        "name": f"test-kb-{uuid4().hex[:6]}",
        "description": "Test collection",
        "chunking_strategy": "simple",
        "chunking_params": {"chunk_size": 500, "chunk_overlap": 100},
        "embedding": {
            "vendor": "fake",
            "model": "fake-model",
            "api_endpoint": "",
        },
        "vector_db_backend": "chromadb",
    }
    response = await client.post(
        "/collections", json=payload, headers=AUTH_HEADERS
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _poll_job(
    client: AsyncClient,
    job_id: str,
    timeout: float = 20.0,
    interval: float = 0.2,
) -> dict:
    """Poll a job endpoint until it reaches a terminal state or timeout."""
    import asyncio  # noqa: PLC0415

    waited = 0.0
    while waited <= timeout:
        response = await client.get(f"/jobs/{job_id}", headers=AUTH_HEADERS)
        assert response.status_code == 200, response.text
        body = response.json()
        if body["status"] in ("completed", "failed"):
            return body
        await asyncio.sleep(interval)
        waited += interval
    raise AssertionError(
        f"Job {job_id} did not finish within {timeout}s; last status={body}"
    )
