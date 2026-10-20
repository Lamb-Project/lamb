import asyncio
from urllib.parse import parse_qs
import pytest
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from lamb.aac.liteshell.shell import LiteShell


def responses():
    calls=[]
    def respond(request):
        p=parse_qs(request.content.decode());fn=p['wsfunction'][0];calls.append((fn,p))
        answers={
            'core_enrol_get_users_courses':[{'id':10,'shortname':'demo','fullname':'Demo'}],
            'core_user_get_course_user_profiles':[{'id':70,'roles':[{'shortname':'editingteacher'}]}],
            'core_course_get_courses':[{'id':10,'shortname':'demo','fullname':'Demo'}],
            'core_course_get_contents':[{'id':1,'name':'Section','modules':[
                {'id':200,'modname':'forum','instance':20},{'id':400,'modname':'assign','instance':40}]}],
            'mod_forum_get_forum_discussions':{'discussions':[{'id':90,'discussion':30}]},
            'mod_forum_get_discussion_posts':{'posts':[{'id':90,'discussionid':30,'message':'Course question'}]},
            'core_enrol_get_enrolled_users':[{'id':70,'fullname':'Teacher'},{'id':80,'fullname':'Learner'}],
            'core_user_get_users_by_field':[{'id':80,'fullname':'Learner'}],
            'mod_assign_get_submissions':{'assignments':[{'assignmentid':40,'submissions':[{'id':50,'userid':80}]}]},
        }
        assert fn in answers,fn
        return Response(200,json=answers[fn])
    return calls,respond


@respx.mock
def test_select_course_then_read_owned_discussion_and_assignment(stores):
    rt=runtime(stores);calls,respond=responses()
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    async def run():
        assert not (await shell.execute('moodle forum posts 30')).success
        assert (await shell.execute('moodle course get 10')).success
        result=await shell.execute('moodle forum posts 30')
        assert result.success,result.error
        assert result.data[0]['message']=='Course question'
        result=await shell.execute('moodle assign submissions 40')
        assert result.success,result.error
        assert result.data[0]['userid']==80
    asyncio.run(run())
    assert 'core_course_get_courses' not in {fn for fn,_ in calls}


@respx.mock
def test_foreign_resources_and_individual_never_reach_detail_endpoint(stores):
    rt=runtime(stores);calls,respond=responses()
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    async def run():
        assert (await shell.execute('moodle course get 10')).success
        for command in ['moodle forum posts 90','moodle forum posts 999','moodle forum discussions 999',
                        'moodle assign submissions 999','moodle user get 999','moodle course get 999']:
            result=await shell.execute(command)
            assert not result.success,command
    asyncio.run(run())
    assert not ({'mod_forum_get_discussion_posts','mod_assign_get_submissions','core_user_get_users_by_field'} & {fn for fn,_ in calls})


@respx.mock
def test_user_search_uses_enrolment_instead_of_site_directory(stores):
    rt=runtime(stores);calls,respond=responses()
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    async def run():
        await shell.execute('moodle course get 10')
        result=await shell.execute('moodle user list --key firstname --value nobody')
        assert result.success,result.error
        assert result.data==[]
    asyncio.run(run())
    assert 'core_user_get_users' not in {fn for fn,_ in calls}


@respx.mock
def test_course_discovery_never_queries_site_wide_directory(stores):
    rt=runtime(stores);calls,respond=responses()
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    shell=LiteShell('','','fixture',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    async def run():
        for command in ['moodle course list','moodle course search Demo']:
            result=await shell.execute(command)
            assert result.success,result.error
            assert [c['id'] for c in result.data]==[10]
    asyncio.run(run())
    assert {fn for fn,_ in calls}=={'core_enrol_get_users_courses','core_user_get_course_user_profiles'}
