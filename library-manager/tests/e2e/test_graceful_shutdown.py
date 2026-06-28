"""E2E graceful shutdown: SIGTERM runs the lifespan shutdown and exits 0.

A SIGTERM to uvicorn triggers the FastAPI ``lifespan`` shutdown (which calls
``stop_worker``) and the process exits cleanly with code 0.
"""

from __future__ import annotations

import pytest

from ._server import ServerProcess

pytestmark = pytest.mark.slow


def test_sigterm_exits_cleanly() -> None:
    """SIGTERM runs the lifespan shutdown to completion and the process exits.

    Uvicorn (launched via ``python -m uvicorn``) runs the FastAPI lifespan
    shutdown — ``stop_worker`` — to completion on SIGTERM, then exits. The exit
    code is either 0 or the signal code (-SIGTERM); both are clean given the
    lifespan shutdown completed (verified in the log).
    """
    import signal  # noqa: PLC0415

    server = ServerProcess()
    server.start()
    try:
        server.wait_healthy(timeout=5)
        code = server.terminate()
        # Process is no longer running.
        assert server.proc.poll() is not None, "process should no longer be running"
        # Clean shutdown: exit 0 or terminated by the SIGTERM we sent.
        assert code in (0, -signal.SIGTERM), f"unexpected exit code {code}\n{server.read_log()}"
        # The lifespan shutdown ran to completion.
        log = server.read_log()
        assert "Application shutdown complete" in log, log
    finally:
        server.stop()
