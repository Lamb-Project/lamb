"""Schema initialization does not leak connections or repeat on every lookup."""
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from lamb.migrations import MigrationRunner, LATEST_VERSION
from lamb.database_manager import LambDatabaseManager

class Lifecycle(unittest.TestCase):
    def test_migration_closes_connection_on_noop_and_error(self):
        for broken in (False, True):
            conn=sqlite3.connect(':memory:')
            conn.execute('CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at INTEGER)')
            conn.execute('INSERT INTO schema_version VALUES (?,0)', (LATEST_VERSION,))
            runner=MigrationRunner(SimpleNamespace(table_prefix='',get_connection=lambda:conn))
            if broken:
                with patch.object(runner, '_get_current_version', side_effect=RuntimeError('test')):
                    with self.assertRaises(RuntimeError):runner.apply_all()
            else:
                runner.apply_all()
            with self.assertRaises(sqlite3.ProgrammingError):conn.execute('SELECT 1')

    def test_repeated_managers_do_not_repeat_schema_setup(self):
        with tempfile.TemporaryDirectory() as directory, patch('config.LAMB_DB_PATH',directory), patch.object(LambDatabaseManager,'_system_org_initialized',True), patch.object(LambDatabaseManager,'_ready_databases',set()), patch.object(LambDatabaseManager,'_configure_database_optimizations') as optimize, patch('lamb.migrations.MigrationRunner.apply_all') as migrate:
            from pathlib import Path
            (Path(directory)/'lamb_v4.db').touch()
            for _ in range(10):LambDatabaseManager()
            migrate.assert_called_once();optimize.assert_called_once()
