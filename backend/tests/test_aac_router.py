"""Request lifecycle regressions: state and resources survive failed/cancelled turns."""
import asyncio
import unittest
import tempfile
from pathlib import Path
from lamb.aac import turn_lock
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException
from lamb.aac import router as r

class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        patcher=patch.object(turn_lock,'LOCK_ROOT',Path(temp.name));patcher.start();self.addCleanup(patcher.stop)

    def fixture(self):
        a=N(conversation=[{'role':'user','content':'hello'}],pending_action={'command':'lamb assistant update 1'},
            tool_audit=[{'success':True}],shell=N(close=AsyncMock()),llm_client=N(close=AsyncMock()),
            session_logger=None,chat=AsyncMock(return_value='done'),get_stats=lambda:{'turns':1})
        mgr=Mock();mgr.get_session.return_value={'id':'s'}
        req=N(json=AsyncMock(return_value={'message':'hello'}),headers={})
        auth=N(user={'email':'teacher@example.test'},organization={'id':1})
        return a,mgr,req,auth

    async def test_plain_success_failure_and_cancel_persist_and_close(self):
        for error in [None,RuntimeError('provider failed'),asyncio.CancelledError()]:
            with self.subTest(error=type(error).__name__):
                a,mgr,req,auth=self.fixture();a.chat.side_effect=error
                with patch.object(r,'AACSessionManager',return_value=mgr),patch.object(r,'_prepare_agent_and_message',AsyncMock(return_value=(a,'hello',None))):
                    if error:
                        with self.assertRaises(asyncio.CancelledError if isinstance(error,asyncio.CancelledError) else HTTPException):
                            await r.send_message('s',req,auth)
                    else:self.assertEqual((await r.send_message('s',req,auth))['response'],'done')
                mgr.update_conversation.assert_called_once()
                self.assertEqual(mgr.update_conversation.call_args.kwargs['pending_action'],a.pending_action)
                self.assertEqual(mgr.update_conversation.call_args.kwargs['tool_audit'],a.tool_audit)
                a.shell.close.assert_awaited_once();a.llm_client.close.assert_awaited_once()

    async def test_stream_failure_and_disconnect_persist(self):
        for error in [None,RuntimeError('provider failed'),asyncio.CancelledError()]:
            a,mgr,req,auth=self.fixture()
            async def chunks(message):
                yield 'partial'
                if error:raise error
            a.chat_stream=chunks
            with patch.object(r,'AACSessionManager',return_value=mgr),patch.object(r,'_prepare_agent_and_message',AsyncMock(return_value=(a,'hello',None))):
                response=await r.send_message_stream('s',req,auth)
                if isinstance(error,asyncio.CancelledError):
                    with self.assertRaises(asyncio.CancelledError):
                        _=[x async for x in response.body_iterator]
                else:
                    output=''.join([x async for x in response.body_iterator])
                    self.assertIn('[DONE]',output)
                    self.assertEqual('provider failed' in output,error is not None)
            mgr.update_conversation.assert_called_once()
            a.shell.close.assert_awaited_once();a.llm_client.close.assert_awaited_once()

    async def test_persistence_or_shell_close_failure_still_closes_llm(self):
        for where in ['db','shell']:
            a,mgr,_,_=self.fixture()
            if where=='db':mgr.update_conversation.side_effect=RuntimeError('db failed')
            else:a.shell.close.side_effect=RuntimeError('close failed')
            with self.assertRaises(RuntimeError):await r._finish_turn(mgr,a,'s','e',None)
            a.shell.close.assert_awaited_once();a.llm_client.close.assert_awaited_once()

    async def test_missing_session_never_builds_agent(self):
        a,mgr,req,auth=self.fixture();mgr.get_session.return_value=None
        for endpoint in [r.send_message,r.send_message_stream]:
            with patch.object(r,'AACSessionManager',return_value=mgr),patch.object(r,'_prepare_agent_and_message',AsyncMock()) as build:
                with self.assertRaises(HTTPException) as error:await endpoint('foreign',req,auth)
                self.assertEqual(error.exception.status_code,404);build.assert_not_awaited()

    async def test_invalid_message_shapes_are_client_errors(self):
        for body in [None, [], {}, {'message':None}, {'message':42}, {'message':[]}, {'message':'  '}]:
            for endpoint in [r.send_message,r.send_message_stream]:
                _,_,req,auth=self.fixture();req.json.return_value=body
                with self.assertRaises(HTTPException) as error:await endpoint('s',req,auth)
                self.assertEqual(error.exception.status_code,400)


class ProviderRoutingTests(unittest.TestCase):
    def resolve(self, default, config):
        with patch.object(r, 'OrganizationConfigResolver') as resolver, patch.object(r, 'AsyncOpenAI') as client:
            resolver.return_value.get_global_default_model_config.return_value = default
            resolver.return_value.get_provider_config.return_value = config
            result = r._resolve_agent_llm('owner@example.test')
            return result, client.call_args.kwargs, resolver.return_value.get_provider_config.call_args.args[0]

    def test_ollama_stays_local_and_preserves_selected_model(self):
        for base in ['http://localhost:11434', 'http://localhost:11434/v1/']:
            result, kwargs, provider = self.resolve({'provider':'ollama','model':'qwen3.8:27b-mlx'}, {'base_url':base,'enabled':True})
            self.assertEqual(provider, 'ollama')
            self.assertEqual(result[1], 'qwen3.8:27b-mlx')
            self.assertEqual(kwargs, {'base_url':'http://localhost:11434/v1','api_key':'ollama'})

    def test_openai_compatible_route_and_legacy_default(self):
        result, kwargs, provider = self.resolve({}, {'api_key':'test-key','base_url':'http://proxy/v1','default_model':'test-model'})
        self.assertEqual(provider,'openai');self.assertEqual(result[1],'test-model')
        self.assertEqual(kwargs['base_url'],'http://proxy/v1')

    def test_invalid_provider_never_falls_back_to_cloud(self):
        for default, config in [({'provider':'google'}, {}), ({'provider':'ollama','model':'qwen'}, {}), ({'provider':'ollama','model':'qwen'}, {'base_url':'http://local','enabled':False}), ({'provider':'ollama'}, {'base_url':'http://local'}), ({'provider':'openai'}, {'enabled':True})]:
            with self.subTest(default=default, config=config), self.assertRaises(HTTPException):
                self.resolve(default,config)

class ConcurrentTurns(unittest.IsolatedAsyncioTestCase):
    fixture=LifecycleTests.fixture
    setUp=LifecycleTests.setUp
    async def test_overlapping_turn_rejected_before_agent_build(self):
        for second_endpoint in [r.send_message,r.send_message_stream]:
            a,mgr,req,auth=self.fixture()
            entered=asyncio.Event();release=asyncio.Event()
            async def first_chat(message):
                entered.set();await release.wait();return 'first'
            a.chat.side_effect=first_chat
            b,_,_,_=self.fixture()
            build=AsyncMock(side_effect=[(a,'first',None),(b,'second',None)])
            with patch.object(r,'AACSessionManager',return_value=mgr),patch.object(r,'_prepare_agent_and_message',build):
                first=asyncio.create_task(r.send_message('s',req,auth))
                await entered.wait()
                try:
                    with self.assertRaises(HTTPException) as error:
                        await second_endpoint('s',req,auth)
                    self.assertEqual(error.exception.status_code,409)
                    self.assertEqual(build.await_count,1)
                finally:
                    release.set();await first

    async def test_stream_holds_lock_until_close_and_persists(self):
        a,mgr,req,auth=self.fixture()
        async def chunks(message):
            yield 'first'
            yield 'second'
        a.chat_stream=chunks
        with patch.object(r,'AACSessionManager',return_value=mgr),patch.object(r,'_prepare_agent_and_message',AsyncMock(return_value=(a,'hello',None))):
            response=await r.send_message_stream('s',req,auth)
            await response.body_iterator.__anext__()
            with self.assertRaises(HTTPException) as error:await r.send_message('s',req,auth)
            self.assertEqual(error.exception.status_code,409)
            await response.body_iterator.aclose()
            mgr.update_conversation.assert_called_once()
            self.assertEqual((await r.send_message('s',req,auth))['response'],'done')

    async def test_failed_agent_build_releases_lock(self):
        _,mgr,req,auth=self.fixture()
        for endpoint in [r.send_message,r.send_message_stream]:
            with patch.object(r,'AACSessionManager',return_value=mgr),patch.object(r,'_prepare_agent_and_message',AsyncMock(side_effect=RuntimeError('build failed'))):
                with self.assertRaises(RuntimeError):await endpoint('s',req,auth)
            with turn_lock.TurnLock('s'):pass

    def test_process_guard_survives_mount_with_process_scoped_flock(self):
        # VirtioFS can accept a second descriptor lock in the same worker.
        with patch.object(turn_lock.fcntl, 'flock'):
            with turn_lock.TurnLock('s'):
                with self.assertRaises(HTTPException) as error:
                    turn_lock.TurnLock('s')
                self.assertEqual(error.exception.status_code, 409)
                with turn_lock.TurnLock('other'):pass
            with turn_lock.TurnLock('s'):pass

    def test_failed_file_lock_does_not_leak_process_guard(self):
        with patch.object(turn_lock.fcntl, 'flock', side_effect=OSError('failure')):
            with self.assertRaises(OSError):turn_lock.TurnLock('s')
        with turn_lock.TurnLock('s'):pass

    def test_lock_is_shared_across_worker_processes(self):
        import subprocess,sys
        script="""from pathlib import Path
import sys
from fastapi import HTTPException
from lamb.aac import turn_lock
turn_lock.LOCK_ROOT=Path(sys.argv[1])
try:
    with turn_lock.TurnLock('s'):pass
except HTTPException as error:
    assert error.status_code == 409
    assert sys.argv[2] == 'busy'
else:
    assert sys.argv[2] == 'free'
"""
        with turn_lock.TurnLock('s'):
            subprocess.run([sys.executable,'-c',script,str(turn_lock.LOCK_ROOT),'busy'],check=True)
        subprocess.run([sys.executable,'-c',script,str(turn_lock.LOCK_ROOT),'free'],check=True)
