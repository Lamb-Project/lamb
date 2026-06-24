"""Alembic migration round-trip.

Runs the real migration chain (``upgrade head`` then ``downgrade base``)
against an isolated temp database via the Alembic CLI, so a broken or
non-reversible revision fails the suite. Uses a subprocess (the Alembic CLI)
against its own throwaway ``DATA_DIR`` — it does not touch the session DB.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "backend"


def _alembic(args: list[str], data_dir: str) -> subprocess.CompletedProcess:
    """Invoke the Alembic CLI in the backend dir against ``data_dir``."""
    env = {**os.environ, "DATA_DIR": data_dir, "LAMB_API_TOKEN": "test"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=_BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )


def _tables(db_path: Path) -> set[str]:
    """Return the set of table names in the SQLite DB at ``db_path``."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


@pytest.mark.slow
def test_upgrade_then_downgrade_roundtrip(tmp_path):
    """`alembic upgrade head` creates every table; `downgrade base` removes them."""
    data_dir = str(tmp_path)
    db_path = tmp_path / "library-manager.db"

    up = _alembic(["upgrade", "head"], data_dir)
    assert up.returncode == 0, up.stderr

    tables = _tables(db_path)
    assert {
        "organizations",
        "libraries",
        "content_folders",
        "content_items",
        "content_images",
        "import_jobs",
        "alembic_version",
    } <= tables

    down = _alembic(["downgrade", "base"], data_dir)
    assert down.returncode == 0, down.stderr

    tables = _tables(db_path)
    assert "content_items" not in tables
    assert "organizations" not in tables
