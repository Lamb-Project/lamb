"""Migrations track the applied set and each migration's name (#465)."""
import ast
import sqlite3
import time
from pathlib import Path

import pytest

from lamb import migrations
from lamb.migrations import COLLIDED_VERSIONS, LATEST_VERSION, RESERVED_ON_OTHER_LINES, MigrationRunner

SOURCE = Path(migrations.__file__).read_text()


def defined_numbers():
    tree = ast.parse(SOURCE)
    runner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MigrationRunner')
    return [int(f.name[11:]) for f in runner.body
            if isinstance(f, ast.FunctionDef) and f.name.startswith('_migration_') and f.name[11:].isdigit()]


def test_numbering_guard():
    numbers = defined_numbers()
    # A second def with the same number would silently replace the first.
    assert len(numbers) == len(set(numbers)), 'two migrations share a number'
    assert LATEST_VERSION == max(numbers), 'LATEST_VERSION must be the highest defined migration'
    assert not set(numbers) & set(RESERVED_ON_OTHER_LINES), 'number already used on another line; take the next free one'
    assert all(MigrationRunner(None)._migration_identity(v) != f'migration {v}' for v in numbers), 'every migration needs a docstring'


class Db:
    table_prefix = 'T_'

    def __init__(self, path):
        self.path = path

    def get_connection(self):
        return sqlite3.connect(self.path)


def old_database(path, versions, named=False):
    """A database migrated by the old high-water-mark runner: no name column."""
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE T_schema_version (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)')
        c.executemany('INSERT INTO T_schema_version VALUES (?, ?)', [(v, int(time.time())) for v in versions])
    return Db(path)


def rows(db):
    with sqlite3.connect(db.path) as c:
        return {v: n for v, n in c.execute('SELECT version, name FROM T_schema_version')}


def tables(db):
    with sqlite3.connect(db.path) as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_old_database_gets_names_column_and_runs_the_missing_migration(tmp_path):
    db = old_database(tmp_path / 'a.db', range(1, 26))
    MigrationRunner(db).apply_all()
    recorded = rows(db)
    assert 'T_api_keys' in tables(db) and 26 in recorded
    assert recorded[26].startswith('Create api_keys table') and recorded[25] is None


def test_a_late_migration_below_the_high_water_mark_still_runs(tmp_path):
    # 27-31 applied by the alpha line; the old runner would never run 26 here.
    db = old_database(tmp_path / 'b.db', [*range(1, 26), 27, 28, 29, 30, 31])
    MigrationRunner(db).apply_all()
    assert 'T_api_keys' in tables(db) and 26 in rows(db)


def test_unnamed_collided_26_without_our_table_is_repaired(tmp_path):
    # The #465 case: 26 was recorded by the other branch's migration; api_keys never created.
    db = old_database(tmp_path / 'c.db', range(1, 27))
    assert 'T_api_keys' not in tables(db)
    MigrationRunner(db).apply_all()
    assert 'T_api_keys' in tables(db) and rows(db)[26].startswith('Create api_keys table')
    assert COLLIDED_VERSIONS == {26: 'api_keys'}


def test_a_number_recorded_for_different_work_refuses_to_start(tmp_path):
    db = old_database(tmp_path / 'd.db', range(1, 26))
    MigrationRunner(db).apply_all()
    with sqlite3.connect(db.path) as c:
        c.execute("UPDATE T_schema_version SET name = 'Create knowledge_stores and kb_content_links tables.' WHERE version = 26")
    with pytest.raises(RuntimeError, match='Migration identity conflict'):
        MigrationRunner(db).apply_all()
