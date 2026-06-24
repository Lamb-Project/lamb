"""Alembic migration round-trip test.

Runs the real migration chain (``upgrade head`` then ``downgrade base``)
against an isolated temp database via the Alembic CLI, so a broken or
non-reversible revision fails the suite.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "backend"


def _alembic(args: list[str], data_dir: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATA_DIR": data_dir, "LAMB_API_TOKEN": "test"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=_BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )


def _tables(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def test_upgrade_then_downgrade_roundtrip(tmp_path):
    data_dir = str(tmp_path)
    db_path = tmp_path / "kb-server.db"

    up = _alembic(["upgrade", "head"], data_dir)
    assert up.returncode == 0, up.stderr

    tables = _tables(db_path)
    assert {"collections", "ingestion_jobs", "alembic_version"} <= tables

    down = _alembic(["downgrade", "base"], data_dir)
    assert down.returncode == 0, down.stderr

    tables = _tables(db_path)
    assert "collections" not in tables
    assert "ingestion_jobs" not in tables
