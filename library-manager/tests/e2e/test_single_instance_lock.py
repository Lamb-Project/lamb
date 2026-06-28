"""E2E single-instance lock: two processes can't share a data directory.

The first process acquires an exclusive ``fcntl`` flock on the data dir's
``.lock`` file at startup. A second process pointed at the same dir must fail
to start (its ``init_db`` raises RuntimeError → lifespan startup fails → the
process exits) while the first stays healthy.
"""

from __future__ import annotations

import time

import pytest

from ._server import ServerProcess

pytestmark = pytest.mark.slow


def test_second_instance_cannot_acquire_lock() -> None:
    """A second process on the same data dir fails to become healthy."""
    a = ServerProcess()
    a.start()
    b = None
    try:
        # B shares A's data dir → the flock is already held.
        b = ServerProcess(data_dir=a.data_dir, port=None)
        b.start(wait=False)

        # B must exit (non-zero) within a few seconds, or never go healthy.
        deadline = time.monotonic() + 8.0
        b_exited = False
        while time.monotonic() < deadline:
            if b.proc is not None and b.proc.poll() is not None:
                b_exited = True
                break
            time.sleep(0.2)

        assert b_exited, f"B should have exited but is still running:\n{b.read_log()}"
        assert b.proc.returncode not in (0, None), b.read_log()

        # A is unaffected and still serving.
        a.wait_healthy(timeout=5)

        # The failure must mention the single-instance lock.
        log = b.read_log()
        assert "Another Library Manager instance is using" in log, log
    finally:
        if b is not None:
            b.stop()
        a.stop()
