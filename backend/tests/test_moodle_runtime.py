import asyncio
from unittest.mock import patch
from urllib.parse import parse_qs
import respx
from httpx import Response
from cryptography.fernet import Fernet
from tests.test_moodle_store import stores
from lamb.moodle.runtime import MoodleRuntime
from lamb.moodle.secrets import TokenCipher
from lamb.aac.liteshell.shell import LiteShell,prepare_command
from lamb.aac.authorization import ActionAuthorizer


def runtime(stores):
    _,store=stores;cipher=TokenCipher(Fernet.generate_key());snap=store.snapshot()
    encrypted=cipher.encrypt('fixture',organization_id=1,owner_id=7,base_url='https://moodle.test')
    store.save({'base_url':'https://moodle.test','moodle_user_id':70,'username':'demo','token_encrypted':encrypted},expected_generation=snap['generation'],expected_policy=snap['policy'])
    return MoodleRuntime(store,cipher=cipher)


@respx.mock
def test_shell_read_uses_owner_and_disconnect_revokes_open_shell(stores):
    rt=runtime(stores)
    route=respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200,json=[]))
    shell=LiteShell('', '', 'fixture@test',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    result=asyncio.run(shell.execute('moodle enrol my-courses'))
    assert result.success,result.error
    assert parse_qs(route.calls[0].request.content.decode())['userid']==['70']
    rt.store.disconnect()
    assert not asyncio.run(shell.execute('moodle enrol my-courses')).success
    assert len(route.calls)==1


@respx.mock
def test_readonly_allowlist_is_enforced_through_shell(stores):
    rt=runtime(stores)
    shell=LiteShell('', '', 'fixture@test',1,user_id=7,moodle=rt)
    from moodle_cli.services.enrol import EnrolService
    with patch.object(EnrolService,'get_my_courses',lambda self,userid:self.call('mod_forum_add_discussion',forumid=1)):
        result=asyncio.run(shell.execute('moodle enrol my-courses'))
    assert not result.success and 'read' in result.error.lower()
    assert not respx.calls


@respx.mock
def test_mid_request_disconnect_withholds_result(stores):
    rt=runtime(stores)
    def reply(request):
        rt.store.disconnect()
        return Response(200,json=[])
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=reply)
    shell=LiteShell('', '', 'fixture@test',1,user_id=7,moodle=rt)
    assert not asyncio.run(shell.execute('moodle enrol my-courses')).success


def test_cache_commands_parse_and_have_read_policy():
    key,_,params,_=prepare_command('moodle sync 10 --section forums')
    assert key=='moodle.sync' and params=={'course_id':10,'section':'forums'}
    assert ActionAuthorizer().check(key)=='auto'
    key,_,params,_=prepare_command('moodle cache show 10 --section forums')
    assert key=='moodle.cache.show' and params['course_id']==10
    assert ActionAuthorizer().check('moodle.forum.reply')=='ask'


def test_dynamic_capability_is_appended_only_when_changed(stores):
    from types import SimpleNamespace
    from lamb.moodle.runtime import attach_to_agent
    rt=runtime(stores)
    agent=SimpleNamespace(shell=SimpleNamespace(allowed_commands={'assistant.get'}),skill_state={},conversation=[],model='fixture-driver')
    attach_to_agent(agent,rt.store)
    assert 'moodle.sync' in agent.shell.allowed_commands
    assert 'moodle.forum.reply' not in agent.shell.allowed_commands
    first=list(agent.conversation)
    attach_to_agent(agent,rt.store)
    assert agent.conversation==first
    assert 'fixture-driver' in first[0]['content']
    rt.store.disconnect();attach_to_agent(agent,rt.store)
    assert agent.shell.allowed_commands=={'assistant.get'}
    assert len(agent.conversation)==2 and 'unavailable' in agent.conversation[-1]['content']
