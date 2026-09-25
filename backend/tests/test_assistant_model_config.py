import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch
from lamb.assistant_model_config import model_configuration
from tests import test_aac_authoring as authoring

class ModelConfiguration(unittest.TestCase):
    def test_global_wins_even_when_stale_form_model_is_available(self):
        caps={'connectors':{'openai':{'available_llms':['gpt-4o-mini']},'ollama':{'available_llms':['qwen']}}}
        result=model_configuration(caps,{'connector':'openai','llm':'gpt-4o-mini'},{'provider':'ollama','model':'qwen'})
        self.assertEqual(result['model_defaults'],{'connector':'ollama','llm':'qwen'})
        self.assertTrue(result['global_default_available'])

    def test_no_models_does_not_turn_saved_preference_into_availability(self):
        result=model_configuration({}, {'connector':'openai','llm':'old'},{'provider':'ollama','model':'qwen'})
        self.assertEqual(result['model_defaults'],{'connector':'','llm':''})
        self.assertEqual(result['global_default_model'],{'provider':'ollama','model':'qwen'})
        self.assertFalse(result['global_default_available'])

    def test_missing_global_uses_available_form_model_without_debug_fallback(self):
        caps={'connectors':{'bypass':{'available_llms':['bypass']},'ollama':{'available_llms':['qwen']}}}
        self.assertEqual(model_configuration(caps,{'connector':'openai','llm':'old'}, {})['model_defaults'],{'connector':'ollama','llm':'qwen'})
        self.assertEqual(model_configuration({'connectors':{'bypass':caps['connectors']['bypass']}},{}, {})['model_defaults']['connector'],'')

class ModelRoutes(unittest.IsolatedAsyncioTestCase):
    async def test_creator_caps_resolves_authenticated_org(self):
        from creator_interface.assistant_router import get_assistant_capabilities
        auth=N(user={'email':'owner@test'},organization={'config':{'assistant_defaults':{'connector':'openai','llm':'old'}}})
        with patch('lamb.completions.main.list_processors_and_connectors',AsyncMock(return_value={'connectors':{'ollama':{'available_llms':['qwen']}}})) as discover, patch('lamb.completions.org_config_resolver.OrganizationConfigResolver') as resolver:
            resolver.return_value.get_global_default_model_config.return_value={'provider':'ollama','model':'qwen'}
            caps=await get_assistant_capabilities(auth)
            discover.assert_awaited_once_with(auth=auth)
            resolver.assert_called_once_with('owner@test')
            self.assertEqual(caps['model_defaults']['llm'],'qwen')

    async def test_liteshell_uses_form_endpoints_and_distinguishes_defaults(self):
        s,h=authoring.Authoring().shell()
        caps={'connectors':{'ollama':{'available_llms':['qwen']}},'model_defaults':{'connector':'ollama','llm':'qwen'},'global_default_model':{'provider':'ollama','model':'qwen'},'global_default_available':True}
        h.get.side_effect=[caps,{'connector':'openai','llm':'old'}]
        result=await s.execute('lamb assistant config')
        self.assertTrue(result.success,result.error)
        self.assertEqual([c.args[0] for c in h.get.call_args_list],['/creator/assistant/capabilities','/creator/assistant/defaults'])
        self.assertEqual(result.data['defaults']['llm'],'qwen')
        self.assertEqual(result.data['form_defaults']['llm'],'old')
        self.assertEqual(result.data['global_default_model']['model'],'qwen')

    async def test_liteshell_failure_does_not_return_stale_success(self):
        s,h=authoring.Authoring().shell();h.get.side_effect=RuntimeError('discovery unavailable')
        result=await s.execute('lamb assistant config')
        self.assertFalse(result.success)
        self.assertIn('discovery unavailable',result.error)
