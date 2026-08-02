#!/usr/bin/env python3
"""Migration checkpoints — build a database at a known schema version, then
upgrade it and check what the upgrade actually produced.

The realistic failure is not re-running a migration that already ran. It is a
database that has *never* seen the new migrations — a production instance
sitting at an older version — being upgraded. This builds that database from
scratch, keeps it as a reusable checkpoint, and lets the upgrade be run against
a fresh copy as often as you like.

Usage:
    python3 testing/migrations/checkpoint.py build 25     # checkpoint at v25
    python3 testing/migrations/checkpoint.py upgrade 25   # copy it, migrate to LATEST, report
    python3 testing/migrations/checkpoint.py list

Checkpoints live in testing/migrations/checkpoints/ (gitignored — they are
build artifacts, rebuildable from code at any time).
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

CHECKPOINTS = Path(__file__).resolve().parent / "checkpoints"


def _fresh_db(path: Path):
    """Create the base schema the way a new install does, with no migrations."""
    if path.exists():
        path.unlink()
    import lamb.database_manager as dbm

    original = dbm.LambDatabaseManager.__init__

    def bare_init(self):
        self.db_path = str(path)
        self.table_prefix = "LAMB_"
        self.create_database_and_tables()

    dbm.LambDatabaseManager.__init__ = bare_init
    try:
        dbm.LambDatabaseManager()
    finally:
        dbm.LambDatabaseManager.__init__ = original


class _DB:
    """Minimal stand-in so MigrationRunner talks to the file we choose."""

    table_prefix = "LAMB_"

    def __init__(self, path: Path):
        self._path = str(path)

    def get_connection(self):
        return sqlite3.connect(self._path)


def _migrate(path: Path, stop_at: int | None = None) -> int:
    from lamb import migrations as m

    original = m.LATEST_VERSION
    if stop_at is not None:
        m.LATEST_VERSION = stop_at
    try:
        m.MigrationRunner(_DB(path)).apply_all()
    finally:
        m.LATEST_VERSION = original
    return _version(path)


def _version(path: Path) -> int:
    con = sqlite3.connect(path)
    try:
        row = con.execute("SELECT COALESCE(MAX(version), 0) FROM LAMB_schema_version").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        con.close()


def _schema(path: Path) -> dict[str, list[str]]:
    con = sqlite3.connect(path)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t: [c[1] for c in con.execute(f"PRAGMA table_info({t})")] for t in tables}
    finally:
        con.close()


def build(version: int) -> Path:
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    target = CHECKPOINTS / f"v{version}.db"
    _fresh_db(target)
    reached = _migrate(target, stop_at=version)
    if reached != version:
        raise SystemExit(f"checkpoint build reached v{reached}, expected v{version}")
    print(f"built checkpoint v{version}: {target} ({len(_schema(target))} tables)")
    return target


def upgrade(version: int) -> None:
    src = CHECKPOINTS / f"v{version}.db"
    if not src.exists():
        raise SystemExit(f"no checkpoint at v{version} — run: checkpoint.py build {version}")
    work = CHECKPOINTS / f"v{version}-upgraded.db"
    shutil.copy2(src, work)

    before_schema, before_version = _schema(work), _version(work)
    after_version = _migrate(work)
    after_schema = _schema(work)

    new_tables = sorted(set(after_schema) - set(before_schema))
    new_columns = {
        t: sorted(set(after_schema[t]) - set(before_schema[t]))
        for t in before_schema
        if set(after_schema.get(t, [])) - set(before_schema[t])
    }

    print(f"upgrade: v{before_version} -> v{after_version}")
    print(f"  new tables ({len(new_tables)}): {', '.join(new_tables) or 'none'}")
    for t, cols in new_columns.items():
        print(f"  new columns on {t}: {', '.join(cols)}")

    from lamb import migrations as m
    if after_version != m.LATEST_VERSION:
        raise SystemExit(f"FAIL: ended at v{after_version}, LATEST_VERSION is {m.LATEST_VERSION}")

    applied = sorted(r[0] for r in sqlite3.connect(work).execute(
        "SELECT version FROM LAMB_schema_version"))
    gaps = [v for v in range(1, after_version + 1) if v not in applied]
    if gaps:
        print(f"  WARNING: versions never applied on this database: {gaps}")
    print("upgrade OK")


def list_checkpoints() -> None:
    if not CHECKPOINTS.exists():
        print("no checkpoints yet")
        return
    for f in sorted(CHECKPOINTS.glob("*.db")):
        print(f"  {f.name}: v{_version(f)}, {len(_schema(f))} tables")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "build":
        build(int(sys.argv[2]))
    elif cmd == "upgrade":
        upgrade(int(sys.argv[2]))
    elif cmd == "list":
        list_checkpoints()
    else:
        raise SystemExit(__doc__)
