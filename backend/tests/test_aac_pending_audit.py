from tests.aac_knowledge_fixtures import knowledge_dependencies
"""Second-letter recovery, payload and rubric/model boundary regressions."""
import copy,json,unittest
from types import SimpleNamespace as N
from unittest.mock import Mock,patch
from lamb.aac.session_guidance import refresh_guidance,browser_session,POLICY_VERSION
from lamb.aac.liteshell.commands import _apply_weights
from lamb.completions.org_config_resolver import OrganizationConfigResolver

class Guidance(unittest.TestCase):
    def test_version_refresh_is_once_and_defers_exact_pending_action(self):
        state={'system_prompt':'old','active_snapshot':'old-key','snapshots':{'old-key':{'prompt':'history'}},'context':{'language':'Spanish'}}
        agent=N(system_prompt='new',load_skills=Mock())
        self.assertIsNone(refresh_guidance(agent,state,{'pending_action':{'command':'exact'}},'skills'))
        self.assertEqual(state['system_prompt'],'old');agent.load_skills.assert_not_called()
        self.assertTrue(refresh_guidance(agent,state,{},'skills'))
        self.assertEqual(state['system_prompt'],'new');self.assertEqual(state['policy_version'],POLICY_VERSION)
        self.assertNotIn('active_snapshot',state);self.assertIn('old-key',state['snapshots'])
        self.assertIsNone(refresh_guidance(agent,state,{},'skills'));agent.load_skills.assert_called_once()

    def test_browser_transcript_omits_prompts_but_preserves_visible_history(self):
        session={'conversation':[{'role':'system','content':'private policy'},{'role':'user','content':'[System: workflow] secret'},
            {'role':'user','content':'hello'},{'role':'assistant','content':'hi'},{'role':'tool','content':'raw output'}],
            'skill_info':{'system_prompt':'secret','snapshots':{'a':{'prompt':'secret'}},'ui_language':'es'},'tool_audit':[{'output':'raw'}]}
        original=copy.deepcopy(session);result=browser_session(session)
        self.assertEqual([m['content'] for m in result['conversation']],['hello','hi'])
        self.assertNotIn('secret',json.dumps(result));self.assertEqual(result['tool_audit_count'],1)
        self.assertEqual(session,original)

class Weights(unittest.TestCase):
    def test_only_single_partial_repair_can_leave_a_bad_total(self):
        criteria=[{'name':'a','weight':20},{'name':'b','weight':20},{'name':'c','weight':20}]
        self.assertEqual(_apply_weights(criteria,'{"a":30}')[0]['weight'],30)
        for patch_value in ['{"a":30,"b":30}', '{"a":20,"b":20,"c":20}']:
            with self.assertRaises(ValueError):_apply_weights(criteria,patch_value)
        self.assertEqual(sum(c['weight'] for c in _apply_weights(criteria,'{"a":60}')),100)
        with self.assertRaises(ValueError):_apply_weights([{'name':'a','weight':20}],'{"a":50}')

class Models(unittest.TestCase):
    def resolver(self,config):
        obj=object.__new__(OrganizationConfigResolver);obj.setup_name='default'
        obj._org={'config':{'setups':{'default':{'providers':config}}}}
        obj.get_provider_config=lambda name:config.get(name,{})
        obj.get_global_default_model_config=lambda:{'provider':'ollama','model':'fallback'}
        return obj
    def test_unknown_catalog_allows_named_model_but_disabled_and_allowlist_do_not(self):
        for catalog in [None,[]]:
            r=self.resolver({'ollama':{'enabled':True,'models':catalog}})
            self.assertEqual(r.resolve_model_for_completion('named','ollama',['ollama'])['model'],'named')
        r=self.resolver({'ollama':{'enabled':True,'models':['fallback']}})
        self.assertEqual(r.resolve_model_for_completion('outside','ollama',['ollama'])['model'],'fallback')
        for config in [{'enabled':False,'models':[]},{'enabled':True,'models':['named']}]:
            r=self.resolver({'ollama':config})
            with self.assertRaises(ValueError):r.resolve_model_for_completion('named','ollama',[])
        with self.assertRaises(ValueError):self.resolver({'ollama':{'enabled':False}}).resolve_model_for_completion('named','ollama')

class Recovery(unittest.IsolatedAsyncioTestCase):
    async def test_retired_saved_skill_recovers_and_invalid_new_selection_rejected(self):
        from lamb.aac import router as r
        from fastapi import HTTPException
        auth=N(user={'email':'owner@test','id':1},organization={'id':1},is_system_admin=False,is_org_admin=False)
        session={'id':'old','conversation':[{'role':'user','content':'hello'}],
            'skill_info':{'skill_id':'retired-skill','context':{},'ui_language':'es'}}
        with knowledge_dependencies(),patch.object(r,'_resolve_agent_llm',return_value=(N(),'fake')),patch.object(r,'SessionLogger'):
            agent, message, state=await r._prepare_agent_and_message(auth,session,'hello')
        self.assertIsNone(state['skill_id'])
        self.assertEqual(agent.conversation[0],session['conversation'][0])
        self.assertIn('no está disponible',agent.conversation[-1]['content'])
        with self.assertRaises(HTTPException):r._validate_skill_selection('retired-skill',{})

    async def test_browser_and_diagnostics_both_check_ownership(self):
        from lamb.aac import router as r
        from fastapi import HTTPException
        auth=N(user={'email':'owner@test'})
        session={'id':'s','conversation':[],'skill_info':{'system_prompt':'secret'}}
        with patch.object(r,'AACSessionManager') as manager:
            manager.return_value.get_session.return_value=session
            self.assertNotIn('secret',json.dumps(await r.get_session('s',auth)))
            self.assertEqual(await r.get_session('s',auth,True),session)
            manager.return_value.get_session.assert_called_with('s','owner@test')
            manager.return_value.get_session.return_value=None
            for diagnostics in [False,True]:
                with self.assertRaises(HTTPException) as error:await r.get_session('s',auth,diagnostics)
                self.assertEqual(error.exception.status_code,404)
