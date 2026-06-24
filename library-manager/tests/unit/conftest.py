"""Unit-tier fixtures: direct module calls, no FastAPI app, no HTTP.

Unit tests exercise one module's logic in isolation. They get:

* ``tmp_storage`` — a throwaway directory for filesystem-touching services.
* ``db_session`` — a real SQLAlchemy session (the session DB is initialised
  once by the root conftest); the caller never has to manage HTTP.
* ``fresh_plugin_registry`` / ``fresh_capability_registry`` — snapshot the
  class-level registry dicts and restore them after the test, so tests that
  register/disable plugins cannot leak state into their neighbours.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def tmp_storage() -> Iterator[Path]:
    """A per-test temporary directory, removed on teardown."""
    path = Path(tempfile.mkdtemp(prefix="lm-unit-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def db_session() -> Iterator:
    """A direct SQLAlchemy session bound to the session test database."""
    from database.connection import get_session_direct  # noqa: PLC0415

    session = get_session_direct()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fresh_plugin_registry() -> Iterator:
    """Snapshot and restore ``PluginRegistry._plugins`` around a test."""
    from plugins.base import PluginRegistry  # noqa: PLC0415

    saved = dict(PluginRegistry._plugins)
    try:
        yield PluginRegistry
    finally:
        PluginRegistry._plugins = saved


@pytest.fixture
def fresh_capability_registry() -> Iterator:
    """Snapshot and restore ``CapabilityRegistry._handlers`` around a test."""
    from plugins.content_handlers.capability import CapabilityRegistry  # noqa: PLC0415

    saved = dict(CapabilityRegistry._handlers)
    try:
        yield CapabilityRegistry
    finally:
        CapabilityRegistry._handlers = saved
