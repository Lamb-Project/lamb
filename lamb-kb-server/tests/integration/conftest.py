"""Integration-tier fixtures: ASGI in-process client + worker lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import main
import pytest
from httpx import ASGITransport, AsyncClient

from tests._helpers import AUTH_HEADERS


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """In-process ASGI client with worker started/stopped per test."""
    from tasks.worker import start_worker, stop_worker  # noqa: PLC0415

    await start_worker()
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await stop_worker()


@pytest.fixture
async def client_no_worker() -> AsyncIterator[AsyncClient]:
    """ASGI client WITHOUT the worker — for tests that drive it manually."""
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def org_id() -> str:
    return f"org-{uuid4().hex[:8]}"


@pytest.fixture
async def collection(client: AsyncClient, org_id: str) -> dict:
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
    response = await client.post("/collections", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201, response.text
    return response.json()
