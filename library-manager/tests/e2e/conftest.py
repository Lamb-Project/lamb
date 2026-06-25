"""E2E-tier fixtures: real HTTP to a uvicorn subprocess (+ optional Docker).

The shared ``server`` fixture covers the read-mostly e2e tests (smoke, auth
boundary, multitenancy, error matrix, real imports). Tests that need to
control the process lifecycle directly (crash recovery, single-instance lock,
graceful shutdown) construct :class:`ServerProcess` themselves.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from ._server import ServerProcess


@pytest.fixture(scope="session")
def server() -> Iterator[ServerProcess]:
    """A single uvicorn subprocess shared across read-mostly e2e tests."""
    proc = ServerProcess()
    proc.start()
    try:
        yield proc
    finally:
        proc.stop()


@pytest.fixture
def http(server: ServerProcess) -> Iterator[httpx.Client]:
    """A real HTTP client bound to the shared server, with auth headers."""
    with server.client() as client:
        yield client
