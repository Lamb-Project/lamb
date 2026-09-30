from unittest.mock import patch
from types import SimpleNamespace
import pytest
from tests.test_moodle_router import client
from tests.test_moodle_store import stores
from lamb.moodle.connection_summary import connection_summary

BINDING = {'generation': 1, 'moodle_user_id': 7, 'base_url': 'https://moodle.test'}
INFO = {'userid': 7, 'siteurl': 'https://moodle.test', 'release': '4.5.2', 'token': 'secret'}
COURSES = [
    {'id': 10, 'fullname': 'Teaching', 'shortname': 'T', 'my_roles': [{'shortname': 'editingteacher'}], 'my_roles_status': 'available', 'private_field': 'omit'},
    {'id': 20, 'fullname': 'Learning', 'shortname': 'L', 'my_roles': [{'shortname': 'student'}], 'my_roles_status': 'available'},
    {'id': 30, 'fullname': 'Unknown', 'shortname': 'U', 'my_roles': None, 'my_roles_status': 'unavailable'},
]


def configured_runtime(mock):
    runtime = mock.return_value
    runtime.result_binding.return_value = BINDING
    runtime.execute.side_effect = [INFO, COURSES]
    runtime.snapshot.return_value = {'record': {'base_url': BINDING['base_url'], 'username': 'teacher', 'moodle_user_id': 7, 'token_encrypted': 'secret'}}
    return runtime


def test_overview_only_exposes_public_identity_version_and_own_course_roles():
    with patch('lamb.moodle.connection_summary.MoodleRuntime') as mock:
        runtime = configured_runtime(mock)
        result = connection_summary(SimpleNamespace())
        assert [call.args for call in runtime.execute.call_args_list] == [('site.info', {}), ('course.list', {})]
        assert result['release'] == '4.5.2'
        assert [c['my_roles'] for c in result['courses']] == [c['my_roles'] for c in COURSES]
        assert 'private_field' not in str(result) and 'secret' not in str(result)


@pytest.mark.parametrize('info', [{**INFO, 'userid': 8}, {**INFO, 'siteurl': 'https://foreign.test'}])
def test_identity_mismatch_never_releases_courses(info):
    with patch('lamb.moodle.connection_summary.MoodleRuntime') as mock:
        runtime = configured_runtime(mock); runtime.execute.side_effect = [info]
        with pytest.raises(PermissionError): connection_summary(SimpleNamespace())
        assert runtime.execute.call_count == 1


def test_changed_connection_during_summary_withholds_results():
    with patch('lamb.moodle.connection_summary.MoodleRuntime') as mock:
        runtime = configured_runtime(mock)
        runtime.result_binding.side_effect = [BINDING, {**BINDING, 'generation': 2}]
        with pytest.raises(PermissionError): connection_summary(SimpleNamespace())


def test_missing_version_and_empty_courses_remain_explicit():
    with patch('lamb.moodle.connection_summary.MoodleRuntime') as mock:
        runtime = configured_runtime(mock); runtime.execute.side_effect = [{**INFO, 'release': None}, []]
        result = connection_summary(SimpleNamespace())
        assert result['release'] == '' and result['courses'] == []


def test_summary_route_is_authenticated_private_and_redacts_failures(client):
    c, auth, _ = client
    with patch('lamb.moodle.connection_summary.connection_summary', return_value={'courses': [], 'release': ''}) as read:
        response = c.get('/moodle/connection/summary')
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'private, no-store'
        for error, code in [(PermissionError('secret'), 403), (RuntimeError('secret'), 503)]:
            read.side_effect = error
            response = c.get('/moodle/connection/summary')
            assert response.status_code == code and 'secret' not in response.text
    auth.organization['id'] = 2
    assert c.get('/moodle/connection/summary').status_code == 403
    c.app.dependency_overrides.clear()
    assert c.get('/moodle/connection/summary').status_code in (401, 403)


def test_summary_uses_standard_owner_only_services(stores):
    import respx
    from httpx import Response
    from urllib.parse import parse_qs
    from tests.test_moodle_runtime import runtime
    rt = runtime(stores)
    calls = []
    def reply(request):
        body = parse_qs(request.content.decode()); name = body['wsfunction'][0]; calls.append(name)
        if name == 'core_webservice_get_site_info':
            return Response(200, json={**INFO, 'userid': 70, 'username': 'demo', 'fullname': 'Demo', 'sitename': 'Fixture', 'lang': 'en', 'version': '2024100700', 'functions': []})
        if name == 'core_enrol_get_users_courses':
            assert body['userid'] == ['70']
            return Response(200, json=[{'id': 10, 'shortname': 'T', 'fullname': 'Teaching'}])
        assert name == 'core_user_get_course_user_profiles'
        assert body['userlist[0][userid]'] == ['70']
        return Response(200, json=[{'id': 70, 'roles': [{'shortname': 'teacher'}]}])
    with respx.mock:
        respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=reply)
        with patch('lamb.moodle.connection_summary.MoodleRuntime', return_value=rt):
            result = connection_summary(rt.store)
    assert result['release'] == '4.5.2'
    assert result['courses'][0]['my_roles'] == [{'shortname': 'teacher'}]
    assert calls == ['core_webservice_get_site_info', 'core_enrol_get_users_courses', 'core_user_get_course_user_profiles']
