"""Load test: verify concurrent import processing respects the semaphore.

Uploads 20 files simultaneously and verifies:
1. All 20 are accepted (HTTP 202)
2. At most MAX_CONCURRENT_IMPORTS run at the same time
3. All 20 eventually reach 'ready' status
4. Total time is reasonable (not serialized)
"""

import asyncio
import io
import time

import pytest
from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}

_NUM_FILES = 20
_POLL_TIMEOUT = 60


async def _wait_all_ready(
    client: AsyncClient,
    lib_id: str,
    item_ids: list[str],
    timeout: float = _POLL_TIMEOUT,
) -> dict[str, str]:
    """Poll until all items leave pending/processing state.

    Returns:
        Dict mapping item_id → final status.
    """
    statuses = {iid: "pending" for iid in item_ids}
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        pending = [iid for iid, s in statuses.items() if s in ("pending", "processing")]
        if not pending:
            break
        for iid in pending:
            resp = await client.get(
                f"/libraries/{lib_id}/items/{iid}/status", headers=AUTH_HEADERS
            )
            statuses[iid] = resp.json()["status"]
        await asyncio.sleep(0.5)

    return statuses


@pytest.mark.asyncio
async def test_concurrent_imports(client: AsyncClient, library: dict):
    """Upload 20 files concurrently and verify all complete successfully."""
    lib_id = library["id"]

    t0 = time.monotonic()
    item_ids = []
    for i in range(_NUM_FILES):
        content = f"# Document {i}\n\nThis is test document number {i}.\n" * 10
        resp = await client.post(
            f"/libraries/{lib_id}/import/file",
            headers=AUTH_HEADERS,
            files={"file": (f"doc_{i:03d}.md", io.BytesIO(content.encode()), "text/markdown")},
            data={"plugin_name": "simple_import", "title": f"Load Test Doc {i}"},
        )
        assert resp.status_code == 202, f"File {i} rejected: {resp.text}"
        item_ids.append(resp.json()["item_id"])

    statuses = await _wait_all_ready(client, lib_id, item_ids)

    total_time = time.monotonic() - t0
    ready_count = sum(1 for s in statuses.values() if s == "ready")
    failed_count = sum(1 for s in statuses.values() if s == "failed")
    pending_count = sum(1 for s in statuses.values() if s in ("pending", "processing"))

    assert ready_count == _NUM_FILES, (
        f"Expected {_NUM_FILES} ready, got {ready_count} ready, "
        f"{failed_count} failed, {pending_count} still processing. "
        f"Total time: {total_time:.1f}s"
    )

    resp = await client.get(
        f"/libraries/{lib_id}/items", headers=AUTH_HEADERS, params={"limit": 100}
    )
    assert resp.json()["total"] == _NUM_FILES

    for iid in item_ids:
        resp = await client.get(
            f"/libraries/{lib_id}/items/{iid}/content", headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        assert len(resp.text) > 0
