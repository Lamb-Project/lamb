import asyncio
from urllib.parse import parse_qs
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from tests.test_moodle_scoped_reads import responses
from tests.test_aac_legacy import agent, tool
from lamb.aac.liteshell.shell import LiteShell, prepare_command
from lamb.aac.language import confirmation_fallback

COMMAND='moodle assign grade --assignment-id 40 --user-id 80 --grade 75 --feedback "Add a source" --rationale "Claim needs evidence"'


@respx.mock
def test_grade_review_confirmation_policy_and_stale_submission(stores):
    rt=runtime(stores);calls,read=responses();writes=[]
    submission={'id':1,'userid':80,'status':'submitted','timemodified':100,'plugins':[{'type':'onlinetext','editorfields':[{'text':'Learner explanation'}]}]}
    def respond(request):
        p=parse_qs(request.content.decode());fn=p['wsfunction'][0]
        if fn=='mod_assign_get_submission_status':
            return Response(200,json={'lastattempt':{'submission':submission}})
        if fn=='mod_assign_save_grade':
            writes.append(p);return Response(200,content="null")
        return read(request)
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt)
    a,_,_=agent([]);a.shell=shell
    async def run():
        assert not (await shell.execute(COMMAND,confirmed=True)).success
        rt.store.configure({'enabled':True,'base_url':'https://moodle.test','mode':'full','allow_grade_write':True})
        assert 'moodle.assign.grade' in rt.available()
        assert 'moodle.forum.post' not in rt.available()
        assert (await shell.execute('moodle course get 10')).success
        assert not (await shell.execute(COMMAND,confirmed=True)).success
        denied=await a._execute_tool(tool(COMMAND.replace('--user-id 80','--user-id 999')))
        assert not denied['success'] and not a.pending_action
        result=await a._execute_tool(tool(COMMAND))
        assert result.get('awaiting_user_confirmation'),result
        rendered=confirmation_fallback(a)
        assert 'Learner explanation' in rendered and 'Claim needs evidence' in rendered
        assert not writes
        submission['timemodified']=101
        await a._resolve_pending_action('yes')
        assert not writes
        assert not shell.history[-1].success
        assert (await a._execute_tool(tool(COMMAND))).get('awaiting_user_confirmation')
        await a._resolve_pending_action('yes')
        assert shell.history[-1].success,shell.history[-1].error
        assert shell.history[-1].data['rationale']=='Claim needs evidence'
        assert len(writes)==1 and writes[0]['applytoall']==['0']
        assert any(event['success'] and 'Claim needs evidence' in event['command'] for event in a.tool_audit)
        assert (await a._execute_tool(tool(COMMAND))).get('awaiting_user_confirmation')
        rt.store.configure({'enabled':True,'base_url':'https://moodle.test','mode':'readonly','allow_grade_write':True})
        await a._resolve_pending_action('yes')
        assert not shell.history[-1].success and len(writes)==1
    asyncio.run(run())


def test_grade_requires_rationale_in_contract():
    import pytest
    with pytest.raises(ValueError):
        prepare_command('moodle assign grade --assignment-id 40 --user-id 80 --grade 75')
