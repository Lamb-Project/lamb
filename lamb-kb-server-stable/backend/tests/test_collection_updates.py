"""Metadata PATCH routing, authentication and rejected-rename atomicity."""
import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from database.connection import get_db
from database.service import CollectionService
from routers.collections import router

class CollectionUpdates(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(router)
        self.db=Mock();app.dependency_overrides[get_db]=lambda:self.db
        self.client=TestClient(app)
        self.headers={'Authorization':'Bearer test-token'}
        p=patch('dependencies.API_KEY','test-token');p.start();self.addCleanup(p.stop)

    def test_authenticated_partial_update_safe_response(self):
        collection={'id':42,'name':'original','description':'changed','owner':'7','visibility':'private','creation_date':'2026-09-16T00:00:00','embeddings_model':{'model':'embed','vendor':'ollama','apikey':'never-return-this'}}
        with patch.object(CollectionService,'update_collection',return_value=collection) as update:
            r=self.client.patch('/collections/42',headers=self.headers,json={'description':'changed'})
            self.assertEqual(r.status_code,200,r.text)
            update.assert_called_once_with(self.db,42,description='changed')
            self.assertNotIn('never-return-this',r.text)
            self.assertEqual(r.json()['name'],'original')

    def test_auth_missing_unknown_and_disallowed_fields(self):
        with patch.object(CollectionService,'update_collection',return_value=None) as update:
            self.assertIn(self.client.patch('/collections/42',json={'description':'x'}).status_code,(401,403))
            self.assertEqual(self.client.patch('/collections/42',headers={'Authorization':'Bearer wrong'},json={'description':'x'}).status_code,401)
            update.assert_not_called()
            for body in ({'owner':'other'},{'visibility':'invalid'},{'embeddings_model':{'apikey':'x'}}):
                self.assertEqual(self.client.patch('/collections/42',headers=self.headers,json=body).status_code,422)
            update.assert_not_called()
            self.assertEqual(self.client.patch('/collections/42',headers=self.headers,json={}).status_code,400)
            self.assertEqual(self.client.patch('/collections/42',headers=self.headers,json={'description':'x'}).status_code,404)

    def test_rejected_rename_does_not_commit_sql(self):
        row=Mock(name='row');row.name='original';row.embeddings_model={}
        self.db.query.return_value.get.return_value=row
        chroma=Mock();chroma.get_collection.return_value.modify.side_effect=ValueError('bad name')
        with patch('database.service.get_chroma_client',return_value=chroma):
            with self.assertRaises(ValueError):CollectionService.update_collection(self.db,42,name='invalid')
        self.db.commit.assert_not_called();self.db.rollback.assert_called_once()

    def test_sql_commit_failure_compensates_chroma_rename(self):
        row=Mock();row.name='original';row.embeddings_model={}
        self.db.query.return_value.get.return_value=row
        self.db.commit.side_effect=RuntimeError('SQL failure')
        chroma=Mock()
        with patch('database.service.get_chroma_client',return_value=chroma):
            with self.assertRaises(RuntimeError):CollectionService.update_collection(self.db,42,name='renamed')
        self.assertEqual([c.kwargs for c in chroma.get_collection.return_value.modify.call_args_list],[{'name':'renamed'},{'name':'original'}])
        self.db.rollback.assert_called_once()

if __name__=='__main__':unittest.main()
