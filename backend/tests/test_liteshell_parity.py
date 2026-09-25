"""Complete surface drift gate plus publication and repaired request regressions."""
import json,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from types import SimpleNamespace as N
from fastapi import HTTPException
from lamb.aac.liteshell.shell import COMMAND_CONTRACTS,prepare_command,FILESYSTEM_COMMANDS,FILESYSTEM_OPTIONS
from lamb.aac.liteshell.commands import COMMAND_REGISTRY
from lamb.aac.authorization import ActionAuthorizer
from lamb.aac.skill_routing import DEFAULT_SKILL,BOOTSTRAP,command_context
from tests import test_aac_authoring as authoring
from tests.test_aac_legacy import agent,message,tool,turn

class Surface(unittest.TestCase):
    def test_every_command_has_reviewed_contract_permission_and_recipe(self):
        m=json.loads((Path(__file__).parent/'fixtures/cli_liteshell_parity.json').read_text())
        self.assertEqual({k:list(v) for k,v in COMMAND_CONTRACTS.items()},m['shell_contracts'])
        self.assertEqual(set(COMMAND_REGISTRY),set(COMMAND_CONTRACTS))
        self.assertEqual(set(COMMAND_REGISTRY)-set(m['cli']),set(m['shell_only']))
        for k in COMMAND_REGISTRY:
            self.assertIn(k,BOOTSTRAP|set(DEFAULT_SKILL))
        for k in m['cli']:
            if k not in COMMAND_REGISTRY:
                with self.subTest(command=k),self.assertRaisesRegex(ValueError,'Hold your horses' if k in FILESYSTEM_COMMANDS else 'does not exist and was not executed'):
                    prepare_command('lamb '+k.replace('.',' '))

class Operations(unittest.IsolatedAsyncioTestCase):
    async def test_filesystem_preflight_blocks_all_known_commands_and_option_aliases(self):
        commands=['lamb '+k.replace('.', ' ')+' 42 /tmp/input' for k in FILESYSTEM_COMMANDS]
        commands += ['lamb '+k.replace('.', ' ')+' 42 '+('-' if len(o)==1 else '--')+o.replace('_','-')+' /tmp/input'
                     for k,opts in FILESYSTEM_OPTIONS.items() for o in opts]
        for command in commands:
            with self.subTest(command=command):
                s,h=authoring.Authoring().shell()
                result=await s.execute(command)
                self.assertFalse(result.success);self.assertIn('Hold your horses',result.error)
                h.get.assert_not_awaited();h.post.assert_not_awaited();h.put.assert_not_awaited()
                for stream in (False,True):
                    a,p,s=agent([message(tools=[tool(command)]),message('Use the UI')])
                    await turn(a,stream)
                    s.execute.assert_not_awaited();self.assertIsNone(a.pending_action)

    async def test_file_free_options_remain_available(self):
        for command in ('lamb rubric export 42 -f json', 'lamb assistant create tutor -s hello',
                        'lamb test add 42 Test -m hello', 'lamb docs read ui-knowledge-bases'):
            prepare_command(command)

    async def test_publication_requires_confirmation_plain_and_stream(self):
        for stream in (False,True):
            for command in ('publish','unpublish'):
                a,p,s=agent([message(tools=[tool(f'lamb assistant {command} 42')]),message('Confirm?')])
                await turn(a,stream)
                s.execute.assert_not_awaited();self.assertIsNotNone(a.pending_action)
                p.responses.extend([message('Done')])
                await a.chat('yes')
                s.execute.assert_awaited_once_with(f'lamb assistant {command} 42')
                self.assertIsNone(a.pending_action)

    async def test_natural_refusal_clears_pending_without_execution(self):
        from lamb.aac.authorization import classify_user_confirmation
        for text in ('No, do not publish it.', 'Do not publish it.', "Don't publish it.", 'No, gracias.'):
            self.assertEqual(classify_user_confirmation(text),'reject',text)
            a,p,s=agent([message(tools=[tool('lamb assistant publish 42')]),message('Confirm?'),message('Cancelled')])
            await a.chat('Publish it');await a.chat(text)
            s.execute.assert_not_awaited();self.assertIsNone(a.pending_action)
        self.assertEqual(classify_user_confirmation('Yes, publish it.'),'approve')
        for text in ('Yes, no.', 'Yes, do not publish it.'):
            self.assertEqual(classify_user_confirmation(text),'other')

    async def test_publish_unpublish_request_and_failure_contract(self):
        for verb,published in [('publish',True),('unpublish',False)]:
            s,h=authoring.Authoring().shell();h.put.return_value={'publish_status':published}
            r=await s.execute(f'lamb assistant {verb} 42');self.assertTrue(r.success)
            h.put.assert_awaited_once_with('/creator/assistant/publish/42',json={'publish_status':published})
            self.assertEqual(r.data,{'id':'42','published':published,'response':{'publish_status':published}})
            from lamb.aac.agent.loop import _extract_artifacts
            self.assertEqual(_extract_artifacts(f'lamb assistant {verb} 42',r)[0]['action'],verb)
            h.put.return_value={'success':False,'error':'Denied'}
            self.assertFalse((await s.execute(f'lamb assistant {verb} 42')).success)

    async def test_owner_check_precedes_publication(self):
        from creator_interface import assistant_router as r
        auth=N(user={'email':'other@test'},require_assistant_access=lambda *a,**kw:(_ for _ in ()).throw(HTTPException(403,'owner required')))
        with patch.object(r,'db_manager') as db,self.assertRaises(HTTPException) as raised:
            await r.publish_assistant(42,r.PublishRequest(publish_status=True),N(),auth)
        self.assertEqual(raised.exception.status_code,403);db.get_assistant_by_id.assert_not_called()

    async def test_canonical_and_saved_legacy_evaluation_order(self):
        for args in [('run1','42','good'),('run1','good','42')]:
            s,h=authoring.Authoring().shell()
            self.assertTrue((await s.execute('lamb test evaluate '+' '.join(args))).success)
            h.post.assert_awaited_once_with('/creator/assistant/42/tests/runs/run1/evaluate',json={'verdict':'good','notes':''})
            self.assertEqual(command_context('test.evaluate',list(args),{},{} )['assistant_id'],'42')

    async def test_pagination_filters_and_test_description_alias(self):
        for cmd,path,params in [
            ('assistant list --limit 7 --offset 3','/creator/assistant/get_assistants',{'limit':7,'offset':3}),
            ('rubric list-public --search clarity --subject math --limit 7 --offset 3','/creator/rubrics',{'limit':7,'offset':3,'tab':'templates','search':'clarity','subject':'math'}),
            ('template list -l 7 --offset 3','/creator/prompt-templates/list',{'limit':7,'offset':3}),
            ('test runs 42 -l 7','/creator/assistant/42/tests/runs',{'limit':7})]:
            s,h=authoring.Authoring().shell();self.assertTrue((await s.execute('lamb '+cmd)).success)
            h.get.assert_awaited_once_with(path,params=params)
        s,h=authoring.Authoring().shell();self.assertTrue((await s.execute('lamb test add 42 Test -m hello -d purpose')).success)
        self.assertEqual(h.post.call_args.kwargs['json']['messages'],[{'role':'user','content':'hello'}])
        self.assertEqual(h.post.call_args.kwargs['json']['description'],'purpose')

class TestCaseNames(unittest.IsolatedAsyncioTestCase):
    async def test_aliases_preserve_handlers_permissions_and_assistant_context(self):
        from lamb.aac.contract import command_reference
        for old,new,arguments in [('test.scenarios','test.cases','42'),('test.scenario-detail','test.case-detail','abc 42'),('test.delete-scenario','test.delete-case','abc 42')]:
            self.assertIs(COMMAND_REGISTRY[old],COMMAND_REGISTRY[new])
            self.assertEqual(ActionAuthorizer().check(old),ActionAuthorizer().check(new))
            self.assertEqual(command_context(old,arguments.split(), {}, {}),command_context(new,arguments.split(), {}, {}))
        self.assertIn('lamb test cases:',command_reference())
        self.assertNotIn('lamb test scenarios:',command_reference())
        for option in ('case','scenario','s'):
            shell,http=authoring.Authoring().shell()
            await shell.execute(f'lamb test run 42 --{option} abc' if len(option)>1 else f'lamb test run 42 -{option} abc')
            self.assertEqual(http.post.await_args.kwargs['json']['scenario_id'],'abc')
