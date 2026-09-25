import asyncio
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from lamb.aac.frontend import Mailbox, FrontendBridge, stream_with_frontend
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
            for session,owner,channel in [('wrong','owner','channel'),('s','foreign','channel'),('s','owner','wrong')]:
                self.assertFalse(other.claim(a,session,owner,channel))
                self.assertFalse(other.acknowledge(a,session,owner,channel,{'status':'current'}))
            self.assertTrue(other.claim(a,'s','owner','channel'))
            self.assertFalse(other.claim(a,'s','owner','channel'))
            self.assertIsNone(box.result(a))
            self.assertTrue(other.acknowledge(a,'s','owner','channel',{'status':'current'}))
            self.assertFalse(other.acknowledge(a,'s','owner','channel',{'status':'current'}))
            self.assertEqual(box.result(a),{'status':'current'})
            b=box.create('s','owner','channel',{'operation':'current'})
            box.expire('s','owner','channel')
            self.assertFalse(other.claim(b,'s','owner','channel'))
            self.assertFalse(box.acknowledge(b,'s','owner','channel',{'status':'current'}))
            self.assertIsNone(box.result(b))

    async def test_bridge_waits_and_reports_failure_instead_of_success(self):
        payload={'operation':'open','resource':'assistant','id':'80','tab':'tests'}
        for result in ({'status':'blocked','reason':'Unsaved'}, {'status':'opened','resource':'assistant','id':'81','tab':'tests'}, {'status':'current'}):
            with patch('lamb.aac.frontend.get_mailbox') as factory:
                factory.return_value.result.return_value=result
                bridge=FrontendBridge('s','owner','00000000-0000-4000-8000-000000000001')
                bridge.emit=AsyncMock()
                with self.assertRaises(ValueError):await bridge.request(payload)
                bridge.close();factory.return_value.expire.assert_called_once()
        with patch('lamb.aac.frontend.get_mailbox') as factory,patch('lamb.aac.frontend.asyncio.sleep',new_callable=AsyncMock):
            factory.return_value.result.return_value=None
            bridge=FrontendBridge('s','owner','00000000-0000-4000-8000-000000000001')
            bridge.emit=AsyncMock()
            with self.assertRaisesRegex(ValueError,'timed out'):await bridge.request(payload)

    async def test_stream_delivers_action_while_tool_waits_then_ack_on_another_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            db=SimpleNamespace(table_prefix='', get_connection=lambda:sqlite3.connect(directory+'/test.db'))
            box=Mailbox(db); other=Mailbox(db)
            with patch('lamb.aac.frontend.get_mailbox', return_value=box):
                bridge=FrontendBridge('s','owner','00000000-0000-4000-8000-000000000001')
            payload={'operation':'open','resource':'assistant','id':'80','tab':'tests'}
            async def model():
                result=await bridge.request(payload)
                yield {'content': result['status']}
            events=stream_with_frontend(model(), bridge)
            event=await asyncio.wait_for(anext(events), 1)
            action=event['frontend_action']['action_id']
            self.assertTrue(other.claim(action,'s','owner',bridge.channel))
            self.assertTrue(other.acknowledge(action,'s','owner',bridge.channel,{'status':'opened',**payload}))
            self.assertEqual(await asyncio.wait_for(anext(events),1), {'content':'opened'})
            await events.aclose()
            bridge.close()

    async def test_consumer_close_cancels_waiting_tool_and_finalizes_source(self):
        closed=asyncio.Event()
        with patch('lamb.aac.frontend.get_mailbox') as factory:
            factory.return_value.result.return_value=None
            bridge=FrontendBridge('s','owner','00000000-0000-4000-8000-000000000001')
            async def model():
                try:
                    await bridge.request({'operation':'current'})
                    yield 'unexpected'
                finally:
                    closed.set()
            events=stream_with_frontend(model(),bridge)
            self.assertIn('frontend_action',await asyncio.wait_for(anext(events),1))
            await asyncio.wait_for(events.aclose(),1)
            self.assertTrue(closed.is_set())
            self.assertIsNone(bridge.emit)

    async def test_connections_closed_and_expiry_uses_server_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            connections=[]
            def connect():
                c=sqlite3.connect(directory+'/test.db');connections.append(c);return c
            box=Mailbox(SimpleNamespace(table_prefix='',get_connection=connect))
            action=box.create('s','owner','c',{},ttl=-1)
            self.assertFalse(box.claim(action,'s','owner','c'))
            self.assertFalse(box.acknowledge(action,'s','owner','c',{'status':'current'}))
            self.assertIsNone(box.result(action))
            box.expire('s','owner','c')
            for c in connections:
                with self.assertRaises(sqlite3.ProgrammingError):c.execute('SELECT 1')

    async def test_source_cancel_and_close_error_propagate_without_hanging(self):
        for error in (asyncio.CancelledError(), RuntimeError('close failed')):
            async def source():
                try:
                    yield 'start'
                finally:
                    raise error
            events=stream_with_frontend(source(), None)
            self.assertEqual(await asyncio.wait_for(anext(events),1),'start')
            with self.assertRaises(type(error)):
                await asyncio.wait_for(anext(events),1)
            await events.aclose()
