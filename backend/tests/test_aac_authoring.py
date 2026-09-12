"""Authoring contract tests: no provider or database writes."""
import io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock,patch
from fastapi import UploadFile,HTTPException
from lamb.aac import files
from lamb.aac.router import attach_file,validate_file
from lamb.aac.liteshell.shell import LiteShell
from lamb.aac.authorization import ActionAuthorizer

class Authoring(unittest.IsolatedAsyncioTestCase):
    def shell(self):
        s=LiteShell(server_url='unused',token='fake',user_email='owner@test',organization_id=1,user_id=7)
        s._http_client=N(get=AsyncMock(return_value={}),post=AsyncMock(return_value={}),put=AsyncMock(return_value={}))
        return s,s._http_client

    async def test_new_write_policies(self):
        a=ActionAuthorizer()
        for name in ['kb.create','kb.upload','rubric.create','rubric.update']:self.assertEqual(a.check(name),'ask')
        for name in ['kb.query','test.evaluations']:self.assertEqual(a.check(name),'auto')

    async def test_kb_create_query_evaluations(self):
        s,h=self.shell()
        self.assertTrue((await s.execute('lamb kb create "My KB" --description "A source"')).success)
        self.assertEqual(h.post.call_args.kwargs['json'],{'name':'My KB','description':'A source'})
        self.assertTrue((await s.execute('lamb kb query 3 "català fact" --top-k 4 --threshold 0.2')).success)
        self.assertEqual(h.post.call_args.kwargs['json']['plugin_params'],{'top_k':4,'threshold':0.2})
        self.assertTrue((await s.execute('lamb test evaluations 3')).success)
        self.assertEqual(h.get.call_args.args[0],'/creator/assistant/3/tests/evaluations')
        for command in ['kb query 3 x --top-k 0','kb query 3 x --threshold nan','kb create x --unknown y','rubric create x --criteria null','rubric create x --criteria []']:
            h.post.reset_mock();self.assertFalse((await s.execute('lamb '+command)).success);h.post.assert_not_awaited()

    async def test_rubric_edit_preserves_fields(self):
        s,h=self.shell();criteria=[{'name':'Clarity','weight':100,'levels':[{'score':1}]}]
        h.get.return_value={'rubric_data':{'title':'Old','description':'Keep','criteria':criteria,'maxScore':7,'scoringType':'points','metadata':{'subject':'Logic','gradeLevel':'Year 1'}}}
        r=await s.execute('lamb rubric update r1 --title "New"');self.assertTrue(r.success,r.error)
        form=h.put.call_args.kwargs['data'];self.assertEqual(form['title'],'New');self.assertEqual(form['description'],'Keep');self.assertEqual(form['maxScore'],7);self.assertEqual(json.loads(form['criteria']),criteria);self.assertEqual(form['subject'],'Logic')

    async def test_attachment_bytes_limits_and_ownership(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(files,'ROOT',Path(temp)):
            auth=N(user={'id':7})
            result=await attach_file(UploadFile(io.BytesIO('Sí source'.encode()),filename='../../source.md'),auth)
            self.assertEqual(files.owned_file(result['path'],7).read_text(),'Sí source')
            await validate_file(result['path'],auth)
            for reference,uid in [(result['path'],8),('../secret',7),('/etc/passwd',7),('7/../../secret',7),('7/missing',7)]:
                with self.assertRaises(ValueError):files.owned_file(reference,uid)
            for name,body,status in [('a.exe',b'x',400),('a.txt',b'',413),('a.txt',b'\xff',400)]:
                with self.assertRaises(HTTPException) as e:await attach_file(UploadFile(io.BytesIO(body),filename=name),auth)
                self.assertEqual(e.exception.status_code,status)
            with patch.object(files,'MAX_BYTES',2):
                with self.assertRaises(HTTPException):await attach_file(UploadFile(io.BytesIO(b'abc'),filename='a.txt'),auth)
            target=Path(temp)/'7'/'linked.md';target.symlink_to(files.owned_file(result['path'],7))
            with self.assertRaises(ValueError):files.owned_file('7/linked.md',7)

    async def test_upload_uses_owned_bytes_and_propagates_failure(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(files,'ROOT',Path(temp)):
            (Path(temp)/'7').mkdir();(Path(temp)/'7'/'doc.pdf').write_bytes(b'%PDF-test')
            s,h=self.shell()
            async def post(path,**kw):
                self.assertEqual(kw['files']['file'][1].read(),b'%PDF-test')
                self.assertEqual(kw['data']['plugin_name'],'markitdown_ingest')
                return {'job_id':'j1'}
            h.post.side_effect=post
            result=await s.execute('lamb kb upload 3 7/doc.pdf');self.assertTrue(result.success);self.assertTrue(result.data['verification_required'])
            h.post.side_effect=ValueError('API error (403)')
            self.assertFalse((await s.execute('lamb kb upload 3 7/doc.pdf')).success)
            with self.assertRaises(HTTPException):await validate_file('7/doc.pdf',N(user={'id':7}))

    async def test_file_binding_requires_validation(self):
        s,h=self.shell();h.get.side_effect=ValueError('Not owned')
        r=await s.execute('lamb assistant create x --file-path 8/private.md');self.assertFalse(r.success);h.post.assert_not_awaited()

    async def test_chat_persistence_and_ingestion_readback(self):
        s,h=self.shell()
        h.post.return_value={'choices':[{'message':{'content':'Answer'}}], 'chat_id':'saved-chat'}
        r=await s.execute('lamb assistant chat 3 --message hello --persist --chat-id saved-chat')
        self.assertTrue(r.success,r.error)
        self.assertTrue(h.post.call_args.kwargs['json']['persist_chat'])
        self.assertEqual(h.post.call_args.kwargs['json']['chat_id'],'saved-chat')
        self.assertEqual(r.data['chat_id'],'saved-chat')
        await s.execute('lamb assistant chat 3 --message hello')
        self.assertFalse(h.post.call_args.kwargs['json']['persist_chat'])
        for command,endpoint in [('jobs','ingestion-jobs'),('status','ingestion-status')]:
            r=await s.execute('lamb kb '+command+' 3')
            self.assertTrue(r.success,r.error)
            self.assertEqual(h.get.call_args.args[0],'/creator/knowledgebases/kb/3/'+endpoint)

    async def test_expected_behavior_sent_with_approved_scenario(self):
        s,h=self.shell()
        r=await s.execute('lamb test add 3 "Station code" --message "What code?" --expected "COBALT-742, not a guessed code" --type single_turn')
        self.assertTrue(r.success,r.error)
        body=h.post.call_args.kwargs['json']
        self.assertEqual(body['expected_behavior'],'COBALT-742, not a guessed code')
        self.assertEqual(body['message'],'What code?')
        self.assertEqual(body['title'],'Station code')
