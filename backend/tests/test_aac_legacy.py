"""Legacy AAC behavioural regressions for #469. No network or database required."""
import asyncio
import json
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock

import httpx
from lamb.aac.agent.loop import AgentLoop
from lamb.aac.authorization import ActionAuthorizer, classify_user_confirmation
from lamb.aac.liteshell.shell import LiteShell, ShellResult, COMMAND_CONTRACTS, _parse_args
from lamb.aac.liteshell.commands import COMMAND_REGISTRY
from lamb.aac.liteshell.http_client import AsyncLambClient


def tool(command='lamb assistant list', name='execute_command', raw=None, ident='call-1'):
    return N(id=ident, function=N(name=name, arguments=raw if raw is not None else json.dumps({'command':command})))


def message(text='', tools=()):
    return N(content=text, tool_calls=list(tools))


class FakeStream:
    def __init__(self, msg, error=None):
        self.msg, self.error, self.closed = msg, error, False
    async def __aiter__(self):
        yield N(choices=[])  # provider usage/heartbeat chunk
        for part in [self.msg.content[:2], self.msg.content[2:]]:
            if part:
                yield N(choices=[N(delta=N(content=part, tool_calls=None))])
        for i, call in enumerate(self.msg.tool_calls):
            args = call.function.arguments
            for j, fragment in enumerate([args[:3],args[3:]]):
                yield N(choices=[N(delta=N(content=None,tool_calls=[N(index=i,
                    id=call.id if j==0 else None,
                    function=N(name=call.function.name if j==0 else None,arguments=fragment))]))])
        if self.error:
            raise self.error
    async def close(self):
        self.closed = True


class Provider:
    def __init__(self, messages):
        self.responses = list(messages)
        self.calls, self.streams = [], []
        self.chat = N(completions=N(create=self.create))
    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError('Unexpected extra provider request')
        msg = self.responses.pop(0)
        if isinstance(msg, BaseException):
            raise msg
        if kwargs.get('stream'):
            stream = FakeStream(msg)
            self.streams.append(stream)
            return stream
        return N(choices=[N(message=msg)])


def agent(messages, **kwargs):
    shell = N(execute=AsyncMock(return_value=ShellResult(True, data={'ok':True})), history=[])
    provider = Provider(messages)
    return AgentLoop(shell=shell,llm_client=provider,model='fake',**kwargs), provider, shell


async def turn(a, streaming, text='hello'):
    if not streaming:
        return await a.chat(text)
    events = [e async for e in a.chat_stream(text)]
    return ''.join(e for e in events if isinstance(e,str))


class LoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_single_request_and_transcript(self):
        for streaming in [False, True]:
            for text in ['', 'Hello', 'Sí, informació en català', '第一步']:
                with self.subTest(streaming=streaming,text=text):
                    a,p,s=agent([message(text)])
                    self.assertEqual(await turn(a,streaming),text)
                    self.assertEqual(len(p.calls),1)
                    self.assertEqual(a.conversation[-1],{'role':'assistant','content':text})
                    s.execute.assert_not_awaited()
                    self.assertTrue(all(x.closed for x in p.streams))

    async def test_round_cap_is_enforced_and_tools_removed(self):
        for streaming in [False,True]:
            for cap in [0,1,2]:
                with self.subTest(streaming=streaming,cap=cap):
                    a,p,s=agent([*[message(tools=[tool(ident=f't{i}')]) for i in range(cap)],message('done')],max_tool_rounds=cap)
                    self.assertEqual(await turn(a,streaming),'done')
                    self.assertEqual(s.execute.await_count,cap)
                    self.assertNotIn('tools',p.calls[-1])
                    self.assertEqual(len(p.calls),cap+1)

    async def test_provider_ignoring_cap_cannot_execute(self):
        for streaming in [False,True]:
            a,p,s=agent([message(tools=[tool()])],max_tool_rounds=0)
            self.assertIn('No further tools',await turn(a,streaming))
            s.execute.assert_not_awaited()
            self.assertFalse(any('tool_calls' in m for m in a.conversation))

    async def test_fragmented_parallel_read_tools(self):
        for streaming in [False,True]:
            calls=[tool(ident='a'),tool('lamb kb list',ident='b')]
            a,p,s=agent([message(tools=calls),message('done')])
            await turn(a,streaming)
            self.assertEqual(s.execute.await_count,2)
            self.assertEqual([x['tool_call_id'] for x in a.conversation if x['role']=='tool'],['a','b'])

    async def test_multiple_writes_keep_first_pending_action(self):
        for streaming in [False,True]:
            a,p,s=agent([message(tools=[tool('lamb assistant create one',ident='a'),tool('lamb assistant create two',ident='b')]),message('Approve?')])
            await turn(a,streaming)
            self.assertEqual(a.pending_action['command'],'lamb assistant create one')
            self.assertEqual(len([x for x in a.conversation if x['role']=='tool']),2)
            self.assertNotIn('tools',p.calls[-1])
            s.execute.assert_not_awaited()

    async def test_confirmation_languages_execute_once(self):
        for text in ['yes','sí','endavant','bai']:
            for streaming in [False,True]:
                with self.subTest(text=text,streaming=streaming):
                    a,p,s=agent([message('done'),message('nothing pending')],pending_action={'command':'lamb assistant create x','action_key':'assistant.create'})
                    await turn(a,streaming,text)
                    await turn(a,streaming,text)
                    self.assertEqual(s.execute.await_count,1)
                    self.assertIsNone(a.pending_action)
                    self.assertEqual(len(a.tool_audit),1)

    async def test_rejection_and_ambiguity(self):
        for text in ['no','cancel·la','ez','tell me more','yes no']:
            a,p,s=agent([message('reply')],pending_action={'command':'lamb assistant create x'})
            await turn(a,True,text)
            s.execute.assert_not_awaited()
            self.assertEqual(a.pending_action is None,classify_user_confirmation(text)=='reject')

    async def test_never_policy(self):
        a,p,s=agent([],authorizer=ActionAuthorizer({'assistant.delete':'never'}))
        result=await a._execute_tool(tool('lamb assistant delete 1'))
        self.assertFalse(result['success']);s.execute.assert_not_awaited()

    async def test_malformed_and_unknown_tools(self):
        for raw in ['not-json','[]','null','123','{"command":12}','{"command":""}']:
            a,p,s=agent([])
            result=await a._execute_tool(tool(raw=raw))
            self.assertFalse(result['success']);s.execute.assert_not_awaited()
        a,p,s=agent([])
        self.assertFalse((await a._execute_tool(tool(name='other')))['success'])

    async def test_errors_and_cancellation_propagate(self):
        for streaming in [False,True]:
            for exc in [RuntimeError('provider unavailable'), asyncio.CancelledError()]:
                a,p,s=agent([exc])
                with self.assertRaises(type(exc)): await turn(a,streaming)
                self.assertFalse(any(x['role']=='assistant' for x in a.conversation))

    async def test_stream_closed_on_error_and_cancel(self):
        for exc in [RuntimeError('broken stream'),asyncio.CancelledError()]:
            stream=FakeStream(message('partial'),error=exc)
            a,p,s=agent([])
            p.chat.completions.create=AsyncMock(return_value=stream)
            with self.assertRaises(type(exc)): await turn(a,True)
            self.assertTrue(stream.closed)

    async def test_failed_approved_command_recorded(self):
        a,p,s=agent([message('failed')],pending_action={'command':'lamb assistant update 1','action_key':'assistant.update'})
        s.execute.return_value=ShellResult(False,error='403 forbidden')
        await turn(a,False,'yes')
        self.assertIsNone(a.pending_action)
        self.assertFalse(a.tool_audit[-1]['success'])
        self.assertIn('403 forbidden',str(a.conversation))

    async def test_skill_startup_does_not_bypass_policy(self):
        a,p,s=agent([])
        s.execute.return_value=ShellResult(True,data={'name':'test','prompt':'text','startup_actions':['lamb assistant delete 1']})
        result=await a._execute_tool(tool('lamb skill load test'))
        self.assertIn('Startup skipped',result['data'])
        self.assertEqual(s.execute.await_count,1)


class ShellTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.http=N(get=AsyncMock(return_value={'data':[]}),post=AsyncMock(return_value={'id':1}),
                    put=AsyncMock(return_value={'id':1}),delete=AsyncMock(return_value={}))
        self.shell=LiteShell('http://unused','private-token','test@example.test',1,_http_client=self.http)

    async def test_every_registered_command_has_contract(self):
        self.assertEqual(set(COMMAND_REGISTRY),set(COMMAND_CONTRACTS))
        for key in COMMAND_REGISTRY:
            result=await self.shell.execute('lamb '+key.replace('.',' ')+' --help')
            self.assertTrue(result.success,key)

    async def test_invalid_commands_rejected_without_http(self):
        for cmd in ['', 'lamb', 'unknown', 'lamb assistant missing', 'lamb assistant get',
                    'lamb assistant get 1 extra', 'lamb assistant create "broken',
                    'lamb assistant create x --typo value', 'lamb assistant create x --llm',
                    'lamb assistant list -o table', 'lamb assistant create x --rag-top-k=-1',
                    'lamb assistant chat 1 --message hi --bypass=garbage']:
            with self.subTest(cmd=cmd): self.assertFalse((await self.shell.execute(cmd)).success)
        self.http.get.assert_not_awaited();self.http.post.assert_not_awaited()

    async def test_quoted_unicode_and_empty_update(self):
        self.http.get.return_value={'name':'old','description':'old','system_prompt':'keep','metadata':'{"connector":"openai","other":123}'}
        r=await self.shell.execute('lamb assistant update 1 --description="" --system-prompt "It\'s català 中文" -o json')
        self.assertTrue(r.success)
        body=self.http.put.call_args.kwargs['json']
        self.assertEqual(body['description'],'')
        self.assertEqual(body['system_prompt'],"It's català 中文")
        self.assertEqual(json.loads(body['metadata'])['other'],123)
        self.assertEqual(body['name'],'old')

    async def test_short_prompt_alias(self):
        result=await self.shell.execute('lamb assistant create x -s "some prompt"')
        self.assertTrue(result.success)
        self.assertEqual(self.http.post.call_args.kwargs['json']['system_prompt'],'some prompt')

    async def test_empty_allowlist_denies_all(self):
        self.shell.allowlist=set()
        self.assertFalse((await self.shell.execute('lamb assistant list')).success)

    async def test_help_does_not_initialize_http(self):
        shell=LiteShell('unused','token','email',1)
        self.assertTrue((await shell.execute('lamb help')).success)
        self.assertIsNone(shell._http_client)

    async def test_analytics_filters_paths_and_policy(self):
        self.http.get.return_value={'chats':[{'id':'a'}]}
        r=await self.shell.execute('lamb analytics chats 12 --page 2 --per-page 5 --search "hello world" --start-date 2026-01-01 --end-date 2026-12-31 --user-id u')
        self.assertEqual(r.data,[{'id':'a'}])
        self.assertEqual(self.http.get.call_args.args[0],'/creator/analytics/assistant/12/chats')
        self.assertEqual(self.http.get.call_args.kwargs['params'],{'page':2,'per_page':5,'search_content':'hello world','start_date':'2026-01-01','end_date':'2026-12-31','user_id':'u'})
        for key,args in [('stats','12'),('timeline','12 --period week'),('chat-detail','12 chat-a')]:
            self.assertTrue((await self.shell.execute(f'lamb analytics {key} {args}')).success)
            self.assertEqual(ActionAuthorizer().check('analytics.'+key),'auto')
        for extra in ['--page 0','--page nope']:
            self.assertFalse((await self.shell.execute('lamb analytics chats 12 '+extra)).success)
        self.assertFalse((await self.shell.execute('lamb analytics timeline 12 --period year')).success)

    async def test_api_denials_are_not_success(self):
        for error in ['API error (401)','API error (403)','API error (404)','API error (500)','Request timed out']:
            self.http.get.side_effect=ValueError(error)
            result=await self.shell.execute('lamb analytics stats 1')
            self.assertFalse(result.success);self.assertIn(error,result.error)

    def test_parser_forms(self):
        self.assertEqual(_parse_args(['1','--description=','-s','text','--bypass']),
                         (['1'],{'description':'','s':'text','bypass':True}))


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_response_and_error_contract(self):
        c=object.__new__(AsyncLambClient)
        for status,body,expected in [(200,{'data':[1]},{'data':[1]}),(204,None,{}),(200,'plain','plain')]:
            response=httpx.Response(status, json=body) if isinstance(body,dict) else httpx.Response(status,text=body or '')
            self.assertEqual(c._handle_response(response),expected)
        for status in [400,401,403,404,409,422,500,503]:
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,str(status)):
                c._handle_response(httpx.Response(status,json={'detail':'denied'}))
        with self.assertRaises(ValueError):
            c._handle_response(httpx.Response(500,text='bad gateway'))

    async def test_request_forwarding_and_timeout(self):
        c=object.__new__(AsyncLambClient)
        client=N(request=AsyncMock(return_value=httpx.Response(200,json={'ok':True})))
        c._get_client=AsyncMock(return_value=client)
        self.assertEqual(await c.get('/creator/test',params={'x':1}),{'ok':True})
        client.request.assert_awaited_once_with('GET','/creator/test',params={'x':1})
        client.request.side_effect=httpx.ReadTimeout('slow')
        with self.assertRaisesRegex(ValueError,'timed out'): await c.get('/creator/test')


if __name__ == '__main__':
    unittest.main()
