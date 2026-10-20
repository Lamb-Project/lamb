from urllib.parse import parse_qs
import pytest
import respx
from httpx import Response
from moodle_cli.client.http import MoodleHTTPClient
from lamb.moodle.scope import MoodleScope


def fixture_response(role='editingteacher'):
    calls=[]
    def reply(request):
        body=parse_qs(request.content.decode());fn=body['wsfunction'][0];calls.append((fn,body))
        if fn == 'core_enrol_get_users_courses':
            assert body['userid']==['7']
            return Response(200,json=[{'id':10,'shortname':'demo','fullname':'Demo'}])
        if fn == 'core_user_get_course_user_profiles':
            assert body['userlist[0][userid]']==['7']
            return Response(200,json=[{'id':7,'roles':[{'shortname':role}]}])
        if fn == 'core_enrol_get_enrolled_users':
            return Response(200,json=[{'id':7,'fullname':'Teacher'}, {'id':8,'fullname':'Demo learner'}])
        pytest.fail('Unexpected Moodle function: '+fn)
    return calls,reply


@respx.mock
def test_teacher_can_read_class_but_not_unrelated_individual_or_course():
    calls,reply=fixture_response()
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=reply)
    with MoodleHTTPClient('https://moodle.test','fixture',readonly=True) as client:
        scope=MoodleScope(client,7)
        assert scope.require_member(10,8)==8
        with pytest.raises(PermissionError):scope.require_member(10,999)
        with pytest.raises(PermissionError):scope.require_teacher(999)
        assert [u['id'] for u in scope.search_class(10,'fullname','learner')]==[8]
    assert len(calls)==3
    assert not any(fn=='core_user_get_users' for fn,_ in calls)


@pytest.mark.parametrize('role',['student','observer',''])
@respx.mock
def test_non_teacher_never_fetches_class_roster(role):
    calls,reply=fixture_response(role)
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=reply)
    with MoodleHTTPClient('https://moodle.test','fixture',readonly=True) as client:
        scope=MoodleScope(client,7)
        assert scope.require_member(10,7)==7
        with pytest.raises(PermissionError):scope.class_roster(10)
    assert [fn for fn,_ in calls]==['core_enrol_get_users_courses','core_user_get_course_user_profiles']


@respx.mock
def test_role_proof_is_not_reused_across_commands():
    calls,reply=fixture_response()
    route=respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=reply)
    with MoodleHTTPClient('https://moodle.test','fixture',readonly=True) as client:
        MoodleScope(client,7).require_teacher(10)
        _,student_reply=fixture_response('student');route.mock(side_effect=student_reply)
        with pytest.raises(PermissionError):MoodleScope(client,7).require_teacher(10)
