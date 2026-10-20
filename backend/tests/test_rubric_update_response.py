"""Rubric update responses must describe committed data, using real SQLite reads."""
import json,sqlite3,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from lamb.evaluaitor.rubric_database import RubricDatabaseManager

class RubricUpdateResponse(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)/'rubrics.db'
        self.manager=RubricDatabaseManager.__new__(RubricDatabaseManager)
        self.manager.db_manager=SimpleNamespace(table_prefix='test_',get_connection=lambda:sqlite3.connect(path))
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE test_organizations (id INTEGER, slug TEXT)')
            db.execute("INSERT INTO test_organizations VALUES (1,'test-org')")
            db.execute('CREATE TABLE test_rubrics (id INTEGER, rubric_id TEXT, organization_id INTEGER, owner_email TEXT, title TEXT, description TEXT, rubric_data TEXT, updated_at INTEGER, is_public INTEGER)')
            db.execute('INSERT INTO test_rubrics VALUES (1,?,1,?,?,?,?,0,0)',('rubric','owner@test','Before','Before',json.dumps({'title':'Before','criteria':[{'id':'criterion','weight':50}]})))

    def test_response_matches_independent_committed_read(self):
        data={'title':'After','description':'Updated','criteria':[{'id':'criterion','weight':60}]}
        response=self.manager.update_rubric('rubric',data,'owner@test')
        self.assertEqual(response['title'],'After')
        self.assertEqual(response['rubric_data'],data)
        self.assertEqual(response,self.manager.get_rubric_by_id('rubric','owner@test'))

    def test_foreign_owner_cannot_update(self):
        with self.assertRaisesRegex(Exception,'access denied'):
            self.manager.update_rubric('rubric',{'title':'Unauthorized'},'foreign@test')
        self.assertEqual(self.manager.get_rubric_by_id('rubric','owner@test')['title'],'Before')
