"""E2E crash-recovery tests: SIGKILL a live server and verify that restarting
the server with the same data directory results in full state recovery.

Each test owns an isolated ``data_dir`` and manages its own server lifecycle.
The session-scoped ``kb_server_process`` fixture is intentionally NOT used
here because these tests require independent start/kill/restart cycles.

``docker_stack`` is the only session fixture used (Ollama container for
real embeddings).  Vector storage uses Qdrant **local on-disk mode** so
each test's ``data_dir`` is fully self-contained and isolated — no shared
remote Qdrant instance is involved.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

# ---------------------------------------------------------------------------
# Module-level helpers (no fixtures)
# ---------------------------------------------------------------------------

_KB_ROOT = Path(__file__).resolve().parent.parent.parent
_AUTH_HEADERS = {"Authorization": "Bearer test-token"}

# How long to wait for a job to reach a given status before giving up.
_JOB_POLL_TIMEOUT = 120.0
_JOB_POLL_INTERVAL = 0.5


def _free_port() -> int:
    """Return an OS-assigned free TCP port on loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_health(base_url: str, timeout: float = 30.0) -> bool:
    """Poll GET /health until 200 or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _start_server(data_dir: str, port: int, **extra_env: str) -> subprocess.Popen:
    """Launch the KB server subprocess.

    Uses Qdrant in **local on-disk mode** (``QDRANT_URL`` is intentionally
    left empty) so each test's ``data_dir`` is a fully self-contained,
    isolated vector store. This avoids cross-test contamination from partial
    writes left by a SIGKILL on a shared remote Qdrant instance.

    Args:
        data_dir: Path to the persistent data directory.
        port: TCP port for uvicorn to bind.
        **extra_env: Additional environment variables to overlay.

    Returns:
        Running ``Popen`` handle (stdout+stderr merged into stdout pipe).
    """
    env = os.environ.copy()
    env.update(
        {
            "LAMB_API_TOKEN": "test-token",
            "DATA_DIR": data_dir,
            "PORT": str(port),
            "LOG_LEVEL": "WARNING",
            "MAX_CONCURRENT_INGESTIONS": "1",
            "INGESTION_TASK_TIMEOUT_SECONDS": "90",
            # Enable Qdrant plugin; empty QDRANT_URL → local on-disk client.
            "VECTOR_DB_QDRANT": "ENABLE",
            "QDRANT_URL": "",
            "EMBEDDING_LOCAL": "DISABLE",
        }
    )
    env.update(extra_env)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--app-dir",
            str(_KB_ROOT / "backend"),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(_KB_ROOT),
    )
    return proc


def _kill_server(proc: subprocess.Popen, *, signum: int = signal.SIGKILL) -> None:
    """Send *signum* to *proc* and wait for it to exit."""
    try:
        os.kill(proc.pid, signum)
    except ProcessLookupError:
        return  # already gone
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _poll_job_status(
    client: httpx.Client,
    job_id: str,
    *,
    target_statuses: tuple[str, ...] = ("completed", "failed"),
    timeout: float = _JOB_POLL_TIMEOUT,
) -> dict:
    """Poll GET /jobs/{job_id} until the job reaches one of *target_statuses*."""
    deadline = time.monotonic() + timeout
    last_body: dict = {}
    while time.monotonic() < deadline:
        r = client.get(f"/jobs/{job_id}", headers=_AUTH_HEADERS, timeout=10.0)
        assert r.status_code == 200, (
            f"GET /jobs/{job_id} returned {r.status_code}: {r.text}"
        )
        last_body = r.json()
        if last_body["status"] in target_statuses:
            return last_body
        time.sleep(_JOB_POLL_INTERVAL)
    raise AssertionError(
        f"Job {job_id} did not reach {target_statuses} within {timeout}s; "
        f"last status: {last_body}"
    )


# ---------------------------------------------------------------------------
# Shared payload builders
# ---------------------------------------------------------------------------


def _make_collection_payload(ollama_url: str, name: str = "crash-test") -> dict:
    """Return a ``POST /collections`` body using Ollama embeddings + Qdrant local."""
    ollama_endpoint = f"{ollama_url}/api/embeddings"
    return {
        "organization_id": "org-crash-test",
        "name": name,
        "chunking_strategy": "simple",
        # chunk_overlap must be < chunk_size — use chunk_overlap (not 'overlap').
        "chunking_params": {"chunk_size": 500, "chunk_overlap": 50},
        "embedding": {
            "vendor": "ollama",
            "model": "nomic-embed-text",
            "api_endpoint": ollama_endpoint,
        },
        "vector_db_backend": "qdrant",
    }


def _make_add_content_payload(
    ollama_url: str, text: str, source_id: str = "item-1"
) -> dict:
    """Return a ``POST /collections/{id}/add-content`` body."""
    ollama_endpoint = f"{ollama_url}/api/embeddings"
    return {
        "documents": [
            {
                "source_item_id": source_id,
                "title": f"Doc {source_id}",
                "text": text,
            }
        ],
        "embedding_credentials": {
            "api_key": "",
            "api_endpoint": ollama_endpoint,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSigkillThenRestartResumesPendingJobs:
    """Queue several jobs, SIGKILL mid-flight, restart, confirm all terminal."""

    def test_sigkill_then_restart_resumes_pending_jobs(
        self, docker_stack: dict
    ) -> None:
        ollama_url = docker_stack["ollama_url"]

        data_dir = tempfile.mkdtemp(prefix="kbs-crash-")
        port1 = _free_port()
        proc1: subprocess.Popen | None = None

        try:
            # --- Start server #1 ---
            proc1 = _start_server(data_dir, port1)
            base1 = f"http://127.0.0.1:{port1}"
            assert _wait_health(base1, timeout=30), "Server #1 failed to start"

            ollama_endpoint = f"{ollama_url}/api/embeddings"

            with httpx.Client(base_url=base1, timeout=30.0) as client:
                # Create a collection that uses Ollama (real embedding, slower than fake).
                col_r = client.post(
                    "/collections",
                    json=_make_collection_payload(ollama_url, name="resume-test"),
                    headers=_AUTH_HEADERS,
                )
                assert col_r.status_code == 201, col_r.text
                col_id = col_r.json()["id"]

                # Queue 5 ingestion jobs back-to-back.
                # MAX_CONCURRENT_INGESTIONS=1 means at most 1 runs; others stay pending.
                job_ids: list[str] = []
                for i in range(5):
                    text = (
                        f"Document {i}: LAMB is an open-source platform for educators "
                        f"that provides AI-powered learning assistants. "
                        f"This is unique content for document number {i}."
                    )
                    r = client.post(
                        f"/collections/{col_id}/add-content",
                        json={
                            "documents": [
                                {
                                    "source_item_id": f"item-{i}",
                                    "title": f"Doc {i}",
                                    "text": text,
                                }
                            ],
                            "embedding_credentials": {
                                "api_key": "",
                                "api_endpoint": ollama_endpoint,
                            },
                        },
                        headers=_AUTH_HEADERS,
                    )
                    assert r.status_code == 202, r.text
                    job_ids.append(r.json()["job_id"])

                # Wait until at least one job transitions to 'processing' so the
                # SIGKILL definitely interrupts an in-flight job.
                deadline = time.monotonic() + 30.0
                found_processing = False
                while time.monotonic() < deadline and not found_processing:
                    for jid in job_ids:
                        jr = client.get(f"/jobs/{jid}", headers=_AUTH_HEADERS)
                        if jr.status_code == 200 and jr.json()["status"] == "processing":
                            found_processing = True
                            break
                    if not found_processing:
                        time.sleep(0.3)
                # Even if we didn't observe 'processing' (fast Ollama on GPU),
                # the SIGKILL still exercises the recovery path.

            # --- SIGKILL server #1 ---
            _kill_server(proc1, signum=signal.SIGKILL)
            proc1 = None

            # --- Start server #2 with the SAME data_dir ---
            port2 = _free_port()
            proc2 = _start_server(data_dir, port2)
            base2 = f"http://127.0.0.1:{port2}"
            try:
                assert _wait_health(base2, timeout=30), "Server #2 failed to start"

                # recover_stale_jobs() runs at startup: any 'processing' jobs are
                # reset to 'pending' and the worker picks them all up.
                with httpx.Client(base_url=base2, timeout=30.0) as client2:
                    for jid in job_ids:
                        final = _poll_job_status(
                            client2,
                            jid,
                            target_statuses=("completed", "failed"),
                            timeout=_JOB_POLL_TIMEOUT,
                        )
                        # Jobs may fail if their in-memory credentials were lost
                        # (ADR-4).  The key invariant is that every job reaches a
                        # terminal state — none should remain stuck.
                        assert final["status"] in ("completed", "failed"), (
                            f"Job {jid} stuck in non-terminal state: {final['status']}"
                        )
            finally:
                _kill_server(proc2)
        finally:
            if proc1 is not None:
                _kill_server(proc1)
            shutil.rmtree(data_dir, ignore_errors=True)


def test_sigkill_preserves_completed_jobs(docker_stack: dict) -> None:
    """A completed job is still retrievable after SIGKILL + restart."""
    ollama_url = docker_stack["ollama_url"]

    data_dir = tempfile.mkdtemp(prefix="kbs-crash-")
    port = _free_port()
    proc: subprocess.Popen | None = None

    try:
        proc = _start_server(data_dir, port)
        base = f"http://127.0.0.1:{port}"
        assert _wait_health(base, timeout=30), "Server failed to start"

        with httpx.Client(base_url=base, timeout=30.0) as client:
            # Create collection.
            col_r = client.post(
                "/collections",
                json=_make_collection_payload(ollama_url, name="preserve-jobs-test"),
                headers=_AUTH_HEADERS,
            )
            assert col_r.status_code == 201, col_r.text
            col_id = col_r.json()["id"]

            # Ingest one document and wait for completion.
            add_r = client.post(
                f"/collections/{col_id}/add-content",
                json=_make_add_content_payload(
                    ollama_url,
                    "LAMB helps teachers build AI learning assistants easily.",
                    source_id="item-preserve",
                ),
                headers=_AUTH_HEADERS,
            )
            assert add_r.status_code == 202, add_r.text
            job_id = add_r.json()["job_id"]

            # Poll until completed.
            final = _poll_job_status(
                client, job_id, target_statuses=("completed", "failed")
            )
            assert final["status"] == "completed", (
                f"Initial ingestion failed: {final.get('error_message')}"
            )
            chunk_count_before = final["chunks_created"]

        # SIGKILL.
        _kill_server(proc, signum=signal.SIGKILL)
        proc = None

        # Restart with same data_dir.
        port2 = _free_port()
        proc = _start_server(data_dir, port2)
        base2 = f"http://127.0.0.1:{port2}"
        assert _wait_health(base2, timeout=30), "Server failed to restart"

        with httpx.Client(base_url=base2, timeout=30.0) as client2:
            # Job should still be 'completed' — the SQLite row survived the kill.
            jr = client2.get(f"/jobs/{job_id}", headers=_AUTH_HEADERS)
            assert jr.status_code == 200, jr.text
            job_data = jr.json()
            assert job_data["status"] == "completed", (
                f"Job status changed after restart: {job_data['status']}"
            )
            assert job_data["chunks_created"] == chunk_count_before

            # Collection should still be present and have correct counters.
            cr = client2.get(f"/collections/{col_id}", headers=_AUTH_HEADERS)
            assert cr.status_code == 200, cr.text
            col_data = cr.json()
            assert col_data["chunk_count"] == chunk_count_before, (
                f"chunk_count changed: {col_data['chunk_count']} != {chunk_count_before}"
            )
    finally:
        if proc is not None:
            _kill_server(proc)
        shutil.rmtree(data_dir, ignore_errors=True)


def test_sigkill_preserves_collection_metadata(docker_stack: dict) -> None:
    """Collections created before SIGKILL are still listed and accessible after restart."""
    ollama_url = docker_stack["ollama_url"]

    data_dir = tempfile.mkdtemp(prefix="kbs-crash-")
    port = _free_port()
    proc: subprocess.Popen | None = None

    try:
        proc = _start_server(data_dir, port)
        base = f"http://127.0.0.1:{port}"
        assert _wait_health(base, timeout=30), "Server failed to start"

        col_ids: list[str] = []
        with httpx.Client(base_url=base, timeout=30.0) as client:
            for i in range(3):
                r = client.post(
                    "/collections",
                    json=_make_collection_payload(ollama_url, name=f"meta-test-{i}"),
                    headers=_AUTH_HEADERS,
                )
                assert r.status_code == 201, r.text
                col_ids.append(r.json()["id"])

        assert len(col_ids) == 3

        # SIGKILL.
        _kill_server(proc, signum=signal.SIGKILL)
        proc = None

        # Restart.
        port2 = _free_port()
        proc = _start_server(data_dir, port2)
        base2 = f"http://127.0.0.1:{port2}"
        assert _wait_health(base2, timeout=30), "Server failed to restart"

        with httpx.Client(base_url=base2, timeout=30.0) as client2:
            # List endpoint must show all 3.
            list_r = client2.get(
                "/collections",
                params={"organization_id": "org-crash-test"},
                headers=_AUTH_HEADERS,
            )
            assert list_r.status_code == 200, list_r.text
            listed_ids = {c["id"] for c in list_r.json()["collections"]}
            for cid in col_ids:
                assert cid in listed_ids, (
                    f"Collection {cid} missing from list after restart"
                )

            # Each collection must be individually accessible.
            for cid in col_ids:
                gr = client2.get(f"/collections/{cid}", headers=_AUTH_HEADERS)
                assert gr.status_code == 200, (
                    f"GET /collections/{cid} returned {gr.status_code} after restart"
                )
    finally:
        if proc is not None:
            _kill_server(proc)
        shutil.rmtree(data_dir, ignore_errors=True)


def test_sigkill_preserves_chromadb_storage(docker_stack: dict) -> None:
    """Vectors ingested before SIGKILL are still queryable after restart.

    Qdrant local-disk mode writes segment files to ``data_dir/storage/...``
    alongside the SQLite database.  Both survive the crash and the restarted
    server should serve identical query results.
    """
    ollama_url = docker_stack["ollama_url"]

    data_dir = tempfile.mkdtemp(prefix="kbs-crash-")
    port = _free_port()
    proc: subprocess.Popen | None = None

    try:
        proc = _start_server(data_dir, port)
        base = f"http://127.0.0.1:{port}"
        assert _wait_health(base, timeout=30), "Server failed to start"

        ollama_endpoint = f"{ollama_url}/api/embeddings"
        query_text = "LAMB open-source educators AI learning"

        # 5 short documents → 5 vectors after simple chunking (each fits in 500 chars).
        docs = [
            {
                "source_item_id": f"vec-item-{i}",
                "title": f"Vector doc {i}",
                "text": (
                    f"LAMB is an open-source platform for educators. "
                    f"Document number {i} contains unique identifiable content {i * 7}."
                ),
            }
            for i in range(5)
        ]

        with httpx.Client(base_url=base, timeout=30.0) as client:
            # Create collection.
            col_r = client.post(
                "/collections",
                json=_make_collection_payload(ollama_url, name="vector-persist-test"),
                headers=_AUTH_HEADERS,
            )
            assert col_r.status_code == 201, col_r.text
            col_id = col_r.json()["id"]

            # Ingest all 5 documents in a single job.
            add_r = client.post(
                f"/collections/{col_id}/add-content",
                json={
                    "documents": docs,
                    "embedding_credentials": {
                        "api_key": "",
                        "api_endpoint": ollama_endpoint,
                    },
                },
                headers=_AUTH_HEADERS,
            )
            assert add_r.status_code == 202, add_r.text
            job_id = add_r.json()["job_id"]

            final = _poll_job_status(
                client, job_id, target_statuses=("completed", "failed")
            )
            assert final["status"] == "completed", (
                f"Ingestion failed: {final.get('error_message')}"
            )
            chunks_before = final["chunks_created"]
            assert chunks_before >= 5

            # Baseline query before kill.
            qr = client.post(
                f"/collections/{col_id}/query",
                json={
                    "query_text": query_text,
                    "top_k": 5,
                    "embedding_credentials": {
                        "api_key": "",
                        "api_endpoint": ollama_endpoint,
                    },
                },
                headers=_AUTH_HEADERS,
            )
            assert qr.status_code == 200, qr.text
            results_before = qr.json()["results"]
            assert len(results_before) >= 1, "Expected at least 1 result before kill"
            top_score_before = results_before[0]["score"]

        # SIGKILL.
        _kill_server(proc, signum=signal.SIGKILL)
        proc = None

        # Restart with same data_dir.
        port2 = _free_port()
        proc = _start_server(data_dir, port2)
        base2 = f"http://127.0.0.1:{port2}"
        assert _wait_health(base2, timeout=30), "Server failed to restart"

        with httpx.Client(base_url=base2, timeout=30.0) as client2:
            # Query after restart — vectors must still be present.
            qr2 = client2.post(
                f"/collections/{col_id}/query",
                json={
                    "query_text": query_text,
                    "top_k": 5,
                    "embedding_credentials": {
                        "api_key": "",
                        "api_endpoint": ollama_endpoint,
                    },
                },
                headers=_AUTH_HEADERS,
            )
            assert qr2.status_code == 200, qr2.text
            results_after = qr2.json()["results"]
            assert len(results_after) >= 1, "Expected at least 1 result after restart"

            # Top similarity score should be essentially the same.
            top_score_after = results_after[0]["score"]
            assert abs(top_score_after - top_score_before) < 0.05, (
                f"Top score changed significantly after restart: "
                f"{top_score_before:.4f} → {top_score_after:.4f}"
            )
    finally:
        if proc is not None:
            _kill_server(proc)
        shutil.rmtree(data_dir, ignore_errors=True)


def test_graceful_sigterm(docker_stack: dict) -> None:
    """SIGTERM causes the server to exit cleanly; /health is up after restart."""
    # docker_stack used only to ensure Ollama container is running; we don't
    # need ollama_url here since no ingestion is performed in this test.
    _ = docker_stack  # mark used

    data_dir = tempfile.mkdtemp(prefix="kbs-crash-")
    port = _free_port()
    proc: subprocess.Popen | None = None

    try:
        proc = _start_server(data_dir, port)
        base = f"http://127.0.0.1:{port}"
        assert _wait_health(base, timeout=30), "Server failed to start"

        # Send SIGTERM — uvicorn handles this as a graceful shutdown.
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # already gone

        # Expect exit within 10 seconds.
        try:
            returncode = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            pytest.fail("Server did not exit within 10s after SIGTERM")

        proc = None
        # SIGTERM → returncode is typically 143 (128+15) or 0 (clean handler).
        assert returncode in (0, -signal.SIGTERM, 143), (
            f"Unexpected exit code after SIGTERM: {returncode}"
        )

        # Restart with same data_dir — server must come back healthy.
        port2 = _free_port()
        proc = _start_server(data_dir, port2)
        base2 = f"http://127.0.0.1:{port2}"
        assert _wait_health(base2, timeout=30), (
            "Server did not become healthy after restart"
        )

        hr = httpx.get(f"{base2}/health", timeout=5.0)
        assert hr.status_code == 200, hr.text
    finally:
        if proc is not None:
            _kill_server(proc)
        shutil.rmtree(data_dir, ignore_errors=True)
