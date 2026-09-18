import asyncio
from urllib.parse import parse_qs
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from lamb.aac.liteshell.shell import LiteShell


def fixture(stores):
    rt=runtime(stores);calls=[]
    def reply(request):
        body=parse_qs(request.content.decode());fn=body['wsfunction'][0];calls.append((fn,body))
        answers={
            'core_enrol_get_users_courses':[{'id':10,'shortname':'demo','fullname':'Demo'}],
            'core_user_get_course_user_profiles':[{'id':70,'roles':[{'shortname':'teacher'}]}],
            'core_enrol_get_enrolled_users':[{'id':70},{'id':80}],
            'core_badges_get_user_badges':{'badges':[{'id':1,'courseid':10}]},
            'core_calendar_get_calendar_events':{'events':[{'id':1,'courseid':10},{'id':2,'courseid':999},{'id':3,'courseid':0}]},
        }
        assert fn in answers,fn
        return Response(200,json=answers[fn])
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=reply)
    return LiteShell('','','fixture',1,user_id=7,moodle=rt,allowed_commands=rt.available()),calls


@respx.mock
def test_own_badges_default_to_token_owner(stores):
    shell,calls=fixture(stores)
    result=asyncio.run(shell.execute('moodle badge user'))
    assert result.success,result.error
    assert len(calls)==1 and calls[0][1]['userid']==['70']


@respx.mock
def test_other_badges_must_be_course_scoped_and_enrolled(stores):
    shell,calls=fixture(stores)
    assert not asyncio.run(shell.execute('moodle badge user --user-id 80')).success
    assert not asyncio.run(shell.execute('moodle badge user --user-id 999 --course-id 10')).success
    assert not any(fn=='core_badges_get_user_badges' for fn,_ in calls)
    result=asyncio.run(shell.execute('moodle badge user --user-id 80 --course-id 10'))
    assert result.success,result.error
    body=calls[-1][1]
    assert body['userid']==['80'] and body['courseid']==['10']


@respx.mock
def test_calendar_uses_own_courses_and_filters_unrelated_course_events(stores):
    shell,calls=fixture(stores)
    result=asyncio.run(shell.execute('moodle calendar events'))
    assert result.success,result.error
    assert [event['id'] for event in result.data]==[1,3]
    assert calls[-1][1]['events[courseids][0]']==['10']
    count=len(calls)
    assert not asyncio.run(shell.execute('moodle calendar events --course-id 999')).success
    assert all(fn!='core_calendar_get_calendar_events' for fn,_ in calls[count:])
