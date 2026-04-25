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


@pytest.fixture(scope="session")
def kb_server_process(docker_stack: dict) -> Iterator[dict]:
    """Launch the KB server in a subprocess on a free port."""
    port = _free_port()
    data_dir = tempfile.mkdtemp(prefix="kbs-e2e-")
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

    info = {
        "base_url": base_url,
        "port": port,
        "data_dir": data_dir,
        "process": proc,
    }

    try:
        yield info
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def http(kb_server_process: dict) -> Iterator[httpx.Client]:
    """Real HTTP client (loopback TCP) bound to the e2e server."""
    with httpx.Client(
        base_url=kb_server_process["base_url"],
        headers=AUTH_HEADERS,
        timeout=30.0,
    ) as client:
        yield client
