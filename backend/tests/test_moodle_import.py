import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs
import pytest
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from tests.test_moodle_scoped_reads import responses
from lamb.aac.liteshell.shell import LiteShell,prepare_command
from lamb.moodle.documents import download_file


def test_import_destinations_and_confirmation_policy():
    from lamb.aac.authorization import ActionAuthorizer
    for suffix, expected in [('--single-file',None),('--to kb 12',12)]:
        key,_,p,_=prepare_command('moodle import file mf_example '+suffix)
        assert key=='moodle.import.file' and p['kb_id']==expected
        assert ActionAuthorizer().check(key)=='ask'
    for suffix in ('','--to kb','--to kb 1 --single-file','--single-file 12'):
        with pytest.raises(ValueError):prepare_command('moodle import file mf_example '+suffix)


@respx.mock
def test_import_ref_scope_revalidation_and_authenticated_upload(stores):
    rt=runtime(stores);_,read=responses()
    present=[True]
    item={'filename':'lesson.txt','url':'https://moodle.test/pluginfile.php/201/mod_resource/content/0/lesson.txt','filesize':8,'timemodified':1,'isdir':False}
    def respond(request):
        p=parse_qs(request.content.decode());fn=p['wsfunction'][0]
        if fn=='core_course_get_contents':
            return Response(200,json=[{'id':1,'name':'Section','modules':[{'id':21,'instance':31,'modname':'resource','contextid':201}]}])
        if fn=='core_files_get_files':return Response(200,json={'files':[item] if present[0] else []})
        return read(request)
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    fetched=respx.get('https://moodle.test/webservice/pluginfile.php/201/mod_resource/content/0/lesson.txt').mock(return_value=Response(200,content=b'Evidence',headers={'content-type':'text/plain'}))
    http=SimpleNamespace(post=AsyncMock(return_value={'path':'7/owned.txt'}))
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt,allowed_commands=rt.available());shell._http_client=http
    async def run():
        await shell.execute('moodle course get 10')
        listed=await shell.execute('moodle file list 201 --component mod_resource --filearea content')
        assert listed.success,listed.error
        ref=listed.data[0]['file_id']
        command=f'moodle import file {ref} --single-file'
        assert not (await shell.execute(command)).success
        assert not (await shell.execute('moodle import file /etc/passwd --single-file',confirmed=True)).success
        assert not fetched.calls
        result=await shell.execute(command,confirmed=True)
        assert result.success,result.error
        assert result.data=={'path':'7/owned.txt'}
        http.post.assert_awaited_with('/creator/aac/files',files={'file':('lesson.txt',b'Evidence','text/plain')})
        result=await shell.execute(f'moodle import file {ref} --to kb 12',confirmed=True)
        assert result.success,result.error
        http.post.assert_awaited_with('/creator/knowledgebases/kb/12/files',files={'files':('lesson.txt',b'Evidence','text/plain')})
        present[0]=False
        assert not (await shell.execute(command,confirmed=True)).success
        assert len(fetched.calls)==2
    asyncio.run(run())
    assert fetched.calls[0].request.url.params['token']=='fixture'


@respx.mock
def test_download_rejects_external_urls_redirects_and_oversize_without_token_leak():
    item={'filename':'lesson.txt','url':'https://other.test/pluginfile.php/1/file','filesize':1}
    with pytest.raises(PermissionError):download_file('https://moodle.test','secret-token',item,single_file=True)
    assert not respx.calls
    item['url']='https://moodle.test/pluginfile.php/1/file'
    route=respx.get('https://moodle.test/webservice/pluginfile.php/1/file').mock(return_value=Response(302,headers={'location':'https://other.test'}))
    with pytest.raises(ValueError) as exc:download_file('https://moodle.test','secret-token',item,single_file=True)
    assert 'secret-token' not in str(exc.value) and len(respx.calls)==1
    item['filesize']=11*1024*1024
    with pytest.raises(ValueError):download_file('https://moodle.test','secret-token',item,single_file=True)
    assert len(route.calls)==1


def test_single_file_import_uses_real_owned_upload_route(tmp_path,monkeypatch):
    from fastapi import FastAPI
    import httpx
    from lamb.aac.router import router
    from lamb.auth_context import get_auth_context
    from lamb.aac.liteshell.http_client import AsyncLambClient
    from lamb.moodle.documents import Download
    from lamb import uploaded_files
    from lamb.aac import files
    monkeypatch.setattr(files,'ROOT',tmp_path)
    monkeypatch.setattr(uploaded_files,'ROOT',tmp_path)
    app=FastAPI();app.include_router(router,prefix='/creator')
    app.dependency_overrides[get_auth_context]=lambda:SimpleNamespace(user={'id':7})
    async def run():
        client=AsyncLambClient.__new__(AsyncLambClient)
        client._client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test')
        source=SimpleNamespace(execute=lambda *args,**kwargs:Download('lesson.txt',b'Evidence','text/plain'))
        shell=LiteShell('','','fixture',1,user_id=7,moodle=source);shell._http_client=client
        try:
            result=await shell.execute('moodle import file mf_fixture --single-file',confirmed=True)
            assert result.success,result.error
            reference=result.data['path']
            assert uploaded_files.owned_document(reference,7).read_bytes()==b'Evidence'
            with pytest.raises(ValueError):uploaded_files.owned_document(reference,8)
        finally:await shell.close()
    asyncio.run(run())
