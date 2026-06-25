"""Alembic migration environment for the LAMB KB Server.

Derives the database URL from ``config.DB_PATH`` (so the ``DATA_DIR`` env
override stays authoritative), targets ``database.models.Base.metadata`` for
autogenerate, and enables SQLite batch mode + WAL/foreign-key pragmas so
migrations behave identically to the running application.
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, event, pool

# Make the backend package importable when Alembic runs from the CLI.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from config import DB_PATH  # noqa: E402
from database.models import Base  # noqa: E402

config = context.config

# NB: deliberately not calling logging.config.fileConfig here — migrations run
# in-process at startup (see database.connection._run_migrations) and we must
# not reconfigure the application's logging.

target_metadata = Base.metadata

_DB_URL = f"sqlite:///{DB_PATH}"


def _enable_sqlite_pragmas(dbapi_conn, _record) -> None:  # noqa: ANN001
    """Match the application's per-connection SQLite pragmas."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DBAPI connection)."""
    context.configure(
        url=_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live SQLite connection."""
    engine = create_engine(
        _DB_URL,
        poolclass=pool.NullPool,
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _enable_sqlite_pragmas)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite cannot ALTER most things in place; batch mode rebuilds
            # tables via copy-and-swap so future migrations work.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
