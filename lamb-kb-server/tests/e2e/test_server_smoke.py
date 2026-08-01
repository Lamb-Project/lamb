"""E2E smoke tests — full HTTP stack over real loopback TCP.

These tests talk to a real uvicorn subprocess (not ASGI in-process).
They exercise the server startup sequence, public vs. protected endpoints,
OpenAPI introspection, plugin capability listings, and graceful shutdown.

All tests in this module use the ``http`` fixture from ``conftest.py``
(an ``httpx.Client`` bound to the session-scoped server) except
``test_graceful_shutdown`` which spawns its own short-lived server process.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

_KB_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(base_url: str, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


# ---------------------------------------------------------------------------
# Basic health + routing
# ---------------------------------------------------------------------------


def test_server_starts_and_health_ok(http: httpx.Client) -> None:
    """GET /health returns 200 with status=ok and both subsystem checks green."""
    r = http.get("/health")
    assert r.status_code == 200

    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["worker"] == "ok"


def test_health_is_public_no_auth(kb_server_process: dict) -> None:
    """GET /health is accessible without an Authorization header."""
    with httpx.Client(base_url=kb_server_process["base_url"], timeout=10.0) as client:
        r = client.get("/health")
    assert r.status_code == 200


def test_unknown_endpoint_returns_404(http: httpx.Client) -> None:
    """GET /nonexistent returns 404 (FastAPI default-route handling)."""
    r = http.get("/nonexistent")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# OpenAPI / docs (only exposed when LOG_LEVEL=DEBUG)
# ---------------------------------------------------------------------------


def test_openapi_json_valid_when_debug(http: httpx.Client) -> None:
    """GET /openapi.json returns valid OpenAPI JSON with expected keys when LOG_LEVEL=DEBUG."""
    r = http.get("/openapi.json")
    assert r.status_code == 200

    schema = r.json()
    # Must have the three top-level OpenAPI keys.
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema

    # Title must match the app name declared in main.py.
    assert schema["info"]["title"] == "LAMB KB Server"


def test_docs_ui_accessible_when_debug(http: httpx.Client) -> None:
    """GET /docs returns an HTML page when LOG_LEVEL=DEBUG."""
    r = http.get("/docs")
    assert r.status_code == 200

    content_type = r.headers.get("content-type", "")
    assert "text/html" in content_type


# ---------------------------------------------------------------------------
# Response time sanity check
# ---------------------------------------------------------------------------


def test_health_ok_within_2s_response_time(http: httpx.Client) -> None:
    """Repinging /health from an already-started server responds in under 2s."""
    start = time.monotonic()
    r = http.get("/health")
    elapsed = time.monotonic() - start

    assert r.status_code == 200
    assert elapsed < 2.0, f"/health took {elapsed:.3f}s — too slow"


# ---------------------------------------------------------------------------
# Plugin capability listings
# ---------------------------------------------------------------------------


def test_backends_lists_chromadb_via_http(http: httpx.Client) -> None:
    """GET /backends (with auth) returns a list that includes 'chromadb'."""
    r = http.get("/backends")
    assert r.status_code == 200

    body = r.json()
    assert "backends" in body

    names = [b["name"] for b in body["backends"]]
    assert "chromadb" in names, f"chromadb not in backends: {names}"


def test_chunking_strategies_lists_all_four(http: httpx.Client) -> None:
    """GET /chunking-strategies returns all four registered strategies."""
    r = http.get("/chunking-strategies")
    assert r.status_code == 200

    body = r.json()
    assert "strategies" in body

    names = {s["name"] for s in body["strategies"]}
    expected = {"simple", "hierarchical", "by_page", "by_section"}
    assert expected.issubset(names), f"Missing strategies: {expected - names}"


def test_embedding_vendors_listed(http: httpx.Client) -> None:
    """GET /embedding-vendors returns openai and ollama (real plugins, no FakeEmbedding in subprocess)."""
    r = http.get("/embedding-vendors")
    assert r.status_code == 200

    body = r.json()
    assert "vendors" in body

    names = {v["name"] for v in body["vendors"]}
    # The subprocess env does NOT register FakeEmbedding; real plugins load.
    assert "openai" in names, f"openai not in vendors: {names}"
    assert "ollama" in names, f"ollama not in vendors: {names}"


# ---------------------------------------------------------------------------
# Graceful shutdown (isolated subprocess — not the session-scoped server)
# ---------------------------------------------------------------------------


def test_graceful_shutdown() -> None:
    """SIGTERM causes the KB server to exit cleanly within 5s.

    This test spins up its own short-lived KB server instance so it doesn't
    disturb the session-scoped ``kb_server_process`` that other tests depend on.
    """
    port = _free_port()
    data_dir = tempfile.mkdtemp(prefix="kbs-sigterm-")
    env = os.environ.copy()
    env.update(
        {
            "LAMB_API_TOKEN": "test-token",
            "DATA_DIR": data_dir,
            "PORT": str(port),
            "LOG_LEVEL": "INFO",
            "VECTOR_DB_QDRANT": "DISABLE",
            "EMBEDDING_LOCAL": "DISABLE",
            "QDRANT_URL": "",
        }
    )

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

    try:
        base_url = f"http://127.0.0.1:{port}"
        ready = _wait_for_health(base_url, timeout=20.0)
        assert ready, "KB server (shutdown test) failed to start within 20s"

        # Confirm it's live before terminating.
        r = httpx.get(f"{base_url}/health", timeout=5.0)
        assert r.status_code == 200

        # Send SIGTERM and wait for clean exit.
        proc.terminate()
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            pytest.fail("KB server did not exit within 5s after SIGTERM")

        # On Unix, a process terminated by SIGTERM has returncode == -signal.SIGTERM
        # (i.e. -15). A graceful exit would be 0. Both indicate clean shutdown
        # (no crash / exception). Only a non-zero positive code means the app
        # failed on its own.
        assert rc in (0, -signal.SIGTERM), (
            f"KB server exited with unexpected returncode {rc} after SIGTERM"
        )
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        import shutil

        shutil.rmtree(data_dir, ignore_errors=True)
