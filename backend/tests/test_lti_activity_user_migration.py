"""Regression coverage for #468 using real SQLite and activity-user methods.

Run from backend: python -m unittest tests.test_lti_activity_user_migration -v
No provider, browser, or application startup is required.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lamb.database_manager import LambDatabaseManager
from lamb.migrations import MigrationRunner


class ActivityUserMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = LambDatabaseManager.__new__(LambDatabaseManager)
        self.db.db_path = str(Path(self.tmp.name) / 'test.db')
        self.db.table_prefix = 'QA_'
        self.runner = MigrationRunner(self.db)

    def connection(self):
        conn = self.db.get_connection()
        self.addCleanup(conn.close)
        return conn

    def baseline(self, existing=False):
        conn = self.connection()
        with conn:
            conn.execute('CREATE TABLE QA_lti_activities (id INTEGER PRIMARY KEY)')
            conn.execute('INSERT INTO QA_lti_activities VALUES (1)')
            self.runner._migration_15(conn.cursor())
            self.runner._ensure_schema_version_table(conn.cursor())
            for version in range(1, 31):
                self.runner._record_version(conn.cursor(), version)
            if existing:
                conn.execute("""INSERT INTO QA_lti_activity_users
                    (activity_id, user_email, user_name, access_count, created_at)
                    VALUES (1, 'student@example.edu', 'Student', 7, 123)""")
        return conn

    def test_upgrade_preserves_existing_rows_and_defaults_to_student(self):
        conn = self.baseline(existing=True)
        self.runner.apply_all()
        self.assertEqual(conn.execute('SELECT user_email, access_count, created_at, is_instructor FROM QA_lti_activity_users').fetchone(),
                         ('student@example.edu', 7, 123, 0))
        self.assertIsNotNone(conn.execute('SELECT version FROM QA_schema_version WHERE version=31').fetchone())

    def test_fresh_activity_table_allows_student_and_instructor_registration(self):
        conn = self.baseline()
        self.runner.apply_all()
        for instructor in (False, True):
            user_id = self.db.create_lti_activity_user(1, f'{instructor}@example.edu', is_instructor=instructor)
            self.assertIsNotNone(user_id)
            self.assertEqual(conn.execute('SELECT is_instructor, access_count FROM QA_lti_activity_users WHERE id=?', (user_id,)).fetchone(),
                             (int(instructor), 1))

    def test_repeated_access_promotes_but_never_demotes(self):
        conn = self.baseline()
        self.runner.apply_all()
        ids = [self.db.create_lti_activity_user(1, 'student@example.edu', is_instructor=flag, owi_user_id='owi-1')
               for flag in (False, False, True, False)]
        self.assertIsNotNone(ids[0])
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(conn.execute('SELECT access_count, is_instructor, owi_user_id FROM QA_lti_activity_users').fetchone(), (4, 1, 'owi-1'))

    def test_existing_column_and_instructor_flag_survive(self):
        conn = self.baseline(existing=True)
        with conn:
            conn.execute('ALTER TABLE QA_lti_activity_users ADD COLUMN is_instructor INTEGER NOT NULL DEFAULT 0')
            conn.execute('UPDATE QA_lti_activity_users SET is_instructor=1')
        self.runner.apply_all()
        self.runner.apply_all()
        with conn:
            self.runner._migration_31(conn.cursor())
        self.assertEqual(conn.execute('SELECT is_instructor, access_count FROM QA_lti_activity_users').fetchone(), (1, 7))

    def test_unprefixed_database(self):
        self.db.table_prefix = ''
        conn = self.connection()
        with conn:
            self.runner._migration_15(conn.cursor())
            self.runner._migration_31(conn.cursor())
        self.assertIn('is_instructor', [r[1] for r in conn.execute('PRAGMA table_info(lti_activity_users)')])


if __name__ == '__main__':
    unittest.main()
