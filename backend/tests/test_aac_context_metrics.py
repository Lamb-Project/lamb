"""Context telemetry must observe without changing history or tool semantics."""
import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

import httpx
from openai import BadRequestError, RateLimitError
from lamb.aac.context_metrics import ContextSizeError, is_context_rejection, request_sizes, usage_counts
from lamb.aac.context_report import summarize
from lamb.aac.session_logger import SessionLogger
from tests.test_aac_legacy import agent, message, tool, turn, FakeStream
from tests import test_aac_router as router_tests
from lamb.aac import router as r


def rejection(code='context_length_exceeded', text='private prompt must never appear'):
    return BadRequestError(text, response=httpx.Response(400, request=httpx.Request('POST','http://fixture/v1/chat/completions')),
                           body={'error': {'code': code, 'message': text}})


class Measurements(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.dict('os.environ', {'AAC_LOG_PATH': self.temp.name, 'AAC_SESSION_LOGGING': 'true'})
        patcher.start(); self.addCleanup(patcher.stop)
        self.log = SessionLogger('synthetic-session', 'fixture@example.invalid', 1)

    def events(self, name):
        return [json.loads(line)['data'] for line in Path(self.log.log_path).read_text().splitlines() if json.loads(line)['event'] == name]

    async def test_usage_only_final_chunk_and_nonstream_usage(self):
        usage={'prompt_tokens':123, 'completion_tokens':5, 'total_tokens':128,
               'prompt_tokens_details':{'cached_tokens':100},'completion_tokens_details':{'reasoning_tokens':2}}
        for streaming in (False, True):
            a,p,s=agent([],session_logger=self.log)
            class UsageStream(FakeStream):
                async def __aiter__(self):
                    async for chunk in super().__aiter__(): yield chunk
                    yield N(choices=[], usage=usage)
            stream=UsageStream(message('Hola'))
            p.chat.completions.create=AsyncMock(return_value=stream if streaming else N(choices=[N(message=message('Hola'))],usage=usage))
            self.assertEqual(await turn(a,streaming), 'Hola')
            kwargs=p.chat.completions.create.call_args.kwargs
            self.assertEqual(kwargs.get('stream_options'), {'include_usage':True} if streaming else None)
            self.assertEqual(self.events('context_response')[-1]['usage']['cached_tokens'],100)
            self.assertEqual(self.events('context_response')[-1]['outcome'],'completed')
            self.assertEqual(self.events('context_request')[-1]['message_count'],2)

    async def test_tool_round_cap_and_history_unchanged_with_logging(self):
        for streaming in (False,True):
            setup=[message(tools=[tool('lamb assistant list')]), message('Done')]
            a,p,s=agent(copy.deepcopy(setup),session_logger=self.log,max_tool_rounds=1)
            b,q,t=agent(copy.deepcopy(setup),max_tool_rounds=1)
            await turn(a,streaming); await turn(b,streaming)
            self.assertEqual(a.conversation,b.conversation)
            self.assertEqual(p.calls,q.calls)
            observation=self.events('context_request')[-1]
            self.assertEqual(observation['tool_results'][0]['command'],'assistant.list')
            self.assertEqual(observation['tool_result_content_bytes'],len(a.conversation[2]['content'].encode()))
            self.assertTrue(self.events('context_turn')[-1]['round_limit_reached'])

    async def test_context_rejection_does_not_retry_or_repeat_tools(self):
        for streaming in (False,True):
            a,p,s=agent([message(tools=[tool()]), rejection()], session_logger=self.log)
            a.skill_state={'ui_language':'es'}
            with self.assertRaisesRegex(ContextSizeError,'Nueva conversación'):
                await turn(a,streaming)
            self.assertEqual(s.execute.await_count,1)
            self.assertEqual(len(p.calls),2)
            self.assertEqual(self.events('context_response')[-1]['outcome'],'context_rejected')
            self.assertIsNone(self.events('context_response')[-1]['usage'])
            self.assertNotIn('private prompt',json.dumps(self.events('context_response')))
            self.assertEqual(a.conversation[-1]['role'],'tool')

    async def test_interrupted_usage_is_unknown_and_stream_is_closed(self):
        a,p,s=agent([message('Partial')],session_logger=self.log,max_tool_rounds=0)
        stream=a.chat_stream('hi')
        await anext(stream)
        self.assertIn('tool-round limit', await anext(stream))
        self.assertEqual((await anext(stream))['status'], 'thinking')
        await anext(stream)
        await stream.aclose()
        self.assertTrue(p.streams[0].closed)
        self.assertEqual(self.events('context_response')[-1]['outcome'],'interrupted')
        self.assertIsNone(self.events('context_response')[-1]['usage'])
        self.assertEqual(self.events('context_turn')[-1]['outcome'],'interrupted')

    async def test_report_deduplicates_repeated_history_and_copied_logs(self):
        a,p,s=agent([message(tools=[tool()]),message('ok'),message('again')],session_logger=self.log)
        await turn(a,True);await turn(a,True)
        report=summarize([Path(self.log.log_path),Path(self.log.log_path)])
        self.assertEqual(report['requests'],3)
        self.assertEqual(report['tool_result_content_bytes_by_command']['assistant.list']['count'],1)
        self.assertEqual(report['requests_without_prompt_usage'],3)
        self.assertEqual(report['sessions_measured'],1)
        self.assertEqual(report['turns'],2)

    async def test_disabled_logging_creates_no_files(self):
        with patch.dict('os.environ', {'AAC_SESSION_LOGGING':'false'}):
            a,p,s=agent([message('ok')],session_logger=SessionLogger('off','nobody',1))
            self.assertEqual(await turn(a,True),'ok')
        self.assertEqual(list(Path(self.temp.name).rglob('*.jsonl')),[])


class Sizes(unittest.TestCase):
    def test_unicode_and_command_arguments_are_not_logged(self):
        call=tool('lamb kb query 25 "sensitive learner text"')
        messages=[{'role':'system','content':'ñ🙂'}, {'role':'assistant','tool_calls':[{'id':call.id,'function':vars(call.function)}]},
                  {'role':'tool','tool_call_id':call.id,'content':'秘密🙂'}]
        original=copy.deepcopy(messages)
        sizes=request_sizes({'messages':messages,'tools':[{'private':'schema'}]})
        self.assertEqual(sizes['system_prompt_bytes'],6)
        self.assertEqual(sizes['tool_result_content_bytes'],10)
        self.assertEqual(sizes['tool_results'][0]['command'],'kb.query')
        self.assertNotIn('sensitive', json.dumps(sizes))
        self.assertNotIn('秘密', json.dumps(sizes))
        self.assertEqual(messages,original)

    def test_only_known_context_failures_are_relabelled(self):
        self.assertTrue(is_context_rejection(rejection()))
        for text in ['maximum context length is 1000 tokens', 'input is too long', 'request exceeds the available context size']:
            self.assertTrue(is_context_rejection(rejection(None,text)))
        self.assertFalse(is_context_rejection(rejection('content_filter','content rejected')))
        self.assertFalse(is_context_rejection(ValueError('maximum context length')))
        error=RateLimitError('too many tokens',response=httpx.Response(429,request=httpx.Request('POST','http://fixture')),body={'code':'context_length_exceeded'})
        self.assertFalse(is_context_rejection(error))
        self.assertIsNone(usage_counts(None))
        self.assertEqual(usage_counts({'prompt_tokens':0})['prompt_tokens'],0)
        self.assertIsNone(usage_counts({'prompt_tokens':-1}))


class ContextRoutes(unittest.IsolatedAsyncioTestCase):
    setUp=router_tests.LifecycleTests.setUp
    fixture=router_tests.LifecycleTests.fixture
    async def test_both_routes_show_recovery_and_preserve_history(self):
        for streaming in (False,True):
            a,mgr,req,auth=self.fixture()
            a.chat.side_effect=ContextSizeError({'ui_language':'es'})
            async def chunks(_):
                raise ContextSizeError({'ui_language':'es'})
                yield
            a.chat_stream=chunks
            with patch.object(r,'AACSessionManager',return_value=mgr),patch.object(r,'_prepare_agent_and_message',AsyncMock(return_value=(a,'hello',None))):
                if streaming:
                    response=await r.send_message_stream('s',req,auth)
                    output=''.join([x async for x in response.body_iterator])
                    events=[json.loads(line[6:]) for line in output.splitlines() if line.startswith('data: {')]
                    failure=next(e for e in events if 'error' in e)
                    self.assertEqual(failure['code'],'context_length_exceeded')
                    self.assertEqual(failure['recovery'],'new_conversation')
                    self.assertIn('Nueva conversación',failure['error'])
                    self.assertIn('[DONE]',output)
                else:
                    with self.assertRaises(r.HTTPException) as error: await r.send_message('s',req,auth)
                    self.assertEqual(error.exception.status_code,413)
                    self.assertIn('Nueva conversación',error.exception.detail)
            mgr.update_conversation.assert_called_once()
            a.shell.close.assert_awaited_once();a.llm_client.close.assert_awaited_once()
