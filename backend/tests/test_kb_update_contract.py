"""Creator-to-KB update contract, including the declared Creator response schema."""
import unittest
from unittest.mock import patch
import httpx
from fastapi import HTTPException
from creator_interface.kb_server_manager import KBServerManager
from creator_interface.knowledgebase_classes import KnowledgeBaseUpdate
from creator_interface.knowledges_router import KnowledgeBaseUpdateResponse

class UpdateContract(unittest.IsolatedAsyncioTestCase):
    async def test_partial_update_returns_valid_creator_response(self):
        requests=[]
        def handle(request):
            requests.append(request)
            return httpx.Response(200,json={'id':42,'owner':'7','name':'original'})
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        manager=KBServerManager()
        with patch.object(manager,'_get_kb_config_for_user',return_value={'url':'http://kb','token':'test'}),patch('creator_interface.kb_server_manager.httpx.AsyncClient',return_value=client):
            result=await manager.update_knowledge_base('42',KnowledgeBaseUpdate(description='changed'),{'id':7})
        parsed=KnowledgeBaseUpdateResponse.model_validate(result)
        self.assertEqual(parsed.kb_id,'42');self.assertEqual(parsed.status,'success')
        self.assertEqual([r.method for r in requests],['GET','PATCH'])
        self.assertEqual(requests[1].url.path,'/collections/42')
        self.assertEqual(requests[1].content,b'{"description":"changed"}')

    async def test_foreign_owner_never_reaches_patch(self):
        methods=[]
        def handle(request):
            methods.append(request.method)
            return httpx.Response(200,json={'id':42,'owner':'8','name':'original'})
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle));manager=KBServerManager()
        with patch.object(manager,'_get_kb_config_for_user',return_value={'url':'http://kb','token':'test'}),patch('creator_interface.kb_server_manager.httpx.AsyncClient',return_value=client):
            with self.assertRaises(HTTPException) as error:
                await manager.update_knowledge_base('42',KnowledgeBaseUpdate(description='changed'),{'id':7})
        self.assertEqual(error.exception.status_code,403);self.assertEqual(methods,['GET'])
