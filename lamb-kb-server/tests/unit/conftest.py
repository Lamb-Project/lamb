"""Unit-tier fixtures: per-test tmpdir, no FastAPI app, no worker."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator

import pytest

from tests._fakes import FakeEmbedding


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
