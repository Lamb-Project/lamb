"""Expose actual registry discovery with the same auth as ingestion discovery."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app, verify_token, QueryService

class QueryDiscovery(unittest.TestCase):
    def test_registry_and_auth(self):
        client=TestClient(app)
        self.assertIn(client.get('/query/plugins').status_code,[401,403])
        plugins=[{'name':'test_query','description':'Test registry','parameters':{},'mode':'ADVANCED'}]
        app.dependency_overrides[verify_token]=lambda:'test-token'
        try:
            with patch.object(QueryService,'list_plugins',return_value=plugins) as listing:
                result=client.get('/query/plugins')
                self.assertEqual(result.status_code,200)
                self.assertEqual(result.json(),plugins)
                listing.assert_called_once_with()
        finally:
            app.dependency_overrides.pop(verify_token,None)
