"""Unit tests for database connection management and ORM models.

Tests cover WAL mode, foreign keys, idempotent init, file locking,
session lifecycle, model defaults, constraints, and timestamp behavior.
"""

from __future__ import annotations

import contextlib
import fcntl
import multiprocessing
import os
import tempfile
import time
import uuid
from datetime import UTC

import pytest
from database.models import Collection, IngestionJob
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_collection(**kwargs) -> Collection:
    col_id = str(uuid.uuid4())
    defaults = dict(
        id=col_id,
        organization_id=f"org-{uuid.uuid4()}",
        name=f"test-kb-{col_id}",
        chunking_strategy="simple",
        embedding_vendor="fake",
        embedding_model="fake-model",
        vector_db_backend="chromadb",
        storage_path=f"org-1/{col_id}",
    )
    defaults.update(kwargs)
    return Collection(**defaults)


def _make_job(**kwargs) -> IngestionJob:
    defaults = dict(
        id=str(uuid.uuid4()),
        collection_id=str(uuid.uuid4()),
        organization_id="org-1",
        documents_json="[]",
    )
    defaults.update(kwargs)
    return IngestionJob(**defaults)


# ---------------------------------------------------------------------------
# _utcnow() helper — timezone-aware
# ---------------------------------------------------------------------------

def test_utcnow_is_timezone_aware() -> None:
    from database.models import _utcnow
    ts = _utcnow()
    assert ts.tzinfo is not None
    assert ts.tzinfo == UTC


# ---------------------------------------------------------------------------
# WAL mode and foreign keys
# ---------------------------------------------------------------------------

def test_wal_mode_enabled(db_session) -> None:
    result = db_session.execute(text("PRAGMA journal_mode")).scalar()
    assert result == "wal"


def test_foreign_keys_enabled(db_session) -> None:
    result = db_session.execute(text("PRAGMA foreign_keys")).scalar()
    assert result == 1


# ---------------------------------------------------------------------------
# init_db() idempotency
# ---------------------------------------------------------------------------

def test_init_db_idempotent() -> None:
    from database.connection import init_db
    init_db()
    init_db()


# ---------------------------------------------------------------------------
# File lock test via subprocess
# ---------------------------------------------------------------------------

def _child_hold_lock(data_dir: str, ready_event, release_event) -> None:
    """Child process: open and hold the exclusive lock, signal parent, then wait."""
    lock_path = os.path.join(data_dir, ".lock")
    os.makedirs(data_dir, exist_ok=True)
    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ready_event.set()
        release_event.wait(timeout=10)


def _child_init_db(data_dir: str, result_queue) -> None:
    """Child process: try to call init_db() on a locked directory, report result."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
    os.environ["DATA_DIR"] = data_dir
    # Re-import config with the new DATA_DIR so DB_PATH reflects the temp dir.
    import importlib

    import config
    importlib.reload(config)
    import database.connection as conn
    importlib.reload(conn)
    try:
        conn.init_db()
        result_queue.put(None)
    except RuntimeError as exc:
        result_queue.put(str(exc))
    except Exception as exc:
        result_queue.put(f"unexpected: {exc}")


def test_file_lock_raises_runtime_error_direct(monkeypatch, tmp_path) -> None:
    """Test the lock-contention path in the main process for coverage."""
    import fcntl

    import database.connection as conn

    lock_dir = tmp_path / "locked-data"
    lock_dir.mkdir()
    lock_path = lock_dir / ".lock"
    lf = open(lock_path, "w")  # noqa: SIM115
    fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)

    saved_session_local = conn._SessionLocal
    saved_engine = conn._engine
    saved_lock_file = conn._lock_file

    conn._SessionLocal = None
    conn._engine = None
    conn._lock_file = None
    conn.DB_PATH = lock_dir / "kb-server.db"

    try:
        with pytest.raises(RuntimeError, match="Another KB Server instance"):
            conn.init_db()
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)
        lf.close()
        conn._SessionLocal = saved_session_local
        conn._engine = saved_engine
        conn._lock_file = saved_lock_file


def test_file_lock_raises_runtime_error() -> None:
    data_dir = tempfile.mkdtemp(prefix="kb-lock-test-")
    ctx = multiprocessing.get_context("fork")
    ready_event = ctx.Event()
    release_event = ctx.Event()
    result_queue = ctx.Queue()

    holder = ctx.Process(
        target=_child_hold_lock,
        args=(data_dir, ready_event, release_event),
        daemon=True,
    )
    holder.start()
    ready_event.wait(timeout=5)

    challenger = ctx.Process(
        target=_child_init_db,
        args=(data_dir, result_queue),
        daemon=True,
    )
    challenger.start()
    challenger.join(timeout=10)

    release_event.set()
    holder.join(timeout=5)

    assert not result_queue.empty(), "Child did not report a result"
    result = result_queue.get_nowait()
    assert result is not None, "Expected RuntimeError but init_db() succeeded"
    assert "instance" in result or "lock" in result.lower() or "Another" in result


# ---------------------------------------------------------------------------
# Session functions
# ---------------------------------------------------------------------------

def test_get_session_direct_returns_session() -> None:
    from database.connection import get_session_direct
    session = get_session_direct()
    try:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        session.close()


def test_get_session_yields_session() -> None:
    from database.connection import get_session
    gen = get_session()
    session = next(gen)
    try:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        with contextlib.suppress(StopIteration):
            next(gen)


def test_get_session_closes_on_exception() -> None:
    from database.connection import get_session
    close_calls = []
    gen = get_session()
    session = next(gen)
    original_close = session.close
    session.close = lambda: close_calls.append(True) or original_close()
    with contextlib.suppress(ValueError, StopIteration):
        gen.throw(ValueError("boom"))
    assert close_calls, "session.close() was not called after exception"


def test_get_session_not_initialized_raises() -> None:
    from database import connection as conn
    original = conn._SessionLocal
    conn._SessionLocal = None
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            next(conn.get_session())
    finally:
        conn._SessionLocal = original


def test_get_session_direct_not_initialized_raises() -> None:
    from database import connection as conn
    original = conn._SessionLocal
    conn._SessionLocal = None
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            conn.get_session_direct()
    finally:
        conn._SessionLocal = original


# ---------------------------------------------------------------------------
# Collection model — defaults
# ---------------------------------------------------------------------------

def test_collection_defaults(db_session) -> None:
    col = _make_collection()
    db_session.add(col)
    db_session.commit()
    db_session.refresh(col)

    assert col.status == "ready"
    assert col.document_count == 0
    assert col.chunk_count == 0


def test_collection_created_at_set_on_insert(db_session) -> None:
    col = _make_collection()
    db_session.add(col)
    db_session.commit()
    db_session.refresh(col)

    assert col.created_at is not None


def test_collection_updated_at_set_on_insert(db_session) -> None:
    col = _make_collection()
    db_session.add(col)
    db_session.commit()
    db_session.refresh(col)

    assert col.updated_at is not None


# ---------------------------------------------------------------------------
# Collection — unique constraint (org_id, name)
# ---------------------------------------------------------------------------

def test_collection_unique_org_name_constraint(db_session) -> None:
    org_id = f"org-{uuid.uuid4()}"
    col1 = _make_collection(organization_id=org_id, name="kb-dup")
    col2 = _make_collection(organization_id=org_id, name="kb-dup")
    db_session.add(col1)
    db_session.commit()
    db_session.add(col2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_collection_same_name_different_org_is_allowed(db_session) -> None:
    col1 = _make_collection(organization_id=f"org-{uuid.uuid4()}", name="shared-name")
    col2 = _make_collection(organization_id=f"org-{uuid.uuid4()}", name="shared-name")
    db_session.add_all([col1, col2])
    db_session.commit()


# ---------------------------------------------------------------------------
# Collection — updated_at mutates on update
# ---------------------------------------------------------------------------

def test_collection_updated_at_changes_on_update(db_session) -> None:
    col = _make_collection()
    db_session.add(col)
    db_session.commit()
    db_session.refresh(col)

    original_updated = col.updated_at

    # Small pause so the new timestamp differs.
    time.sleep(0.05)

    col.document_count = 5
    db_session.commit()
    db_session.refresh(col)

    assert col.updated_at > original_updated


# ---------------------------------------------------------------------------
# IngestionJob model — defaults
# ---------------------------------------------------------------------------

def test_ingestion_job_defaults(db_session) -> None:
    job = _make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.status == "pending"
    assert job.attempts == 0
    assert job.documents_processed == 0
    assert job.chunks_created == 0


def test_ingestion_job_created_at_set_on_insert(db_session) -> None:
    job = _make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.created_at is not None


def test_ingestion_job_updated_at_set_on_insert(db_session) -> None:
    job = _make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.updated_at is not None


# ---------------------------------------------------------------------------
# IngestionJob — updated_at mutates on update
# ---------------------------------------------------------------------------

def test_ingestion_job_updated_at_changes_on_update(db_session) -> None:
    job = _make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    original_updated = job.updated_at

    time.sleep(0.05)

    job.status = "processing"
    db_session.commit()
    db_session.refresh(job)

    assert job.updated_at > original_updated
