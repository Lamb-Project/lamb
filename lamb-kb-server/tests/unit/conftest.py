"""Unit-tier fixtures: per-test tmpdir, no FastAPI app, no worker."""

from __future__ import annotations

import importlib
import shutil
import tempfile
from collections.abc import Iterator

import pytest

from tests._fakes import FakeEmbedding


@pytest.fixture()
def reload_config() -> Iterator[None]:
    """Reload the ``config`` module after env-var mutations.

    Lives at the tier root so any unit test that needs env-driven config
    re-evaluation can use it without re-defining the fixture locally.
    Mirror of the same-named fixture in tests/unit/test_config.py — keep
    them in sync.
    """
    import config  # noqa: PLC0415

    yield
    importlib.reload(config)


@pytest.fixture
def tmp_storage() -> Iterator[str]:
    """Per-test temp dir for vector DB persistence."""
    path = tempfile.mkdtemp(prefix="kbs-unit-")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def fake_embedding() -> FakeEmbedding:
    return FakeEmbedding()


@pytest.fixture
def db_session() -> Iterator:
    """Direct SQLAlchemy session against the test DB (no HTTP)."""
    from database.connection import get_session_direct  # noqa: PLC0415

    session = get_session_direct()
    try:
        yield session
    finally:
        session.close()
