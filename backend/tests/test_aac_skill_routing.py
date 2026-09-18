from tests.aac_knowledge_fixtures import knowledge_dependencies
"""Workflow routing, exact request prefixes, recipes and permission regressions."""
import json,re,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from types import SimpleNamespace as N
from tests.test_aac_legacy import agent,message,tool,turn
from lamb.aac.liteshell.shell import prepare_command
from lamb.aac.liteshell.commands import COMMAND_REGISTRY,_rubric_form
from lamb.aac.skill_routing import CAPABILITIES,BOOTSTRAP,DEFAULT_SKILL,catalogue_prompt
from lamb.aac.skill_loader import load_skill,SKILLS_DIR
from lamb.evaluaitor.rubric_validator import RubricValidator

class Routing(unittest.IsolatedAsyncioTestCase):
    async def test_freeform_linked_context_reaches_both_transports_once(self):
        for streaming in (False,True):
            a,p,s=agent([message('first'),message('second')])
            a.skill_state={'context':{'assistant_id':89}}
            a.conversation=[{'role':'user','content':'Existing history'}]
            await turn(a,streaming)
            prefix=list(a.conversation)
            await turn(a,streaming)
            notices=[m for m in a.conversation if m.get('content','').startswith('[System: Selected assistant context]')]
            self.assertEqual(len(notices),1)
            self.assertIn('"assistant_id": "89"',notices[0]['content'])
            self.assertEqual(a.conversation[:len(prefix)],prefix)
            self.assertEqual(a.skill_state['announced_assistant_id'],'89')

    async def test_guard_supplies_recipe_before_action_plain_and_stream(self):
        for streaming in (False,True):
            a,p,s=agent([message(tools=[tool('lamb kb get 14')]),message(tools=[tool('lamb kb get 14')]),message('done')])
            a.skill_state={'context':{}}
            self.assertEqual(await turn(a,streaming),'done')
            s.execute.assert_awaited_once_with('lamb kb get 14')
            outputs=[json.loads(m['content']) for m in a.conversation if m['role']=='tool']
            self.assertEqual(outputs[0]['skill_loaded'],'manage-knowledge-base')
            self.assertIn('NOT executed',outputs[0]['error'])
            self.assertIsNone(a.pending_action)

    async def test_multi_call_batch_cannot_execute_after_unseen_recipe(self):
        a,p,s=agent([message(tools=[tool('lamb kb create demo'),tool('lamb kb create demo',ident='second')]),message('review')])
        a.skill_state={'context':{}}
        await a.chat('Create a KB')
        s.execute.assert_not_awaited();self.assertIsNone(a.pending_action)
        self.assertIn('new decision',a.conversation[-2]['content'])

    async def test_skill_load_never_approves_write_and_does_not_repeat_startup(self):
        a,p,s=agent([]);a.skill_state={'context':{}}
        r=await a._execute_tool(tool('lamb skill load manage-knowledge-base'))
        self.assertTrue(r['success']);s.execute.assert_not_awaited()
        r=await a._execute_tool(tool('lamb skill load manage-knowledge-base'))
        self.assertIn('already active',r['data']);s.execute.assert_not_awaited()
        r=await a._execute_tool(tool('lamb kb create demo'))
        self.assertTrue(r['awaiting_user_confirmation']);s.execute.assert_not_awaited()
        r=await a._execute_tool(tool('lamb skill load manage-rubric'))
        self.assertFalse(r['success']);self.assertEqual(a.skill_state['skill_id'],'manage-knowledge-base')

    async def test_reopen_prefix_and_skill_snapshot_survive_disk_changes(self):
        a,p,s=agent([message(tools=[tool('lamb kb get 14')]),message(tools=[tool('lamb kb get 14')]),message('done')])
        a.skill_state={'context':{}};a.system_prompt+='\n'+catalogue_prompt();await a.chat('Check KB')
        saved=json.loads(json.dumps({'conversation':a.conversation,'state':a.skill_state,'system':a.system_prompt}))
        b,p2,s2=agent([message(tools=[tool('lamb kb status 14')]),message('still checked')])
        b.conversation=saved['conversation'];b.skill_state=saved['state'];b.system_prompt=saved['system']
        b.session_logger=MagicMock()
        with patch('lamb.aac.skill_routing.load_skill',side_effect=AssertionError('must reuse active snapshot')):
            await b.chat('Try again')
        previous=p.calls[-1]['messages'];current=p2.calls[0]['messages']
        self.assertEqual(current[:len(previous)],previous)
        prefix=[c.args[1] for c in b.session_logger.log.call_args_list if c.args[0]=='request_prefix'][0]
        self.assertTrue(prefix['prefix_preserved']);self.assertTrue(prefix['tools_unchanged'])
        self.assertEqual(b.skill_state['skill_id'],'manage-knowledge-base')

    async def test_skill_switch_appends_without_rewriting_old_context(self):
        a,p,s=agent([message(tools=[tool('lamb kb get 14')]),message('loaded')]);a.skill_state={'context':{}}
        await a.chat('Inspect KB');before=json.loads(json.dumps(a.conversation))
        p.responses.extend([message(tools=[tool('lamb analytics stats 2')]),message('activity ready')])
        await a.chat('Now inspect assistant activity')
        self.assertEqual(a.conversation[:len(before)],before)
        self.assertEqual(a.skill_state['skill_id'],'inspect-activity')
        s.execute.assert_not_awaited()

    async def test_selected_skill_preparation_persists_and_does_not_greet_again(self):
        from lamb.aac import router as r
        auth=N(user={'email':'x@test','id':1},organization={'id':1},is_system_admin=False,is_org_admin=False)
        session={'id':'test','conversation':[], 'skill_info':{'skill_id':'explain-assistant','context':{'assistant_id':2,'language':'Spanish'}}}
        with knowledge_dependencies(),patch.object(r,'_resolve_agent_llm',return_value=(N(), 'fake')),patch.object(r,'SessionLogger',MagicMock()):
            a,text,state=await r._prepare_agent_and_message(auth,session,'Explica este asistente')
            self.assertEqual(text,'Explica este asistente');self.assertIn('Spanish',a.conversation[-1]['content'])
            session=json.loads(json.dumps({**session,'conversation':a.conversation,'skill_info':state}))
            b,text,state=await r._prepare_agent_and_message(auth,session,'Más detalle')
            self.assertEqual(b.conversation,a.conversation);self.assertEqual(a.system_prompt,b.system_prompt)
            self.assertEqual(b.skill_state['skill_id'],'explain-assistant')
            previous=json.loads(json.dumps(b.conversation))
            session=json.loads(json.dumps({**session,'conversation':b.conversation,'skill_info':state}))
            c,text,state=await r._prepare_agent_and_message(auth,session,'Show activity statistics for assistant 2')
            self.assertEqual(c.skill_state['skill_id'],'inspect-activity')
            self.assertEqual(c.conversation[:len(previous)],previous)
            self.assertIn('Active workflow: inspect-activity',c.conversation[-1]['content'])

    async def test_missing_context_and_path_skill_fail_without_switch(self):
        a,p,s=agent([]);a.skill_state={'context':{}}
        for command in ['lamb skill load explain-assistant','lamb skill load ../secret']:
            result=await a._execute_tool(tool(command));self.assertFalse(result['success'])
        self.assertNotIn('active_snapshot',a.skill_state);s.execute.assert_not_awaited()

class Recipes(unittest.TestCase):
    def test_every_business_command_has_a_workflow(self):
        self.assertEqual(set(COMMAND_REGISTRY)-BOOTSTRAP-set(DEFAULT_SKILL),set())
        for skill in CAPABILITIES:
            self.assertTrue(load_skill(skill,{'assistant_id':1})['prompt'])

    def test_all_marked_command_templates_parse_and_rubric_schema_is_valid(self):
        count=0;rubrics=0
        for path in SKILLS_DIR.glob('*.md'):
            for block in re.findall(r'```aac-command\n(.*?)```',path.read_text(),re.S):
                for line in block.strip().splitlines():
                    for key in ['ASSISTANT_ID','KB_ID','RUBRIC_ID','SCENARIO_ID','RUN_ID','CHAT_ID']:
                        line=line.replace(key,'1')
                    key,args,kwargs,_=prepare_command(line);count+=1
                    if key=='rubric.create':
                        form=_rubric_form({}, {**kwargs,'title':args[0]})
                        for criterion in json.loads(form['criteria']):
                            valid,error=RubricValidator.validate_criterion(criterion);self.assertTrue(valid,error)
                        rubrics+=1
        self.assertGreater(count,20);self.assertEqual(rubrics,1)


class UserTurnSelection(unittest.TestCase):
    def test_clear_activity_request_selected_before_first_command(self):
        from lamb.aac.skill_routing import select_workflow
        state={'skill_id':'manage-knowledge-base','context':{'language':'English'},'active_snapshot':'old'}
        for text in ['For assistant 30, show saved student activity statistics and a dated timeline. Read-only.',
                     'Muestra la actividad del asistente 30, sin cambios.',
                     "Mostra les estadistiques de l'assistent 30, sense canvis."]:
            selected=select_workflow(text,state)
            self.assertEqual(selected[0],'inspect-activity');self.assertEqual(selected[1]['assistant_id'],'30')

    def test_scenario_update_does_not_select_assistant_improvement(self):
        from lamb.aac.skill_routing import select_workflow
        state={'skill_id':'improve-assistant','context':{'assistant_id':87},'active_snapshot':'old'}
        for text in ['Propose the same expected-only update again for assistant 87 test case abc: expected Tuesday. Do not change other fields.',
                     'Edit test scenario abc for assistant 87 using test-and-evaluate.',
                     'Editar el caso de prueba abc del asistente 87.']:
            self.assertEqual(select_workflow(text,state)[0],'test-and-evaluate',text)
        selected=select_workflow('Update the description of assistant 87',{'context':{'assistant_id':87}})
        self.assertEqual(selected[0],'improve-assistant')

    def test_ambiguity_negation_and_followups_do_not_switch(self):
        from lamb.aac.skill_routing import select_workflow
        state={'skill_id':'manage-knowledge-base','context':{},'active_snapshot':'old'}
        for text in ['Try again','Create an assistant and a rubric','Do not inspect activity for assistant 30',
                     'Show activity for another assistant','Show activity']:
            self.assertIsNone(select_workflow(text,state),text)


class SelectedActivityContext(unittest.TestCase):
    def test_recipe_names_selected_assistant(self):
        prompt=load_skill('inspect-activity', {'assistant_id':77})['prompt']
        self.assertIn('selected assistant ID is `77`',prompt)


class ContextIdentityTests(unittest.TestCase):
    def test_integer_session_target_matches_cli_target_without_reloading(self):
        from lamb.aac.skill_routing import select_workflow
        a,_,_=agent([])
        a.skill_state={'context':{'assistant_id':25,'language':'English'}}
        instructions=a.activate_skill('explain-assistant')
        self.assertIn('Selected context (data):',instructions)
        self.assertIn('"assistant_id": "25"',instructions)
        count=len(a.skill_state['snapshots'])
        a.skill_state['context']['assistant_id']=25  # legacy persisted JSON
        self.assertIsNone(a.required_skill('assistant.get',['25'],{}))
        self.assertIsNone(select_workflow('explain assistant 25',a.skill_state))
        self.assertEqual(len(a.skill_state['snapshots']),count)

class ScenarioTerminology(unittest.TestCase):
    def test_unqualified_scenario_means_learning_context_even_with_linked_assistant(self):
        from lamb.aac.skill_routing import select_workflow
        for text in ['Create a scenario', 'Edit my scenario for assistant 87', 'Editar mi escenario', 'Edita el meu escenari']:
            self.assertEqual(select_workflow(text, {'context': {'assistant_id': 87}})[0], 'manage-learning-scenarios', text)
        for text in ['Run test cases for assistant 87', 'List test scenarios for assistant 87', 'Muestra escenarios de prueba del asistente 87', 'Mostra els casos de prova de l’assistent 87']:
            self.assertEqual(select_workflow(text, {'context': {'assistant_id': 87}})[0], 'test-and-evaluate', text)
