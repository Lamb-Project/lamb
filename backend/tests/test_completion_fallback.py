import unittest
from unittest.mock import patch,Mock,AsyncMock
from types import SimpleNamespace as N
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.completions.main import resolve_completion_config
from creator_interface import assistant_router as router
import json

class Fallback(unittest.IsolatedAsyncioTestCase):
    def resolver(self):
        r=OrganizationConfigResolver('owner@example.test')
        r._org={'id':2,'config':{'setups':{'default':{'global_default_model':{'provider':'ollama','model':'qwen'},'providers':{'ollama':{'enabled':True,'models':['qwen']},'openai':{'enabled':False,'models':['old']}}}}}}
        return r
    def test_disabled_and_missing_connector_falls_back(self):
        r=self.resolver()
        for provider,model in [('openai','old'),('removed','x'),('', '')]:
            self.assertEqual(r.resolve_model_for_completion(model,provider,{'ollama'}),{'provider':'ollama','model':'qwen'})
        with self.assertRaises(ValueError):r.resolve_model_for_completion('old','openai',set())
    def test_dispatch_keeps_stored_preference(self):
        preference={'connector':'openai','llm':'old','rag_processor':'no_rag'}
        with patch('lamb.completions.org_config_resolver.OrganizationConfigResolver',return_value=self.resolver()),patch('lamb.completions.main.load_plugins',return_value={'ollama':None}):
            effective=resolve_completion_config(N(owner='owner@example.test'),preference)
        self.assertEqual(effective['connector'],'ollama')
        self.assertEqual(preference['connector'],'openai')
    async def test_description_edit_does_not_discover_models_or_require_legacy_llm(self):
        metadata=json.dumps({'connector':'openai','prompt_processor':'simple_augment','rag_processor':'no_rag'})
        current=N(owner='owner@example.test',name='7_test',description='',system_prompt='',prompt_template='',RAG_Top_k=3,RAG_collections='',api_callback=metadata)
        request=N(json=AsyncMock(return_value={'description':'changed'}));auth=Mock();auth.user={'id':1,'email':'admin@example.test'}
        with patch.object(router,'AssistantService') as svc,patch('lamb.completions.main.list_processors_and_connectors',side_effect=RuntimeError('provider down')) as discovery:
            svc.return_value.get_assistant_by_id.return_value=current
            self.assertEqual((await router.update_assistant_proxy(77,request,auth))['assistant_id'],77)
            discovery.assert_not_called()
            self.assertEqual(svc.return_value.update_assistant.call_args.args[1].owner,current.owner)
