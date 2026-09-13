import json
import unittest
from unittest.mock import patch, AsyncMock, Mock
from types import SimpleNamespace
from fastapi import HTTPException
from lamb.services.assistant_model_validation import validate_model_metadata
from lamb.auth_context import AuthContext
from creator_interface import assistant_router as router

CAPS = {'connectors': {'ollama': {'available_llms': ['qwen']}}}

class ModelValidation(unittest.IsolatedAsyncioTestCase):
    def test_invalid_and_valid_pairs(self):
        for value in [None, 'broken', '[]', {}, {'connector':'openai','llm':'qwen'}, {'connector':'ollama','llm':'other'}]:
            self.assertIsNotNone(validate_model_metadata(value, CAPS))
        for value in [{'connector':'ollama','llm':'qwen'}, json.dumps({'connector':'ollama','llm':'qwen'})]:
            self.assertIsNone(validate_model_metadata(value, CAPS))

    async def test_discovery_uses_supplied_owner(self):
        with patch('lamb.completions.main.list_processors_and_connectors', new_callable=AsyncMock, return_value=CAPS) as discovery:
            await router.validate_assistant_model({'connector':'ollama','llm':'qwen'}, 'owner@example.test')
            self.assertEqual(discovery.call_args.kwargs['auth'].user['email'], 'owner@example.test')

    async def test_create_rejects_before_persistence(self):
        request=Mock(); request.json=AsyncMock(return_value={'name':'invalid','metadata':json.dumps({'connector':'openai','llm':'gpt-4o-mini'})})
        auth=AuthContext(user={'id':7,'email':'test@example.test'},token_payload={})
        with patch('lamb.completions.main.list_processors_and_connectors', new_callable=AsyncMock, return_value=CAPS), patch.object(router.db_manager,'get_assistant_by_name',return_value=None), patch.object(router.db_manager,'add_assistant') as add:
            with self.assertRaises(HTTPException) as error:
                await router.create_assistant_directly(request,auth)
            self.assertEqual(error.exception.status_code,400)
            add.assert_not_called()

    async def test_admin_update_checks_owner_and_rejects_before_write(self):
        metadata=json.dumps({'connector':'openai','llm':'bad','prompt_processor':'simple_augment','rag_processor':'no_rag'})
        current=SimpleNamespace(owner='owner@example.test',name='7_test',description='',system_prompt='',prompt_template='',RAG_Top_k=3,RAG_collections='',api_callback=metadata)
        request=Mock(); request.json=AsyncMock(return_value={'description':'changed'})
        auth=Mock(); auth.user={'id':1,'email':'admin@example.test'}
        with patch.object(router,'AssistantService') as service, patch('lamb.completions.main.list_processors_and_connectors',new_callable=AsyncMock,return_value=CAPS) as discovery:
            service.return_value.get_assistant_by_id.return_value=current
            with self.assertRaises(HTTPException) as error:
                await router.update_assistant_proxy(77,request,auth)
            self.assertEqual(error.exception.status_code,400)
            self.assertEqual(discovery.call_args.kwargs['auth'].user['email'],'owner@example.test')
            service.return_value.update_assistant.assert_not_called()

if __name__ == '__main__': unittest.main()
