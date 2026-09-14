import asyncio
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from lamb.aac.frontend import Mailbox, FrontendBridge
from lamb.aac.liteshell.shell import prepare_command
from tests.test_aac_authoring import Authoring

class FrontendTests(unittest.IsolatedAsyncioTestCase):
    async def test_contract_and_absent_browser(self):
        for command in ('frontend-manage open assistant 80 --tab properties', 'frontend-manage open kb 15 --tab ingest', 'frontend-manage current'):
            prepare_command(command)
            s,h=Authoring().shell();r=await s.execute(command)
            self.assertFalse(r.success);self.assertIn('No connected frontend',r.error);h.get.assert_not_awaited()
        for command in ('frontend-manage open assistant 1 --tab delete', 'frontend-manage open kb ../x', 'frontend-manage open url 1', 'frontend-manage open assistant 0', 'frontend-manage open assistant 1 --url https://example.com'):
            with self.subTest(command=command), self.assertRaises(ValueError):prepare_command(command)

    async def test_permission_before_browser_and_actual_ack(self):
        s,h=Authoring().shell();s.frontend=AsyncMock(return_value={'status':'opened','resource':'assistant','id':'80','tab':'tests'})
        self.assertTrue((await s.execute('frontend-manage open assistant 80 --tab tests')).success)
        h.get.assert_awaited_once_with('/creator/assistant/get_assistant/80')
        s.frontend.assert_awaited_once_with({'operation':'open','resource':'assistant','id':'80','tab':'tests'})
        h.get.side_effect=ValueError('403');s.frontend.reset_mock()
        self.assertFalse((await s.execute('frontend-manage open assistant 80')).success)
        s.frontend.assert_not_awaited()

    async def test_guided_destinations_and_permission_failures(self):
        rubric = '12345678-1234-4234-8234-123456789012'
        cases = [
            ('assistants', {'resource': 'assistants', 'id': '', 'tab': ''}, None),
            ('assistant-create', {'resource': 'assistant-create', 'id': '', 'tab': ''}, None),
            ('assistant 80 --tab activity', {'resource': 'assistant', 'id': '80', 'tab': 'activity'}, '/creator/assistant/get_assistant/80'),
            ('assistant 80 --tab edit', {'resource': 'assistant', 'id': '80', 'tab': 'edit'}, '/creator/assistant/get_assistant/80'),
            (f'rubric {rubric}', {'resource': 'rubric', 'id': rubric, 'tab': 'view'}, f'/creator/rubrics/{rubric}'),
        ]
        for command, target, path in cases:
            with self.subTest(command=command):
                s,h=Authoring().shell()
                s.frontend=AsyncMock(return_value={'status':'opened', **target})
                self.assertTrue((await s.execute('frontend-manage open '+command)).success)
                s.frontend.assert_awaited_once_with({'operation':'open', **target})
                if path:
                    h.get.assert_awaited_once_with(path)
                    h.get.side_effect=ValueError('403');s.frontend.reset_mock()
                    self.assertFalse((await s.execute('frontend-manage open '+command)).success)
                    s.frontend.assert_not_awaited()
                else:
                    h.get.assert_not_awaited()
        for target in ('assistants 1', 'assistant-create --tab tests', 'rubric ../file', 'rubric 1', f'rubric {rubric} --tab delete', 'assistant 1 --tab publish'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                prepare_command('frontend-manage open '+target)

    async def test_shared_mailbox_isolation_expiry_and_single_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            db=SimpleNamespace(table_prefix='',get_connection=lambda:sqlite3.connect(directory+'/test.db'))
            box=Mailbox(db);other=Mailbox(db)
            a=box.create('s','owner','channel',{'operation':'open','id':'80'})
            pending=other.pending('s','owner','channel')[0]
            self.assertEqual({k:v for k,v in pending.items() if k!='expires'}, {'action_id':a,'operation':'open','id':'80'})
            self.assertGreater(pending['expires'],0)
            self.assertEqual(other.pending('s','foreign','channel'),[])
            for session,owner,channel in [('wrong','owner','channel'),('s','foreign','channel'),('s','owner','wrong')]:
                self.assertFalse(other.acknowledge(a,session,owner,channel,{'status':'current'}))
            self.assertTrue(other.acknowledge(a,'s','owner','channel',{'status':'current'}))
            self.assertFalse(other.acknowledge(a,'s','owner','channel',{'status':'current'}))
            self.assertEqual(box.result(a),{'status':'current'})
            b=box.create('s','owner','channel',{'operation':'current'})
            box.expire('s','owner','channel')
            self.assertEqual(box.pending('s','owner','channel'),[])
            self.assertFalse(box.acknowledge(b,'s','owner','channel',{'status':'current'}))
            self.assertIsNone(box.result(b))

    async def test_bridge_waits_and_reports_failure_instead_of_success(self):
        payload={'operation':'open','resource':'assistant','id':'80','tab':'tests'}
        for result in ({'status':'blocked','reason':'Unsaved'}, {'status':'opened','resource':'assistant','id':'81','tab':'tests'}, {'status':'current'}):
            with patch('lamb.aac.frontend.Mailbox') as factory:
                factory.return_value.result.return_value=result
                bridge=FrontendBridge('s','owner','00000000-0000-4000-8000-000000000001')
                with self.assertRaises(ValueError):await bridge.request(payload)
                bridge.close();factory.return_value.expire.assert_called_once()
        with patch('lamb.aac.frontend.Mailbox') as factory,patch('lamb.aac.frontend.asyncio.sleep',new_callable=AsyncMock):
            factory.return_value.result.return_value=None
            bridge=FrontendBridge('s','owner','00000000-0000-4000-8000-000000000001')
            with self.assertRaisesRegex(ValueError,'timed out'):await bridge.request(payload)
