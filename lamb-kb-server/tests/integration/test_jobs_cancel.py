"""Integration tests for ``POST /jobs/{id}/cancel``.

Seeds an ``IngestionJob`` row directly so the cancel transitions can be
exercised deterministically (without racing a live worker).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests._helpers import AUTH_HEADERS


def _seed_job(status: str) -> str:
    from database.connection import get_session_direct
    from database.models import IngestionJob

    session = get_session_direct()
    try:
        job_id = f"job-cancel-{status}"
        # Remove any prior row from a previous run.
        existing = session.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if existing:
            session.delete(existing)
            session.commit()
        session.add(IngestionJob(
            id=job_id,
            collection_id="col-x",
            organization_id="org-x",
            documents_json="[]",
            documents_total=1,
            status=status,
        ))
        session.commit()
        return job_id
    finally:
        session.close()


@pytest.mark.asyncio
async def test_cancel_nonexistent_job_404(client_no_worker: AsyncClient) -> None:
    resp = await client_no_worker.post(
        "/jobs/does-not-exist/cancel", headers=AUTH_HEADERS
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_pending_job(client_no_worker: AsyncClient) -> None:
    job_id = _seed_job("pending")
    resp = await client_no_worker.post(f"/jobs/{job_id}/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_terminal_job_is_noop(client_no_worker: AsyncClient) -> None:
    job_id = _seed_job("completed")
    resp = await client_no_worker.post(f"/jobs/{job_id}/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    # Terminal job stays unchanged (no transition to cancelled).
    assert resp.json()["status"] == "completed"
