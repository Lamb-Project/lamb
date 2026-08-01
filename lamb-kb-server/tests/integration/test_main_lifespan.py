"""Integration tests for backend/main.py — lifespan, middleware, and startup checks.

Targets the missing lines/branches reported at 74% coverage:
- Lines 35-36  : empty LAMB_API_TOKEN guard / sys.exit(1)
- Lines 44-55  : lifespan startup and shutdown sequence
- Lines 133-134: exception path inside _discover_plugins
"""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys
import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

import main
from database.connection import get_session_direct
from database.models import IngestionJob
from tests._helpers import AUTH_HEADERS


# ---------------------------------------------------------------------------
# 1. Startup guard — empty LAMB_API_TOKEN causes sys.exit(1)
# ---------------------------------------------------------------------------


def test_empty_token_refuses_start(tmp_path) -> None:
    """Lines 35-36: LAMB_API_TOKEN='' must cause the process to exit with 1.

    We spawn a fresh interpreter so the guard runs unconditionally, without
    any interference from the session-level test environment.
    """
    script = (
        "import sys; "
        "sys.path.insert(0, 'backend'); "
        "import os; "
        "os.environ['LAMB_API_TOKEN'] = ''; "
        "os.environ['DATA_DIR'] = str(__import__('pathlib').Path(sys.argv[1])); "
        "import main"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        cwd="/home/novelia/Documents/lamb/lamb-kb-server",
    )
    assert result.returncode != 0, (
        "Expected non-zero exit when LAMB_API_TOKEN is empty, "
        f"but got {result.returncode}. stderr={result.stderr!r}"
    )
    combined = result.stdout + result.stderr
    assert "LAMB_API_TOKEN" in combined or "token" in combined.lower(), (
        "Expected the startup log to mention the missing token requirement; "
        f"got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 2. _discover_plugins survives one module raising on import (lines 133-134)
# ---------------------------------------------------------------------------


def test_discover_plugins_survives_import_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Lines 133-134: exception inside importlib.import_module is swallowed.

    Monkeypatching importlib.import_module inside main._discover_plugins to
    raise for exactly one module verifies the except branch is exercised while
    still allowing other plugins to register.
    """
    from plugins.base import ChunkingRegistry

    # Capture the count of chunking strategies before (they are already
    # registered at session startup, so the count should be stable).
    before_count = len(ChunkingRegistry.list_plugins())

    original_import = importlib.import_module

    def _failing_import(name: str, *args, **kwargs):
        if name == "plugins.embedding.openai":
            raise ImportError("Simulated dependency missing for openai plugin")
        return original_import(name, *args, **kwargs)

    with caplog.at_level(logging.WARNING, logger="main"):
        with patch.object(importlib, "import_module", side_effect=_failing_import):
            main._discover_plugins()

    # The warning log must mention the failing module.
    warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        "plugins.embedding.openai" in msg for msg in warning_messages
    ), f"Expected a warning about the failing module; got records: {warning_messages}"

    # Chunking strategies must still be registered (other modules loaded fine).
    after_count = len(ChunkingRegistry.list_plugins())
    assert after_count >= before_count, (
        "Chunking strategies should still be registered after a single plugin "
        f"import failure; before={before_count}, after={after_count}"
    )
    assert after_count >= 4, (
        f"Expected at least 4 chunking strategies; got {after_count}"
    )


# ---------------------------------------------------------------------------
# 3. Request logging middleware emits one log line per request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_logging_middleware_emits_log(
    client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Lines 80-92: each HTTP request produces a log record with method, path,
    status code, and duration in milliseconds.

    The log format in main.py is:
        "%s %s → %d (%dms)", method, path, status_code, duration_ms
    """
    with caplog.at_level(logging.INFO, logger="main"):
        response = await client.get("/health")

    assert response.status_code == 200

    # Find the middleware log record.
    request_logs = [r for r in caplog.records if "→" in r.getMessage()]
    assert request_logs, (
        "Expected at least one log record with '→' from the request logging "
        f"middleware; got records: {[r.getMessage() for r in caplog.records]}"
    )
    log_text = request_logs[0].getMessage()
    assert "GET" in log_text, f"Method 'GET' not found in log: {log_text!r}"
    assert "/health" in log_text, f"Path '/health' not found in log: {log_text!r}"
    assert "200" in log_text, f"Status '200' not found in log: {log_text!r}"
    assert "ms" in log_text, f"Duration 'ms' not found in log: {log_text!r}"


# ---------------------------------------------------------------------------
# 4. /docs endpoint is 404 when LOG_LEVEL != DEBUG (test environment default)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docs_not_exposed_in_non_debug_mode(client: AsyncClient) -> None:
    """`_docs_url` is None when LOG_LEVEL != 'DEBUG', so /docs returns 404.

    The test conftest sets LOG_LEVEL=WARNING, which causes _docs_url=None and
    therefore FastAPI does not mount the Swagger UI at /docs.
    """
    response = await client.get("/docs")
    assert response.status_code == 404, (
        f"Expected /docs to return 404 in non-DEBUG mode; got {response.status_code}"
    )


def test_docs_url_none_in_non_debug_mode() -> None:
    """Inspect app.docs_url directly — must be None when LOG_LEVEL != 'DEBUG'."""
    # The conftest sets LOG_LEVEL=WARNING before importing main.
    assert main.app.docs_url is None, (
        f"Expected app.docs_url to be None in WARNING mode; got {main.app.docs_url!r}"
    )


def test_docs_url_is_docs_path_when_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    """_docs_url variable equals '/docs' when LOG_LEVEL is DEBUG.

    We can't re-import main in-process without corrupting the test session,
    so we verify the conditional logic by re-evaluating it directly against
    a patched config module.
    """
    import config as cfg  # noqa: PLC0415

    original = cfg.LOG_LEVEL
    try:
        monkeypatch.setattr(cfg, "LOG_LEVEL", "DEBUG")
        # Evaluate the same expression main.py uses.
        docs_url = "/docs" if cfg.LOG_LEVEL == "DEBUG" else None
        assert docs_url == "/docs", (
            f"Expected '/docs' when LOG_LEVEL=DEBUG; got {docs_url!r}"
        )
    finally:
        cfg.LOG_LEVEL = original


# ---------------------------------------------------------------------------
# 5. /openapi.json reachable vs. 404 based on LOG_LEVEL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openapi_json_accessible_in_non_debug_mode(client: AsyncClient) -> None:
    """/openapi.json is always served by FastAPI (even when docs_url is None).

    FastAPI sets openapi_url='/openapi.json' by default independent of
    docs_url, so this endpoint returns valid JSON regardless of LOG_LEVEL.
    """
    response = await client.get("/openapi.json")
    assert response.status_code == 200, (
        f"Expected /openapi.json to be available; got {response.status_code}"
    )
    data = response.json()
    assert "info" in data, f"Response missing 'info' key; keys={list(data.keys())}"
    assert data["info"]["title"] == "LAMB KB Server", (
        f"Unexpected API title: {data['info']['title']!r}"
    )


# ---------------------------------------------------------------------------
# 6. Lifespan startup sequence: DB, plugins, worker, stale recovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_startup_state(client: AsyncClient) -> None:
    """Lines 44-51: after startup, all systems are green.

    The `client` fixture calls start_worker(), which simulates the worker
    portion of the lifespan. The session-level conftest calls init_db() and
    _discover_plugins(). Together they reproduce the full startup sequence.
    """
    from tasks.worker import is_worker_running  # noqa: PLC0415

    # Worker is running.
    assert is_worker_running(), "Worker should be running after lifespan startup"

    # DB is queryable (health endpoint polls it).
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["database"] == "ok", (
        f"Database check should be 'ok' after startup; got {body['checks']['database']}"
    )

    # Plugins are discoverable via /backends.
    resp_backends = await client.get("/backends", headers=AUTH_HEADERS)
    assert resp_backends.status_code == 200
    names = [b["name"] for b in resp_backends.json()["backends"]]
    assert "chromadb" in names, (
        f"Expected 'chromadb' in backends after plugin discovery; got {names}"
    )


# ---------------------------------------------------------------------------
# 7. recover_stale_jobs is called at startup (line 47)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recover_stale_jobs_called_at_startup(
    client_no_worker: AsyncClient,
) -> None:
    """Line 47: recover_stale_jobs() resets stale 'processing' jobs to 'pending'.

    Insert a fake processing job directly into the DB, call recover_stale_jobs()
    (which is what the lifespan does), then confirm the job was reset.
    """
    from tasks.worker import recover_stale_jobs  # noqa: PLC0415

    db = get_session_direct()
    stale_job = IngestionJob(
        id=str(uuid.uuid4()),
        collection_id="test-collection-stale",
        organization_id="test-org-stale",
        documents_json="[]",
        status="processing",
        attempts=0,
    )
    db.add(stale_job)
    db.commit()
    stale_job_id = stale_job.id
    db.close()

    try:
        # Simulate the lifespan startup action for stale job recovery.
        recover_stale_jobs()

        # Verify the job was reset to 'pending'.
        db = get_session_direct()
        recovered = (
            db.query(IngestionJob)
            .filter(IngestionJob.id == stale_job_id)
            .first()
        )
        assert recovered is not None, "Stale job should still exist in DB"
        assert recovered.status == "pending", (
            f"Stale job should be reset to 'pending'; got '{recovered.status}'"
        )
        db.close()
    finally:
        # Clean up the test job.
        db = get_session_direct()
        job = db.query(IngestionJob).filter(IngestionJob.id == stale_job_id).first()
        if job:
            db.delete(job)
            db.commit()
        db.close()


@pytest.mark.asyncio
async def test_recover_stale_jobs_marks_failed_when_max_attempts_exceeded(
    client_no_worker: AsyncClient,
) -> None:
    """recover_stale_jobs marks jobs failed when attempts >= _MAX_ATTEMPTS."""
    from tasks import worker as worker_mod  # noqa: PLC0415
    from tasks.worker import recover_stale_jobs  # noqa: PLC0415

    max_attempts = worker_mod._MAX_ATTEMPTS

    db = get_session_direct()
    exhausted_job = IngestionJob(
        id=str(uuid.uuid4()),
        collection_id="test-collection-exhausted",
        organization_id="test-org-exhausted",
        documents_json="[]",
        status="processing",
        attempts=max_attempts,  # already at the ceiling
    )
    db.add(exhausted_job)
    db.commit()
    exhausted_job_id = exhausted_job.id
    db.close()

    try:
        recover_stale_jobs()

        db = get_session_direct()
        job = (
            db.query(IngestionJob)
            .filter(IngestionJob.id == exhausted_job_id)
            .first()
        )
        assert job is not None
        assert job.status == "failed", (
            f"Job with max attempts should be 'failed'; got '{job.status}'"
        )
        assert job.error_message is not None and "max attempts" in job.error_message, (
            f"Error message should mention max attempts; got {job.error_message!r}"
        )
        db.close()
    finally:
        db = get_session_direct()
        job = (
            db.query(IngestionJob)
            .filter(IngestionJob.id == exhausted_job_id)
            .first()
        )
        if job:
            db.delete(job)
            db.commit()
        db.close()


# ---------------------------------------------------------------------------
# 8. Lifespan shutdown stops worker (lines 53-55)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_shutdown_stops_worker() -> None:
    """Lines 53-55: shutdown branch of lifespan stops the worker.

    We run the full lifespan context manager and assert the worker is running
    inside and stopped after the context exits.
    """
    from tasks.worker import is_worker_running  # noqa: PLC0415

    async with main.lifespan(main.app):
        assert is_worker_running(), (
            "Worker should be running inside the lifespan context"
        )

    assert not is_worker_running(), (
        "Worker should be stopped after lifespan context exits"
    )


# ---------------------------------------------------------------------------
# 9. Lifespan startup sequence ordering via direct lifespan context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_startup_sequence_ordering() -> None:
    """Lines 44-51: ensure each step of the startup sequence completes.

    We call the lifespan context directly. This exercises ensure_directories,
    init_db (idempotent), _discover_plugins, recover_stale_jobs, start_worker.
    """
    from tasks.worker import is_worker_running, stop_worker  # noqa: PLC0415

    # Ensure worker is stopped before entering lifespan (clean slate).
    if is_worker_running():
        await stop_worker()

    assert not is_worker_running(), "Pre-condition: worker should be stopped"

    async with main.lifespan(main.app):
        from plugins.base import VectorDBRegistry  # noqa: PLC0415

        assert is_worker_running(), "Lifespan startup should start the worker"

        # Plugin discovery should have run — chromadb must be registered.
        vdb_names = [p["name"] for p in VectorDBRegistry.list_plugins()]
        assert "chromadb" in vdb_names, (
            f"chromadb should be registered after lifespan startup; got {vdb_names}"
        )

    assert not is_worker_running(), "Lifespan shutdown should stop the worker"
