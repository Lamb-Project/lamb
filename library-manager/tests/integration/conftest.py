"""Integration-tier fixtures: in-process ASGI, real DB + real worker.

These tests drive the FastAPI app through ``httpx.ASGITransport`` (no socket,
no subprocess) against the real SQLite database and the real background import
worker. Isolation between tests comes from unique library/organization ids
rather than resetting the shared session database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from _helpers import AUTH_HEADERS, library_payload
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """ASGI client with the background import worker running.

    Use for any test that imports content and waits for it to reach a
    terminal status.
    """
    from main import app  # noqa: PLC0415
    from tasks import worker  # noqa: PLC0415

    await worker.start_worker()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await worker.stop_worker()
    # ``stop_worker`` shuts the executor down with ``wait=False`` (production
    # fast-shutdown). Drain it here so no import thread outlives this test and
    # later touches the shared session DB during teardown.
    if worker._executor is not None:
        worker._executor.shutdown(wait=True, cancel_futures=True)


@pytest.fixture
async def client_no_worker() -> AsyncIterator[AsyncClient]:
    """ASGI client with NO worker running.

    Use when a test drives the worker loop manually (e.g. dispatching a
    single job, asserting stale-job recovery) and does not want the polling
    loop racing it.
    """
    from main import app  # noqa: PLC0415

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def library(client: AsyncClient) -> dict:
    """Create a fresh library (unique id under ``org-test``) and return it."""
    resp = await client.post("/libraries", headers=AUTH_HEADERS, json=library_payload())
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def org_id() -> str:
    """A unique organization id, for multi-tenant isolation assertions."""
    from _helpers import unique_id  # noqa: PLC0415

    return unique_id("org")
