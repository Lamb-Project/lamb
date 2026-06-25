"""Unit tests for ``backend/database/connection.py``.

The session database is already initialised by the root conftest (which also
holds the single-instance file lock). These tests therefore never call
``init_db`` again; they exercise the session factories, the WAL/foreign-key
pragmas, and the not-initialised RuntimeError branches by temporarily
nulling the module-level session factory under try/finally.
"""

from __future__ import annotations

import sqlite3

import pytest
from database import connection
from sqlalchemy import text
from sqlalchemy.orm import Session


class TestSessionFactories:
    """``get_session`` / ``get_session_direct`` yield usable sessions."""

    def test_get_session_direct_returns_session(self):
        """``get_session_direct`` returns a live Session the caller closes."""
        session = connection.get_session_direct()
        try:
            assert isinstance(session, Session)
            assert session.execute(text("SELECT 1")).scalar() == 1
        finally:
            session.close()

    def test_get_session_generator_yields_and_closes(self):
        """``get_session`` yields a working Session and closes it on exit."""
        gen = connection.get_session()
        session = next(gen)
        assert isinstance(session, Session)
        assert session.execute(text("SELECT 1")).scalar() == 1
        # Exhausting the generator runs the finally: close().
        with pytest.raises(StopIteration):
            next(gen)


class TestNotInitialisedBranches:
    """Both accessors raise RuntimeError when the factory is unset."""

    def test_get_session_direct_raises_when_uninitialised(self):
        """``get_session_direct`` raises RuntimeError if init_db not called."""
        saved = connection._SessionLocal
        connection._SessionLocal = None
        try:
            with pytest.raises(RuntimeError, match="Database not initialized"):
                connection.get_session_direct()
        finally:
            connection._SessionLocal = saved

    def test_get_session_raises_when_uninitialised(self):
        """``get_session`` raises RuntimeError if init_db not called."""
        saved = connection._SessionLocal
        connection._SessionLocal = None
        try:
            gen = connection.get_session()
            with pytest.raises(RuntimeError, match="Database not initialized"):
                next(gen)
        finally:
            connection._SessionLocal = saved


class TestPragmas:
    """WAL journal mode and foreign-key enforcement are active."""

    def test_pragmas_on_live_engine_connection(self):
        """A connection from the real engine reports WAL + foreign_keys=ON."""
        with connection._engine.connect() as conn:
            journal = conn.execute(text("PRAGMA journal_mode")).scalar()
            fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert journal.lower() == "wal", "journal_mode should be WAL"
        assert fk == 1, "foreign_keys enforcement should be ON"

    def test_enable_sqlite_wal_applies_pragmas(self):
        """``_enable_sqlite_wal`` sets WAL + foreign_keys on a raw connection."""
        # Use a real on-disk DB: WAL is not available on :memory: connections.
        import tempfile  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        tmp = Path(tempfile.mkdtemp(prefix="lm-wal-")) / "wal.db"
        raw = sqlite3.connect(str(tmp))
        try:
            connection._enable_sqlite_wal(raw, None)
            cur = raw.cursor()
            journal = cur.execute("PRAGMA journal_mode").fetchone()[0]
            fk = cur.execute("PRAGMA foreign_keys").fetchone()[0]
            cur.close()
            assert journal.lower() == "wal"
            assert fk == 1
        finally:
            raw.close()
