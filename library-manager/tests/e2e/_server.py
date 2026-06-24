"""Subprocess control for the e2e tier.

Spawns the real application as a ``uvicorn`` subprocess listening on a
loopback TCP port — exactly how it runs in production, minus the container.
Gives tests fine-grained process control (graceful ``terminate``, hard
``kill``, restart against the same data directory) that a container makes
clumsy, which is why the behaviour-heavy e2e tests use this rather than
Docker.

``stdout``/``stderr`` are redirected to a log file inside the data directory
(never a PIPE) to avoid the classic fill-the-pipe-buffer deadlock when the
parent isn't draining it.
"""

from __future__ import annotations

import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

# library-manager/backend — the working directory uvicorn runs from.
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"


def free_port() -> int:
    """Return an unused loopback TCP port."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerProcess:
    """A managed ``uvicorn main:app`` subprocess for one data directory.

    Parameters mirror the knobs the e2e tests need:

    * ``data_dir`` — reuse an existing dir to test restart/recovery; omit for
      a fresh throwaway dir.
    * ``port`` — omit to grab a free one.
    * ``env`` — extra environment (e.g. ``LM_MAX_JOB_ATTEMPTS``).
    """

    def __init__(
        self,
        data_dir: str | os.PathLike | None = None,
        port: int | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(tempfile.mkdtemp(prefix="lm-e2e-"))
        self.owns_data_dir = data_dir is None
        self.port = port or free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.env = env or {}
        self.proc: subprocess.Popen | None = None
        self.log_path = self.data_dir / "server.log"

    # -- lifecycle ----------------------------------------------------------

    def start(self, wait: bool = True, timeout: float = 30.0) -> ServerProcess:
        """Launch the subprocess; optionally block until ``/health`` is 200."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["LAMB_API_TOKEN"] = "test-token"
        env["DATA_DIR"] = str(self.data_dir)
        env.setdefault("LOG_LEVEL", "INFO")
        env.update(self.env)
        log = open(self.log_path, "ab")  # noqa: SIM115 — closed in stop()
        self._log_file = log
        self.proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "main:app",
                "--host", "127.0.0.1", "--port", str(self.port),
            ],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        if wait:
            self.wait_healthy(timeout=timeout)
        return self

    def wait_healthy(self, timeout: float = 30.0) -> None:
        """Block until the server answers ``/health`` 200, or raise."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                raise RuntimeError(
                    f"server exited early (code={self.proc.returncode}):\n{self.read_log()}"
                )
            try:
                r = httpx.get(f"{self.base_url}/health", timeout=1.0)
                if r.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        raise RuntimeError(f"server not healthy within {timeout}s:\n{self.read_log()}")

    def wait_exit(self, timeout: float = 15.0) -> int | None:
        """Block until the process exits; return its code (or None on timeout)."""
        if self.proc is None:
            return None
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def kill(self) -> None:
        """Hard kill (SIGKILL) — simulates an uncontrolled crash."""
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGKILL)
            self.proc.wait(timeout=10)
        self._close_log()

    def terminate(self) -> int | None:
        """Graceful shutdown (SIGTERM) — exercises the lifespan shutdown path."""
        if self.proc is None:
            return None
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
        code = self.wait_exit(timeout=15.0)
        if code is None:  # pragma: no cover - defensive
            self.proc.send_signal(signal.SIGKILL)
            self.proc.wait(timeout=10)
        self._close_log()
        return code

    def stop(self) -> None:
        """Best-effort teardown: terminate the process, free the data dir."""
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            if self.wait_exit(timeout=10.0) is None:  # pragma: no cover - defensive
                self.proc.send_signal(signal.SIGKILL)
                self.proc.wait(timeout=10)
        self._close_log()
        if self.owns_data_dir:
            import shutil  # noqa: PLC0415

            shutil.rmtree(self.data_dir, ignore_errors=True)

    # -- helpers ------------------------------------------------------------

    def client(self, **kwargs) -> httpx.Client:
        """A real HTTP client bound to this server's base URL with auth."""
        from _helpers import AUTH_HEADERS  # noqa: PLC0415

        headers = {**AUTH_HEADERS, **kwargs.pop("headers", {})}
        return httpx.Client(base_url=self.base_url, headers=headers, timeout=30.0, **kwargs)

    @property
    def db_path(self) -> Path:
        """Path to this server's SQLite database file."""
        return self.data_dir / "library-manager.db"

    def sqlite(self) -> sqlite3.Connection:
        """Open the server's SQLite DB directly (only while the server is stopped)."""
        return sqlite3.connect(str(self.db_path))

    def read_log(self) -> str:
        """Return the captured server log (for failure diagnostics)."""
        try:
            return self.log_path.read_text(errors="replace")
        except OSError:  # pragma: no cover - defensive
            return "(no log)"

    def _close_log(self) -> None:
        log = getattr(self, "_log_file", None)
        if log is not None and not log.closed:
            log.close()
