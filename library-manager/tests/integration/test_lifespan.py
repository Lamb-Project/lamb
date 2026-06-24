"""Cover the FastAPI app lifespan, startup helpers, and middleware.

Drives ``main.lifespan`` directly (exercising ensure_directories → init_db →
_discover_plugins → purge_stale_uploads → recover_stale_jobs → start_worker →
stop_worker), the ``purge_stale_uploads`` helper, the request-logging
middleware, and the production docs gating.

Source under test: ``backend/main.py`` + ``routers/importing.py`` (purge).
"""

from __future__ import annotations

import os
import time

from _helpers import AUTH_HEADERS
from httpx import ASGITransport, AsyncClient
from tasks import worker


async def test_lifespan_starts_and_stops_worker() -> None:
    """Entering the lifespan starts the worker; exiting stops it."""
    from main import app, lifespan  # noqa: PLC0415

    # Ensure a clean baseline regardless of fixture ordering.
    if worker.is_worker_running():
        await worker.stop_worker()

    assert not worker.is_worker_running()
    async with lifespan(app):
        assert worker.is_worker_running()
    assert not worker.is_worker_running()


async def test_purge_stale_uploads_removes_old_files() -> None:
    """purge_stale_uploads deletes temp uploads older than the max age."""
    from routers.importing import (  # noqa: PLC0415
        _UPLOAD_DIR,
        _UPLOAD_MAX_AGE_SECONDS,
        purge_stale_uploads,
    )

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stale = _UPLOAD_DIR / "stale_upload.bin"
    stale.write_bytes(b"old")
    # Backdate the mtime well past the cutoff.
    old = time.time() - (_UPLOAD_MAX_AGE_SECONDS + 60)
    os.utime(stale, (old, old))

    fresh = _UPLOAD_DIR / "fresh_upload.bin"
    fresh.write_bytes(b"new")

    purge_stale_uploads()

    assert not stale.exists(), "stale upload should have been purged"
    assert fresh.exists(), "fresh upload should remain"
    fresh.unlink(missing_ok=True)


async def test_purge_stale_uploads_noop_without_dir() -> None:
    """purge_stale_uploads returns cleanly when the upload dir is absent."""
    import shutil  # noqa: PLC0415

    from routers.importing import _UPLOAD_DIR, purge_stale_uploads  # noqa: PLC0415

    if _UPLOAD_DIR.exists():
        shutil.rmtree(_UPLOAD_DIR, ignore_errors=True)
    purge_stale_uploads()  # must not raise
    assert not _UPLOAD_DIR.exists()


async def test_request_logging_middleware_passthrough(client: AsyncClient) -> None:
    """A normal request flows through the log_requests middleware and returns 200."""
    resp = await client.get("/health")
    assert resp.status_code == 200, resp.text


async def test_docs_disabled_in_non_debug_env() -> None:
    """With LOG_LEVEL != DEBUG, docs are gated off and /docs returns 404."""
    from main import app  # noqa: PLC0415

    assert app.docs_url is None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/docs", headers=AUTH_HEADERS)
    assert resp.status_code == 404, resp.text
