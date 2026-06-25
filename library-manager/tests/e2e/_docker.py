"""Docker helpers for the e2e smoke test of the real shipping image.

The Library Manager has no external container dependency, so the bulk of the
e2e tier runs as a plain subprocess (see ``_server.py``). This module exists
only for the one test that validates the actual deployment artifact: build
``library-manager/Dockerfile``, run it, and confirm it boots, serves, and
enforces the single-instance file lock inside the container.

Everything here degrades gracefully: if the Docker daemon is unavailable the
test skips with an actionable message rather than failing.
"""

from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path

import httpx

# library-manager/ — the Docker build context (contains Dockerfile + backend/).
PROJECT_DIR = Path(__file__).resolve().parents[2]
IMAGE_TAG = "lamb-library-manager:e2e-test"


def docker_available() -> bool:
    """True if a usable Docker daemon is reachable."""
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=15,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def free_port() -> int:
    """Return an unused loopback TCP port for the host-side mapping."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def build_image(timeout: float = 600.0) -> None:
    """Build the real image from the project Dockerfile."""
    subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "."],
        cwd=str(PROJECT_DIR),
        check=True,
        timeout=timeout,
    )


class Container:
    """A running test container, with host-port mapping and exec helpers."""

    def __init__(self, name: str, host_port: int) -> None:
        self.name = name
        self.host_port = host_port
        self.base_url = f"http://127.0.0.1:{host_port}"

    @classmethod
    def run(cls, name: str, host_port: int | None = None) -> Container:
        """Start a detached container mapping host_port → 9091."""
        port = host_port or free_port()
        subprocess.run(
            [
                "docker", "run", "-d", "--rm",
                "--name", name,
                "-e", "LAMB_API_TOKEN=test-token",
                "-e", "LOG_LEVEL=INFO",
                "-p", f"{port}:9091",
                IMAGE_TAG,
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return cls(name, port)

    def wait_healthy(self, timeout: float = 60.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                r = httpx.get(f"{self.base_url}/health", timeout=2.0)
                if r.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RuntimeError(f"container {self.name} not healthy within {timeout}s:\n{self.logs()}")

    def exec(self, *cmd: str) -> subprocess.CompletedProcess:
        """Run a command inside the container."""
        return subprocess.run(
            ["docker", "exec", self.name, *cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def logs(self) -> str:
        try:
            r = subprocess.run(
                ["docker", "logs", self.name], capture_output=True, text=True, timeout=15
            )
            return r.stdout + r.stderr
        except subprocess.SubprocessError:  # pragma: no cover - defensive
            return "(no logs)"

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True, timeout=30)
