"""Educator request contracts, approval boundaries and error propagation."""
import asyncio
import json
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from lamb.aac.liteshell.shell import LiteShell, prepare_command
from lamb.aac.authorization import ActionAuthorizer
from tests.test_aac_legacy import agent, message, tool, turn

from pathlib import Path
CASES = json.loads((Path(__file__).parent / 'fixtures/educator_parity_requests.json').read_text())

class EducatorParity(unittest.IsolatedAsyncioTestCase):
    def shell(self):
        http=N(**{method:AsyncMock(return_value={'success':True,'rubric':{'title':'Preview'}}) for method in ['get','post','put','patch','delete']})
        return LiteShell('unused','token','owner@test',1,_http_client=http),http

    async def test_all_requests_and_denials(self):
        for command,method,path,kwargs in CASES:
            with self.subTest(command=command):
                shell,http=self.shell()
                result=await shell.execute('lamb '+command)
                self.assertTrue(result.success,result.error)
                getattr(http,method).assert_awaited_once_with(path,**kwargs)
                for code in [403,404,503]:
                    shell,http=self.shell();getattr(http,method).side_effect=ValueError(f'API error ({code}): denied')
                    result=await shell.execute('lamb '+command)
                    self.assertFalse(result.success);self.assertIn(str(code),result.error)

    async def test_new_mutations_require_exact_approval_plain_and_stream(self):
        for command,method,path,kwargs in CASES:
            key=prepare_command('lamb '+command)[0]
            if method=='get' or key in {'rubric.generate','template.export'}:continue
            self.assertEqual(ActionAuthorizer().check(key),'ask',key)
            for stream in [False,True]:
                a,p,s=agent([message(tools=[tool('lamb '+command)]),message('Confirm?')])
                await turn(a,stream)
                s.execute.assert_not_awaited();self.assertEqual(a.pending_action['command'],'lamb '+command)
                p.responses.append(message('Cancelled'));await a.chat('no')
                s.execute.assert_not_awaited();self.assertIsNone(a.pending_action)

    async def test_nonfile_ingestion_passes_actual_backend_parameters(self):
        shell,http=self.shell();http.get.return_value={'plugins':[{'name':'url_ingest','kind':'remote-ingest'}]}
        result=await shell.execute('lamb kb ingest 4 --plugin url_ingest --url https://example.com --param depth=2 --param mode=text')
        self.assertTrue(result.success,result.error)
        body=http.post.call_args.kwargs['json']
        from creator_interface.knowledges_router import BasePluginIngestRequest
        parsed=BasePluginIngestRequest(**body)
        self.assertEqual(parsed.parameters,{'url':'https://example.com','depth':'2','mode':'text'})
        http.get.return_value={'plugins':[{'name':'simple_ingest','kind':'file-ingest'}]};http.post.reset_mock()
        result=await shell.execute('lamb kb ingest 4 --plugin simple_ingest')
        self.assertFalse(result.success);self.assertIn('Hold your horses',result.error);http.post.assert_not_awaited()

    async def test_capabilities_and_multiturn_preserve_data(self):
        shell,http=self.shell();http.get.return_value={'name':'Original','metadata':json.dumps({'capabilities':{'vision':True,'custom':7},'llm':'saved'})}
        result=await shell.execute('lamb assistant update 30 --no-vision --image-generation -s "New prompt"')
        self.assertTrue(result.success,result.error)
        body=http.put.call_args.kwargs['json'];md=json.loads(body['metadata'])
        self.assertEqual(md['capabilities'],{'vision':False,'custom':7,'image_generation':True});self.assertEqual(md['llm'],'saved');self.assertEqual(body['system_prompt'],'New prompt')
        payload=[{'role':'user','content':'first'},{'role':'user','content':'second'}]
        import shlex
        result=await shell.execute('lamb test add 30 Multi --messages '+shlex.quote(json.dumps(payload))+' --type multi_turn')
        self.assertTrue(result.success,result.error);self.assertEqual(http.post.call_args.kwargs['json']['messages'],payload)

    def test_invalid_preflight(self):
        for command in ['kb share 4','kb share 4 --enable --disable','assistant update 30 --vision --no-vision',
                        'kb ingest 4','kb ingest 4 -p url_ingest --param path=/etc/passwd',
                        'test run 30 --timeout nan','test run 30 --timeout -1','test add 30 Multi --messages "{}"']:
            with self.subTest(command=command),self.assertRaises(ValueError):prepare_command('lamb '+command)

