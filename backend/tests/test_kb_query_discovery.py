"""Query discovery must use the user's KB and accept query-only metadata."""
import unittest
from unittest.mock import AsyncMock, Mock, patch
import httpx
from fastapi import HTTPException
from creator_interface.kb_server_manager import KBServerManager
from creator_interface import knowledges_router as router

class QueryDiscovery(unittest.IsolatedAsyncioTestCase):
    async def test_org_route_and_query_shape(self):
        user={'email':'teacher@example.test'}
        plugins=[{'name':'simple_query','description':'Vector query','mode':'SIMPLIFIED','parameters':{'top_k':{'type':'integer','default':5}}}]
        manager=KBServerManager()
        client=AsyncMock();client.get.return_value=httpx.Response(200,json=plugins)
        with patch.object(manager,'_get_kb_config_for_user',return_value={'url':'http://org-kb/','token':'org-test-token'}) as config, patch('creator_interface.kb_server_manager.httpx.AsyncClient') as factory:
            factory.return_value.__aenter__.return_value=client
            self.assertEqual(await manager.get_query_plugins(user),plugins)
            config.assert_called_once_with(user)
            client.get.assert_awaited_once_with('http://org-kb/query/plugins',headers={'Authorization':'Bearer org-test-token'})
        with patch.object(router,'authenticate_creator_user',AsyncMock(return_value=user)),patch.object(router.kb_server_manager,'is_kb_server_available',AsyncMock(return_value=True)),patch.object(router.kb_server_manager,'get_query_plugins',AsyncMock(return_value=plugins)) as get:
            result=await router.get_query_plugins(Mock())
            get.assert_awaited_once_with(user)
            self.assertEqual(router.GetQueryPluginsResponse(**result).plugins[0].name,'simple_query')

    async def test_upstream_error_and_invalid_shape(self):
        manager=KBServerManager()
        for response,status in [(httpx.Response(403,json={'detail':'Denied'}),403),(httpx.Response(200,json={'unexpected':[]}),502)]:
            client=AsyncMock();client.get.return_value=response
            with patch.object(manager,'_get_kb_config_for_user',return_value={'url':'http://org-kb','token':'test'}),patch('creator_interface.kb_server_manager.httpx.AsyncClient') as factory:
                factory.return_value.__aenter__.return_value=client
                with self.assertRaises(HTTPException) as error:await manager.get_query_plugins({'email':'test'})
                self.assertEqual(error.exception.status_code,status)
