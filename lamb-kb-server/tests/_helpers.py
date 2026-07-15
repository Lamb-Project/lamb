"""Shared test helpers (auth headers, polling)."""

from __future__ import annotations

import asyncio

from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


async def poll_job(
    client: AsyncClient,
    job_id: str,
    timeout: float = 20.0,
    interval: float = 0.2,
) -> dict:
    """Poll /jobs/{id} until the job reaches a terminal state or timeout."""
    waited = 0.0
    body: dict = {}
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


# Backwards-compatible alias used by the original conftest helper name.
_poll_job = poll_job
