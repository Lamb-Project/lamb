"""Tests for failed-job retry with bounded in-memory credential retention.

Covers the worker-level credential cache (retain across attempts, discard on
terminal/exhausted states, TTL purge) and the HTTP retry endpoints.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from config import MAX_JOB_ATTEMPTS
from database.connection import get_session_direct
from database.models import IngestionJob
from httpx import AsyncClient
from tasks import worker

from tests.conftest import AUTH_HEADERS


def _insert_job(status: str, attempts: int) -> str:
    job_id = uuid4().hex
    db = get_session_direct()
    try:
        db.add(
            IngestionJob(
                id=job_id,
                collection_id="some-collection",
                organization_id=f"org-{uuid4().hex[:8]}",
                documents_json="[]",
                status=status,
                documents_total=0,
                documents_processed=0,
                chunks_created=0,
                attempts=attempts,
            )
        )
        db.commit()
    finally:
        db.close()
    return job_id


# ---------------------------------------------------------------------------
# Worker-level credential cache
# ---------------------------------------------------------------------------


def test_store_and_retry_available() -> None:
    job_id = uuid4().hex
    worker.store_credentials(job_id, {"api_key": "k", "api_endpoint": ""})
    assert worker.retry_available(job_id) is True
    worker._discard_credentials(job_id)
    assert worker.retry_available(job_id) is False


def test_purge_expired_credentials_drops_old_entries() -> None:
    job_id = uuid4().hex
    worker.store_credentials(job_id, {"api_key": "k"})
    # Backdate the stored timestamp beyond the retention window.
    worker._job_cred_stored_at[job_id] = datetime.now(UTC) - timedelta(
        minutes=worker.RETRY_CACHE_TTL_MINUTES + 1
    )
    worker._purge_expired_credentials()
    assert worker.retry_available(job_id) is False


def test_purge_keeps_fresh_entries() -> None:
    job_id = uuid4().hex
    worker.store_credentials(job_id, {"api_key": "k"})
    worker._purge_expired_credentials()
    assert worker.retry_available(job_id) is True
    worker._discard_credentials(job_id)


# ---------------------------------------------------------------------------
# HTTP retry endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_failed_job_with_creds_requeues(client: AsyncClient) -> None:
    job_id = _insert_job("failed", attempts=1)
    worker.store_credentials(job_id, {"api_key": "k", "api_endpoint": ""})
    try:
        resp = await client.post(f"/jobs/{job_id}/retry", headers=AUTH_HEADERS)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "pending"
        assert body["error_message"] is None
    finally:
        worker._discard_credentials(job_id)


@pytest.mark.asyncio
async def test_retry_without_creds_returns_410(client: AsyncClient) -> None:
    job_id = _insert_job("failed", attempts=1)  # no store_credentials
    resp = await client.post(f"/jobs/{job_id}/retry", headers=AUTH_HEADERS)
    assert resp.status_code == 410
    assert "re-submit" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_retry_non_failed_job_returns_409(client: AsyncClient) -> None:
    job_id = _insert_job("completed", attempts=1)
    worker.store_credentials(job_id, {"api_key": "k"})
    try:
        resp = await client.post(f"/jobs/{job_id}/retry", headers=AUTH_HEADERS)
        assert resp.status_code == 409
    finally:
        worker._discard_credentials(job_id)


@pytest.mark.asyncio
async def test_retry_exhausted_attempts_returns_409(client: AsyncClient) -> None:
    job_id = _insert_job("failed", attempts=MAX_JOB_ATTEMPTS)
    worker.store_credentials(job_id, {"api_key": "k"})
    try:
        resp = await client.post(f"/jobs/{job_id}/retry", headers=AUTH_HEADERS)
        assert resp.status_code == 409
        assert "exhausted" in resp.json()["detail"].lower()
    finally:
        worker._discard_credentials(job_id)


@pytest.mark.asyncio
async def test_retry_unknown_job_returns_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/jobs/00000000-0000-0000-0000-000000000000/retry", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retry_available_endpoint(client: AsyncClient) -> None:
    job_id = _insert_job("failed", attempts=1)
    # Without creds → not available.
    resp = await client.get(f"/jobs/{job_id}/retry-available", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == {
        "available": False,
        "attempts": 1,
        "max_attempts": MAX_JOB_ATTEMPTS,
    }
    # With creds → available.
    worker.store_credentials(job_id, {"api_key": "k"})
    try:
        resp = await client.get(
            f"/jobs/{job_id}/retry-available", headers=AUTH_HEADERS
        )
        assert resp.json()["available"] is True
    finally:
        worker._discard_credentials(job_id)


@pytest.mark.asyncio
async def test_retry_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/jobs/whatever/retry")
    assert resp.status_code in (401, 403)
