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

    _run_migrations()

    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)

    logger.info("Database initialized at %s", DB_PATH)


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
