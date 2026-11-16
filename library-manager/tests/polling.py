"""Shared polling helpers for tests that wait on asynchronous import jobs.

The wait budget defaults to 60 seconds, which is comfortable for slow or
contended CI runners, and can be tuned per environment with the
``LM_TEST_POLL_TIMEOUT`` environment variable (seconds). The budget is only
spent on worst-case paths: polling returns as soon as the item is done.
"""

import asyncio
import os
import time

import pytest
from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}

# Maximum time (seconds) to wait for an import job to complete.
POLL_TIMEOUT = float(os.environ.get("LM_TEST_POLL_TIMEOUT", "60"))
POLL_INTERVAL = 0.5

_FINAL_STATUSES = ("ready", "failed")


async def wait_for_ready(
    client: AsyncClient,
    lib_id: str,
    item_id: str,
    timeout: float | None = None,
    job_id: str | None = None,
) -> str:
    """Poll item status until it leaves 'pending'/'processing'.

    Args:
        client: HTTP client.
        lib_id: Library ID.
        item_id: Content item ID.
        timeout: Max seconds to wait. Defaults to ``POLL_TIMEOUT``.
        job_id: Import job ID, only used in the timeout diagnostic.

    Returns:
        Final status string ('ready' or 'failed').

    Raises:
        pytest.fail.Exception: if the item is still not done when the budget
            runs out. The message carries the elapsed time, the last observed
            status and error message, and the ids needed to follow up.
    """
    budget = POLL_TIMEOUT if timeout is None else timeout
    started = time.monotonic()
    last: dict = {}
    while True:
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status",
            headers=AUTH_HEADERS,
        )
        last = resp.json()
        if last.get("status") in _FINAL_STATUSES:
            return last["status"]
        if time.monotonic() - started >= budget:
            break
        await asyncio.sleep(POLL_INTERVAL)

    pytest.fail(
        f"Import did not finish within {time.monotonic() - started:.1f}s "
        f"(budget {budget:.0f}s, set LM_TEST_POLL_TIMEOUT to change it). "
        f"Last status: {last.get('status')!r}; "
        f"last error_message: {last.get('error_message')!r}; "
        f"library: {lib_id}; item: {item_id}; job: {job_id or 'not given'}"
    )
