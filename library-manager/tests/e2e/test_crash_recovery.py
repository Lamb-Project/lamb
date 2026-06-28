"""E2E crash recovery: stale 'processing' jobs are recovered on restart.

Simulates an uncontrolled crash (SIGKILL) of an in-flight import by hand-editing
the SQLite state so a job is left ``status='processing'`` (exactly the post-crash
DB shape of a job that was mid-flight). A fresh process on the same data
directory runs ``recover_stale_jobs`` at startup:

* attempts < LM_MAX_JOB_ATTEMPTS → reset to 'pending', reprocessed → 'ready'.
* attempts >= LM_MAX_JOB_ATTEMPTS → marked 'failed' (no retry).

Note: a *successful* import deletes the temp upload file, so to test the
recover-to-ready path we queue the import, kill before processing completes,
and make sure the source temp file is present (recreating it if the worker had
already consumed it) — mirroring a crash that happened while the job was still
in flight and its source still on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _helpers import library_payload, poll_until_ready_sync, text_file

from ._server import ServerProcess

pytestmark = pytest.mark.slow

_CONTENT = "# Recover\n\nbody text to recover after a crash"


def _queue_import(server: ServerProcess) -> tuple[str, str, str]:
    """Create a library + queue a simple import; return (lib_id, item_id, job_id)."""
    with server.client() as c:
        lib = library_payload()
        assert c.post("/libraries", json=lib).status_code == 201
        resp = c.post(
            f"/libraries/{lib['id']}/import/file",
            files=text_file(_CONTENT, "recover.md"),
            data={"plugin_name": "simple_import", "title": "Recover Doc"},
        )
        assert resp.status_code == 202, resp.text
        body = resp.json()
    return lib["id"], body["item_id"], body["job_id"]


def _job_source_path(server: ServerProcess, job_id: str) -> str:
    """Read the temp source_path recorded for a job (server must be stopped)."""
    conn = server.sqlite()
    try:
        row = conn.execute(
            "SELECT source_path FROM import_jobs WHERE id=?", (job_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row and row[0], "job has no source_path"
    return row[0]


def _set_stale_state(server: ServerProcess, job_id: str, item_id: str, attempts: int) -> None:
    """Rewrite the DB to the post-crash shape: job 'processing', item 'processing'."""
    conn = server.sqlite()
    try:
        conn.execute(
            "UPDATE import_jobs SET status='processing', attempts=? WHERE id=?",
            (attempts, job_id),
        )
        conn.execute(
            "UPDATE content_items SET status='processing' WHERE id=?",
            (item_id,),
        )
        conn.commit()
    finally:
        conn.close()


def test_stale_job_recovered_to_ready() -> None:
    """A killed in-flight job (attempts<max) is reset to pending and reprocessed."""
    server = ServerProcess()
    server.start()
    restarted = None
    try:
        lib_id, item_id, job_id = _queue_import(server)

        # Uncontrolled crash before the import is guaranteed complete.
        server.kill()

        # Post-crash in-flight DB shape.
        _set_stale_state(server, job_id, item_id, attempts=1)

        # Ensure the source temp file is on disk for the reprocess (the worker
        # may have consumed it before the kill). Recreating it reflects a crash
        # that happened while the source was still present.
        src = Path(_job_source_path(server, job_id))
        if not src.is_file():
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(_CONTENT, encoding="utf-8")

        # Restart against the same data dir → recover_stale_jobs runs.
        restarted = ServerProcess(data_dir=server.data_dir)
        restarted.start()
        with restarted.client() as c:
            status = poll_until_ready_sync(c, lib_id, item_id, timeout=40)
        assert status == "ready", status
    finally:
        if restarted is not None:
            restarted.stop()
        server.stop()


def test_stale_job_over_max_attempts_marked_failed() -> None:
    """A killed job at/over LM_MAX_JOB_ATTEMPTS is marked failed, not retried."""
    server = ServerProcess(env={"LM_MAX_JOB_ATTEMPTS": "3"})
    server.start()
    restarted = None
    try:
        lib_id, item_id, job_id = _queue_import(server)

        server.kill()
        _set_stale_state(server, job_id, item_id, attempts=3)

        restarted = ServerProcess(
            data_dir=server.data_dir, env={"LM_MAX_JOB_ATTEMPTS": "3"}
        )
        restarted.start()
        with restarted.client() as c:
            status = poll_until_ready_sync(c, lib_id, item_id, timeout=30)
        assert status == "failed", status
    finally:
        if restarted is not None:
            restarted.stop()
        server.stop()
