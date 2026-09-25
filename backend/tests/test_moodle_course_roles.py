from unittest.mock import Mock, patch
import pytest
from lamb.moodle.course_roles import with_my_roles
from moodle_cli.client.exceptions import MoodleAPIError, ConnectionError as MoodleConnectionError
from tests.test_moodle_store import stores

COURSES = [{'id':10,'fullname':'Teaching'}, {'id':11,'fullname':'Studying'}]


def test_roles_are_per_course_owner_only_and_minimal():
    client = Mock()
    client.call.side_effect = [
        [{'id':70,'email':'private','roles':[{'id':3,'shortname':'editingteacher','name':'Professor','extra':'omit'}]}],
        [{'id':70,'roles':[{'shortname':'student'},{'shortname':'custom_role','name':'Tutor'}]}]]
    result = with_my_roles(client,COURSES,70)
    assert result[0]['my_roles']==[{'id':3,'shortname':'editingteacher','name':'Professor'}]
    assert result[1]['my_roles']==[{'shortname':'student'},{'shortname':'custom_role','name':'Tutor'}]
    assert all(c['my_roles_status']=='available' for c in result)
    for call, course in zip(client.call.call_args_list, COURSES):
        assert call.args==('core_user_get_course_user_profiles',)
        assert call.kwargs=={'userlist':[{'userid':70,'courseid':course['id']}]}
    assert COURSES[0]=={'id':10,'fullname':'Teaching'}


@pytest.mark.parametrize('profile', [None, {}, {'roles':None}, {'roles':[{}]}])
def test_missing_roles_are_unknown_not_empty(profile):
    with patch('lamb.moodle.course_roles.CourseIdentityService.own_course_profile',return_value=profile):
        item=with_my_roles(Mock(),COURSES[:1],70)[0]
    assert item['my_roles'] is None and item['my_roles_status']=='unavailable'


@pytest.mark.parametrize('error', [PermissionError('private'), MoodleAPIError('private'), MoodleConnectionError('private')])
def test_partial_failure_preserves_courses_and_other_roles(error):
    with patch('lamb.moodle.course_roles.CourseIdentityService.own_course_profile',side_effect=[error,{'roles':[]}]):
        result=with_my_roles(Mock(),COURSES,70)
    assert result[0]['my_roles'] is None
    assert result[1]['my_roles']==[] and result[1]['my_roles_status']=='available'
    assert 'private' not in str(result)


def test_unexpected_programming_errors_are_not_hidden():
    with patch('lamb.moodle.course_roles.CourseIdentityService.own_course_profile',side_effect=RuntimeError('bug')):
        with pytest.raises(RuntimeError): with_my_roles(Mock(),COURSES,70)


@pytest.mark.parametrize('key,params', [('course.list',{}),('course.search',{'query':'Demo'}),
    ('enrol.my-courses',{}),('course.timeline',{'classification':'all'})])
def test_all_course_discovery_paths_return_roles(stores,key,params):
    import respx
    from httpx import Response
    from urllib.parse import parse_qs
    from tests.test_moodle_runtime import runtime
    calls=[]
    def reply(request):
        data=parse_qs(request.content.decode());fn=data['wsfunction'][0];calls.append(fn)
        courses=[{'id':10,'shortname':'demo','fullname':'Demo'}]
        if fn=='core_user_get_course_user_profiles':
            assert data['userlist[0][userid]']==['70']
            assert data['userlist[0][courseid]']==['10']
            return Response(200,json=[{'id':70,'roles':[{'shortname':'teacher'}]}])
        if fn=='core_course_get_enrolled_courses_by_timeline_classification':
            return Response(200,json={'courses':courses,'nextoffset':0})
        assert fn=='core_enrol_get_users_courses'
        return Response(200,json=courses)
    with respx.mock:
        respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=reply)
        result=runtime(stores).execute(key,params)
    assert result[0]['my_roles']==[{'shortname':'teacher'}]
    assert result[0]['my_roles_status']=='available'
    assert len(calls)==2
