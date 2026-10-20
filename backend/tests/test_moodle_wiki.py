import asyncio
from urllib.parse import parse_qs
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from tests.test_moodle_scoped_reads import responses
from lamb.aac.liteshell.shell import LiteShell


def test_wiki_reference_uses_activity_id_not_subwiki_id():
    from lamb.moodle.contract import prepare_moodle
    spec,params=prepare_moodle('moodle wiki pages 50')
    assert params=={'wiki_id':50}
    assert 'WIKI_ID' in spec.reference() and 'SUBWIKI_ID' not in spec.reference()


@respx.mock
def test_wiki_parameter_compatibility_and_page_lineage(stores):
    rt=runtime(stores);calls,read=responses();wiki_calls=[];pages=[{'id':55,'title':'Start'}]
    def respond(request):
        p=parse_qs(request.content.decode());fn=p['wsfunction'][0]
        if fn.startswith('mod_wiki_'):
            wiki_calls.append((fn,p))
            if fn=='mod_wiki_get_subwiki_pages':
                assert p['wikiid']==['50'] and 'subwikiid' not in p
                return Response(200,json={'pages':pages})
            assert fn=='mod_wiki_get_page_contents'
            return Response(200,json={'page':{'id':55,'cachedcontent':'Fixture wiki'}})
        if fn=='core_course_get_contents':
            return Response(200,json=[{'id':1,'name':'Section','modules':[{'id':500,'modname':'wiki','instance':50}]}])
        return read(request)
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    async def run():
        assert (await shell.execute('moodle course get 10')).success
        assert not (await shell.execute('moodle wiki page 55')).success
        assert not (await shell.execute('moodle wiki pages 999')).success
        assert not wiki_calls
        result=await shell.execute('moodle wiki pages 50')
        assert result.success,result.error
        result=await shell.execute('moodle wiki page 55')
        assert result.success,result.error
        assert result.data['cachedcontent']=='Fixture wiki'
        assert not (await shell.execute('moodle wiki page 999')).success
        pages.clear()
        assert not (await shell.execute('moodle wiki page 55')).success
    asyncio.run(run())
    assert sum(fn=='mod_wiki_get_page_contents' for fn,_ in wiki_calls)==1
