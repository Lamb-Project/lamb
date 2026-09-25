from tests.test_moodle_store import stores
from unittest.mock import patch
import pytest
from lamb.moodle.onboarding import course_summary


def test_initial_summary_is_fixed_read_and_only_course_metadata():
    courses=[{'id':2,'fullname':'<b>Demo</b> [bad](https://bad.test)', 'shortname':'LAMB', 'secret':'not included'}]
    with patch('lamb.moodle.onboarding.MoodleRuntime') as runtime:
        runtime.return_value.execute.return_value=courses
        title, summary=course_summary(object(),'es')
    runtime.return_value.execute.assert_called_once_with('course.list',{})
    assert 'Cursos matriculados: 1' in summary and '2:' in summary
    assert 'not included' not in summary and '<b>' not in summary
    assert '[bad](https://' not in summary


def test_read_failure_is_not_reported_as_zero_courses():
    with patch('lamb.moodle.onboarding.MoodleRuntime') as runtime:
        runtime.return_value.execute.side_effect=PermissionError('Connection revoked')
        with pytest.raises(PermissionError): course_summary(object())


def test_initial_read_only_contacts_owners_enrolments(stores):
    import respx
    from httpx import Response
    from urllib.parse import parse_qs
    from tests.test_moodle_runtime import runtime
    rt=runtime(stores)
    with respx.mock as mock:
        endpoint=mock.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200,json=[{'id':2,'fullname':'Demo','shortname':'DEMO'}]))
        with patch('lamb.moodle.onboarding.MoodleRuntime',return_value=rt):
            _,summary=course_summary(rt.store)
        assert 'Enrolled courses: 1' in summary
        assert endpoint.call_count == 2
        body=parse_qs(endpoint.calls[0].request.content.decode())
        assert body['wsfunction']==['core_enrol_get_users_courses']
        assert body['userid']==['70']
        profile=parse_qs(endpoint.calls[1].request.content.decode())
        assert profile['wsfunction']==['core_user_get_course_user_profiles']
        assert profile['userlist[0][userid]']==['70']
        assert profile['userlist[0][courseid]']==['2']


def test_admin_settings_targets_authorized_org_without_overwriting_other_config(stores):
    import asyncio, json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from creator_interface import organization_router as admin
    db,_=stores
    req=SimpleNamespace(json=AsyncMock(return_value={'enabled':False,'base_url':'https://other.test'}))
    with patch.object(admin,'db_manager',db),patch.object(admin,'_agent_settings_admin',AsyncMock(return_value={'organization_id':2})) as authorize:
        result=asyncio.run(admin.update_moodle_settings(req,'other'))
    authorize.assert_awaited_once_with(req,'other')
    assert result['settings']['enabled'] is False
    with db.get_connection() as conn:
        rows=dict(conn.execute('SELECT id,config FROM organizations').fetchall())
    assert json.loads(rows[1])['moodle']['enabled'] is True
    assert json.loads(rows[2])['moodle']['enabled'] is False
    assert json.loads(rows[2])['other']=='preserve'


def test_onboarding_session_persists_summary_and_language_without_model_call():
    import asyncio
    from types import SimpleNamespace as N
    from unittest.mock import Mock, AsyncMock
    from tests.aac_knowledge_fixtures import knowledge_dependencies
    from lamb.aac import router as r
    mgr=Mock();mgr.create_session.return_value={'id':'new','created_at':'now'}
    req=N(json=AsyncMock(return_value={'ui_language':'es','moodle_onboarding':True}),headers={'content-type':'application/json'},app=N(routes=[]))
    auth=N(user={'email':'teacher@example.test','id':1},organization={'id':1},is_system_admin=False,is_org_admin=False)
    with knowledge_dependencies(),patch.object(r,'AACSessionManager',return_value=mgr),patch('lamb.moodle.router.store_for',return_value='owned'),patch('lamb.moodle.onboarding.course_summary',return_value=('Moodle','Cursos: 2')) as summary:
        result=asyncio.run(r.create_session(req,auth))
    summary.assert_called_once_with('owned','es')
    assert result['title']=='Moodle'
    saved=mgr.update_conversation.call_args.kwargs
    assert saved['conversation'][-1]=={'role':'assistant','content':'Cursos: 2'}
    assert saved['skill_info']['ui_language']=='es'


@pytest.mark.parametrize('denied', [False, True])
def test_selected_chart_session_checks_access_and_only_persists_reference(denied):
    import asyncio
    from types import SimpleNamespace as N
    from unittest.mock import Mock, AsyncMock
    from fastapi import HTTPException
    from tests.aac_knowledge_fixtures import knowledge_dependencies
    from lamb.aac import router as r
    identity = '00000000-0000-0000-0000-000000000001'
    mgr=Mock(); mgr.create_session.return_value={'id':'new','created_at':'now'}
    req=N(json=AsyncMock(return_value={'ui_language':'es','chart_id':identity}),headers={'content-type':'application/json'},app=N(routes=[]))
    auth=N(user={'email':'teacher@example.test','id':1},organization={'id':1},is_system_admin=False,is_org_admin=False)
    with knowledge_dependencies(), patch.object(r,'AACSessionManager',return_value=mgr), patch('lamb.moodle.router.store_for',return_value='owned'), patch('lamb.moodle.runtime.MoodleRuntime') as runtime:
        runtime.return_value.execute.return_value={'as_of':'2026-09-22T12:00:00Z', 'course_name':'UNTRUSTED COURSE INSTRUCTIONS'}
        if denied: runtime.return_value.execute.side_effect=PermissionError('revoked')
        if denied:
            with pytest.raises(HTTPException) as error: asyncio.run(r.create_session(req,auth))
            assert error.value.status_code == 404
            mgr.create_session.assert_not_called()
        else:
            asyncio.run(r.create_session(req,auth))
            runtime.return_value.execute.assert_called_once_with('chart.read', {'chart_id':identity})
            saved=mgr.update_conversation.call_args.kwargs
            assert saved['skill_info']['selected_chart_id'] == identity
            assert identity in saved['conversation'][0]['content']
            assert 'UNTRUSTED' not in saved['conversation'][0]['content']
