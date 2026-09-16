import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('migration', Path(__file__).parents[1] / 'migrate_06_to_07.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MigrationTests(unittest.TestCase):
    def test_wal_rows_are_verified_without_changing_original_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=sqlite3.connect(root/'lamb_v4.db')
            try:
                db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA wal_autocheckpoint=0')
                db.execute('CREATE TABLE users(id INTEGER)');db.execute('INSERT INTO users VALUES (7)');db.commit()
                before=m.inventory(root)
                self.assertIn('lamb_v4.db-wal', before)
                self.assertEqual(m.sqlite_checks(root)['lamb_v4.db']['table_rows']['users'],1)
                self.assertEqual(before,m.inventory(root))
            finally:db.close()

    def test_missing_required_or_unknown_sources_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for overrides in ({}, {'lamb-data':None}, {'surprise':'/tmp'}):
                with self.assertRaises(ValueError):m.sources(Path(tmp),overrides)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'link').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):m.inventory(root)

    def test_running_project_volume_and_ancestor_bind_are_rejected(self):
        for container in [
            {'Name':'old','Config':{'Labels':{'com.docker.compose.project':'legacy'}}},
            {'Name':'volume','Mounts':[{'Type':'volume','Name':'new_lamb-data'}]},
            {'Name':'bind','Mounts':[{'Type':'bind','Source':'/opt/old'}]},
        ]:
            with patch.object(m,'run',side_effect=['id',json.dumps([container])]):
                with self.assertRaises(ValueError):
                    m.ensure_stopped({'lamb-data':'/opt/old/lamb_v4.db'}, {'legacy','new'}, ['new_lamb-data'])

    def test_unrelated_running_container_is_allowed(self):
        with patch.object(m,'run',side_effect=['id',json.dumps([{'Name':'other','Mounts':[{'Type':'bind','Source':'/opt/elsewhere'}]}])]):
            m.ensure_stopped({'lamb-data':'/opt/old/lamb_v4.db'}, {'old','new'}, ['new_lamb-data'])

if __name__=='__main__':unittest.main()
