"""Database connection management.

Provides a single engine and session factory for the KB Server's SQLite
metadata database. The schema is brought to ``head`` with Alembic on the
first call to ``init_db`` (see ``_run_migrations``).
"""

import logging
from collections.abc import Generator
from pathlib import Path

from config import DB_PATH
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _enable_sqlite_wal(dbapi_conn, _connection_record) -> None:  # noqa: ANN001
    """Enable WAL mode and foreign keys for every new SQLite connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_lock_file = None


def _run_migrations() -> None:
    """Bring the database schema to ``head`` using Alembic.

    Databases created by the historical ``create_all`` path already have the
    tables but no ``alembic_version`` row. Those are stamped to the baseline
    revision first so the baseline migration is not re-applied on top of the
    existing schema; any later revisions then run normally.
    """
    from alembic import command  # noqa: PLC0415
    from alembic.config import Config  # noqa: PLC0415
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    backend_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))

    inspector = inspect(_engine)
    has_schema = inspector.has_table("collections")
    has_version = inspector.has_table("alembic_version")
    if has_schema and not has_version:
        base_rev = ScriptDirectory.from_config(cfg).get_base()
        command.stamp(cfg, base_rev)
        logger.info("Stamped pre-Alembic database to baseline revision %s", base_rev)

    command.upgrade(cfg, "head")
    logger.info("Database schema migrated to head")


def init_db() -> None:
    """Create the engine, enable SQLite optimizations, and migrate the schema.

    Acquires an exclusive file lock on the data directory to prevent two
    instances from running against the same storage simultaneously, then runs
    Alembic migrations up to ``head``.

    Safe to call multiple times.

    Raises:
        RuntimeError: If another instance holds the lock.
    """
    global _engine, _SessionLocal, _lock_file
    if _SessionLocal is not None:
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    import fcntl  # noqa: PLC0415

    lock_path = DB_PATH.parent / ".lock"
    _lock_file = open(lock_path, "w")  # noqa: SIM115
    import atexit  # noqa: PLC0415
    atexit.register(_lock_file.close)
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        raise RuntimeError(
            f"Another KB Server instance is using {DB_PATH.parent}. "
            "Only one instance may run per data directory."
        ) from exc

    _engine = create_engine(
        f"sqlite:///{DB_PATH}",
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )

    event.listen(_engine, "connect", _enable_sqlite_wal)

    # Bring the schema to head with Alembic, then apply the KG-RAG columns
    # via the idempotent lightweight path. Those columns are declared on the
    # model but are not yet part of the Alembic baseline, so we add them here
    # for fresh DBs; the migration skips any column that already exists, so it
    # is also safe on installations created by the historical create_all path.
    _run_migrations()
    _run_lightweight_migrations(_engine)

    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)

    logger.info("Database initialized at %s", DB_PATH)


def _run_lightweight_migrations(engine: Engine) -> None:
    """Apply forward-compatible ALTER TABLEs that ``create_all`` cannot do.

    ``Base.metadata.create_all`` only creates missing *tables*; it never
    adds missing *columns* to existing tables. When this repo evolves the
    schema with a new column on an already-populated DB, we apply the
    change here so existing deployments don't crash on the next query.

    Add new entries below as additive, idempotent ``ALTER TABLE ADD
    COLUMN`` statements; never delete data or change types here — those
    need a real migration tool.
    """
    additions = [
        # (table, column, ddl-snippet)
        (
            "collections",
            "graph_enabled",
            "INTEGER NOT NULL DEFAULT 0",
        ),
        (
            "collections",
            "extraction_vendor",
            "TEXT",
        ),
        (
            "collections",
            "extraction_model",
            "TEXT",
        ),
        (
            "collections",
            "extraction_endpoint",
            "TEXT",
        ),
    ]
    # Use a direct sqlite3 connection rather than the SQLAlchemy engine.
    # The engine's pool keeps the underlying connection around between
    # calls (with WAL state intact), and that lingering state has been
    # observed to interfere with fork-based tests that re-acquire the
    # data-directory lock. A short-lived ``sqlite3.connect`` opened and
    # closed entirely inside this function sidesteps that.
    import sqlite3  # noqa: PLC0415

    db_url = str(engine.url)
    if not db_url.startswith("sqlite:///"):
        return  # Only SQLite needs this hand-rolled path right now.
    db_file = db_url[len("sqlite:///") :]
    conn = sqlite3.connect(db_file)
    try:
        for table, column, ddl in additions:
            cur = conn.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cur.fetchall()}
            if column in existing:
                continue
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            conn.commit()
            logger.info(
                "Schema migration applied: ALTER TABLE %s ADD COLUMN %s %s",
                table,
                column,
                ddl,
            )
    finally:
        conn.close()


def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session and ensure it is closed afterward.

    Intended for use as a FastAPI ``Depends`` dependency.

    Yields:
        A SQLAlchemy ``Session`` bound to the KB Server database.

    Raises:
        RuntimeError: If ``init_db`` has not been called yet.
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_session_direct() -> Session:
    """Return a plain ``Session`` for use outside FastAPI dependency injection.

    The caller is responsible for closing the session.

    Returns:
        A new SQLAlchemy ``Session``.

    Raises:
        RuntimeError: If ``init_db`` has not been called yet.
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()
