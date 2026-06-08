"""E2E-tier fixtures: real uvicorn subprocess + docker stack + VCR.

The docker-compose stack (Qdrant + Ollama) is brought up at session start
and torn down at session end via ``tests/e2e/_compose.py``. If Docker
isn't available the entire e2e tier is skipped with a clear message.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from tests._helpers import AUTH_HEADERS  # noqa: F401  (re-exported for tests)

_E2E_ROOT = Path(__file__).resolve().parent
_KB_ROOT = _E2E_ROOT.parent.parent


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _container_host_port(container_name: str, container_port: int) -> int | None:
    """Return the host port mapped from a running container's internal port, or None.

    Uses ``docker port`` which reliably returns the host binding even when the
    container is in a non-default network where ``docker inspect`` Ports may be
    empty.
    """
    try:
        result = subprocess.run(
            ["docker", "port", container_name, str(container_port)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            return None
        # Output format: "0.0.0.0:PORT\n[::]:PORT\n"
        for line in result.stdout.splitlines():
            line = line.strip()
            if ":" in line:
                host_port = line.rsplit(":", 1)[-1]
                if host_port.isdigit():
                    return int(host_port)
    except Exception:
        pass
    return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http(url: str, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _wait_for_ollama_model(ollama_url: str, model: str, timeout: float = 300.0) -> bool:
    """Poll ``/api/tags`` until *model* is listed (pull complete)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                if any(name.startswith(model) for name in models):
                    return True
        except Exception:
            pass
        time.sleep(2.0)
    return False


@pytest.fixture(scope="session")
def docker_stack() -> Iterator[dict]:
    """Bring up Qdrant + Ollama containers for the e2e tier.

    If ``QDRANT_TEST_PORT`` and ``OLLAMA_TEST_PORT`` environment variables are
    already set (i.e. the stack was started externally before the test session),
    the fixture skips compose_up/down and simply verifies the containers are
    reachable at those ports. This allows running the e2e tier against a
    pre-started stack without port conflicts or container name collisions.
    """
    if not _docker_available():
        pytest.skip("Docker not available; skipping e2e tier")

    from tests.e2e._compose import compose_down, compose_up

    # --- Pre-started stack mode -------------------------------------------
    # When the orchestrator (or CI) has already brought up the stack, detect
    # it via env vars OR by inspecting the well-known container names. This
    # avoids port conflicts and container name collisions when re-running tests.
    pre_qdrant_port = os.environ.get("QDRANT_TEST_PORT")
    pre_ollama_port = os.environ.get("OLLAMA_TEST_PORT")

    # Fall back to docker inspect if env vars not set but containers exist.
    if not pre_qdrant_port:
        discovered = _container_host_port("kbs-test-qdrant", 6333)
        if discovered:
            pre_qdrant_port = str(discovered)
    if not pre_ollama_port:
        discovered = _container_host_port("kbs-test-ollama", 11434)
        if discovered:
            pre_ollama_port = str(discovered)

    if pre_qdrant_port and pre_ollama_port:
        qdrant_url = f"http://127.0.0.1:{pre_qdrant_port}"
        ollama_url = f"http://127.0.0.1:{pre_ollama_port}"
        if not _wait_for_http(f"{qdrant_url}/", timeout=10):
            pytest.skip(f"Pre-started Qdrant not reachable at {qdrant_url}")
        if not _wait_for_http(f"{ollama_url}/api/tags", timeout=10):
            pytest.skip(f"Pre-started Ollama not reachable at {ollama_url}")
        if not _wait_for_ollama_model(ollama_url, "nomic-embed-text", timeout=300):
            pytest.skip(
                f"Pre-started Ollama at {ollama_url} does not have "
                f"nomic-embed-text pulled (run: ollama pull nomic-embed-text)"
            )
        yield {
            "qdrant_url": qdrant_url,
            "ollama_url": ollama_url,
            "qdrant_port": int(pre_qdrant_port),
            "ollama_port": int(pre_ollama_port),
        }
        return  # do NOT tear down a pre-started stack

    # --- Self-managed stack mode ------------------------------------------
    qdrant_port = _free_port()
    ollama_port = _free_port()
    env = {
        "QDRANT_TEST_PORT": str(qdrant_port),
        "OLLAMA_TEST_PORT": str(ollama_port),
    }

    try:
        compose_up(env)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"docker compose up failed: {exc}")

    qdrant_url = f"http://127.0.0.1:{qdrant_port}"
    ollama_url = f"http://127.0.0.1:{ollama_port}"

    if not _wait_for_http(f"{qdrant_url}/", timeout=30):
        compose_down(env)
        pytest.skip("Qdrant container failed to become ready")
    if not _wait_for_http(f"{ollama_url}/api/tags", timeout=60):
        compose_down(env)
        pytest.skip("Ollama container failed to become ready")
    # Wait for the embedding model to finish pulling — /api/tags returns 200
    # before the model is ready, so tests racing the pull see 404s.
    if not _wait_for_ollama_model(ollama_url, "nomic-embed-text", timeout=300):
        compose_down(env)
        pytest.skip("Ollama failed to pull nomic-embed-text within 300s")

    info = {
        "qdrant_url": qdrant_url,
        "ollama_url": ollama_url,
        "qdrant_port": qdrant_port,
        "ollama_port": ollama_port,
    }
    try:
        yield info
    finally:
        compose_down(env)


def _spawn_kb_server(data_dir: str, env_overrides: dict[str, str] | None = None) -> dict:
    """Spawn a uvicorn KB server subprocess against *data_dir*.

    Returns an ``info`` dict (base_url, port, data_dir, process). Caller is
    responsible for stopping the server via :func:`_stop_kb_server`.
    """
    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "LAMB_API_TOKEN": "test-token",
            "DATA_DIR": data_dir,
            "PORT": str(port),
            "LOG_LEVEL": "DEBUG",  # exposes /docs and /openapi.json
            "MAX_CONCURRENT_INGESTIONS": "2",
            "INGESTION_TASK_TIMEOUT_SECONDS": "30",
            "VECTOR_DB_QDRANT": "ENABLE",
            "EMBEDDING_LOCAL": "DISABLE",
            "QDRANT_URL": "",  # local on-disk mode by default
        }
    )
    if env_overrides:
        env.update(env_overrides)

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

    base_url = f"http://127.0.0.1:{port}"
    if not _wait_for_http(f"{base_url}/health", timeout=30):
        proc.terminate()
        out = proc.stdout.read().decode() if proc.stdout else ""
        pytest.fail(f"KB server failed to start:\n{out[-2000:]}")

    return {
        "base_url": base_url,
        "port": port,
        "data_dir": data_dir,
        "process": proc,
    }


def _stop_kb_server(info: dict) -> None:
    """Terminate a server spawned by :func:`_spawn_kb_server`. Idempotent."""
    proc = info["process"]
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture(scope="session")
def kb_server_process_standalone() -> Iterator[dict]:
    """Launch the KB server in a subprocess on a free port — no Docker required.

    Use this fixture for tests that only need a live KB server (auth, routing,
    error paths, capability listings) and do NOT need real Ollama or Qdrant
    services.  Tests that perform actual ingestion with real embeddings must
    use ``kb_server_process`` (which depends on ``docker_stack``).
    """
    data_dir = tempfile.mkdtemp(prefix="kbs-e2e-sa-")
    info = _spawn_kb_server(data_dir=data_dir)
    try:
        yield info
    finally:
        _stop_kb_server(info)
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def kb_server_process(docker_stack: dict) -> Iterator[dict]:
    """Launch the KB server in a subprocess on a free port."""
    data_dir = tempfile.mkdtemp(prefix="kbs-e2e-")
    info = _spawn_kb_server(data_dir=data_dir)
    try:
        yield info
    finally:
        _stop_kb_server(info)
        shutil.rmtree(data_dir, ignore_errors=True)


def _make_no_chromadb_fixture(ollama_url: str) -> Iterator[dict]:
    """Shared implementation for the two-phase 503-backend-unavailable fixture.

    Phase 1: spawn a default-config server, create a chromadb-backed collection
    (using *ollama_url* for the embedding endpoint — Ollama is never contacted),
    stop the server. Phase 2: spawn a second server against the same DATA_DIR
    with ``VECTOR_DB_CHROMADB=DISABLE`` so the persisted collection's backend is
    no longer registered. Yields ``{"info": phase2_info, "collection_id": str}``.
    """
    data_dir = tempfile.mkdtemp(prefix="kbs-e2e-503-")

    # Phase 1 — chromadb registered, create the collection.
    info1 = _spawn_kb_server(data_dir=data_dir)
    try:
        payload = {
            "organization_id": "org-503",
            "name": "kb-503",
            "description": "503 e2e test",
            "chunking_strategy": "simple",
            "chunking_params": {"chunk_size": 400, "chunk_overlap": 0},
            "embedding": {
                "vendor": "ollama",
                "model": "nomic-embed-text",
                "api_endpoint": f"{ollama_url}/api/embeddings",
            },
            "vector_db_backend": "chromadb",
        }
        with httpx.Client(base_url=info1["base_url"], headers=AUTH_HEADERS, timeout=30.0) as client:
            r = client.post("/collections", json=payload)
            assert r.status_code == 201, f"phase-1 create failed: {r.status_code} {r.text}"
            collection_id = r.json()["id"]
    finally:
        _stop_kb_server(info1)

    # Phase 2 — chromadb disabled; persisted collection now points at a
    # backend that is not registered, so /query returns 503.
    info2 = _spawn_kb_server(data_dir=data_dir, env_overrides={"VECTOR_DB_CHROMADB": "DISABLE"})
    try:
        yield {"info": info2, "collection_id": collection_id}
    finally:
        _stop_kb_server(info2)
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def kb_server_no_chromadb_standalone() -> Iterator[dict]:
    """Two-phase 503-backend-unavailable fixture — no Docker required.

    Ollama is listed as the embedding vendor in the collection payload but is
    never contacted: 503 fires before the embedding callable is invoked, so
    a dummy (unreachable) endpoint suffices.
    """
    yield from _make_no_chromadb_fixture("http://127.0.0.1:19999")


@pytest.fixture
def kb_server_no_chromadb(docker_stack: dict) -> Iterator[dict]:
    """Two-phase fixture for testing 503 backend-unavailable.

    Phase 1: spawn a default-config server, create a chromadb-backed collection,
    stop the server. Phase 2: spawn a second server against the same DATA_DIR
    with ``VECTOR_DB_CHROMADB=DISABLE`` so the persisted collection's backend is
    no longer registered. Yields ``{"info": phase2_info, "collection_id": str}``.

    Depends on docker_stack only because Ollama is the simplest registered
    embedding vendor available to a fresh subprocess (the test fake plugin
    only registers in the test process). Ollama is not actually contacted —
    503 fires before the embedding callable is invoked.
    """
    yield from _make_no_chromadb_fixture(docker_stack["ollama_url"])


@pytest.fixture
def http(kb_server_process: dict) -> Iterator[httpx.Client]:
    """Real HTTP client (loopback TCP) bound to the e2e server."""
    with httpx.Client(
        base_url=kb_server_process["base_url"],
        headers=AUTH_HEADERS,
        timeout=30.0,
    ) as client:
        yield client


@pytest.fixture
def http_standalone(kb_server_process_standalone: dict) -> Iterator[httpx.Client]:
    """Real HTTP client bound to the standalone (no-Docker) e2e server."""
    with httpx.Client(
        base_url=kb_server_process_standalone["base_url"],
        headers=AUTH_HEADERS,
        timeout=30.0,
    ) as client:
        yield client
