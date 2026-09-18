import asyncio
from urllib.parse import parse_qs
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from tests.test_moodle_scoped_reads import responses
from lamb.aac.liteshell.shell import LiteShell

POST='moodle forum post --forum-id 20 --subject Example --message Approved'
REPLY='moodle forum reply --post-id 90 --message Approved'


def test_agent_passes_confirmation_only_after_user_approval():
    from tests.test_aac_legacy import agent
    a,_,shell=agent([])
    a.pending_action={'command':POST,'action_key':'moodle.forum.post'}
    asyncio.run(a._resolve_pending_action('no'))
    shell.execute.assert_not_awaited()
    a.pending_action={'command':POST,'action_key':'moodle.forum.post'}
    asyncio.run(a._resolve_pending_action('yes'))
    shell.execute.assert_awaited_once_with(POST,confirmed=True)


@respx.mock
def test_forum_requires_policy_confirmation_and_owned_target(stores):
    rt=runtime(stores)
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt)
    assert not asyncio.run(shell.execute(POST,confirmed=True)).success
    assert not respx.calls
    rt.store.configure({'enabled':True,'base_url':'https://moodle.test','mode':'full','write_groups':['forum']})
    assert 'moodle.forum.post' in rt.available()
    assert not asyncio.run(shell.execute(POST)).success
    assert not respx.calls
    calls,read=responses();writes=[]
    def respond(request):
        params=parse_qs(request.content.decode());fn=params['wsfunction'][0]
        if fn.startswith('mod_forum_add_'):
            writes.append((fn,params))
            return Response(200,json={'discussionid':31,'postid':91})
        return read(request)
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    async def run():
        assert (await shell.execute('moodle course get 10')).success
        for command in (POST.replace('20','999'),REPLY.replace('90','999')):
            assert not (await shell.execute(command,confirmed=True)).success
        assert not writes
        result=await shell.execute(POST,confirmed=True)
        assert result.success,result.error
        assert result.data['discussion_id']==31
        result=await shell.execute(REPLY,confirmed=True)
        assert result.success,result.error
        assert result.data['post_id']==91
    asyncio.run(run())
    assert len(writes)==2
    assert writes[1][1]['postid']==['90']
    rt.store.configure({'enabled':True,'base_url':'https://moodle.test'})
    assert not asyncio.run(shell.execute(REPLY,confirmed=True)).success
    assert len(writes)==2


@respx.mock
def test_disconnect_during_scope_verification_prevents_write(stores):
    rt=runtime(stores)
    rt.store.configure({'enabled':True,'base_url':'https://moodle.test','mode':'full','write_groups':['forum']})
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt)
    calls,read=responses()
    def respond(request):
        result=read(request)
        if parse_qs(request.content.decode())['wsfunction']==['core_course_get_contents']:
            rt.store.disconnect()
        return result
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    async def run():
        assert (await shell.execute('moodle course get 10')).success
        assert not (await shell.execute(POST,confirmed=True)).success
    asyncio.run(run())
    assert not any(fn.startswith('mod_forum_add_') for fn,_ in calls)
