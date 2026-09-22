from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
import respx
from httpx import Response
from lamb.moodle.analytics.authorization import validate_completion_scope
from lamb.moodle.analytics.client import COMPLETION_SCOPE_FUNCTION
from tests.test_moodle_store import stores
from tests.test_moodle_runtime import runtime
from lamb.moodle.charts import ChartStore

SCOPE = {'course_id':7,'module_ids':[42]}
RESPONSE = {'authorized':True,'courseid':7,'cmids':[42]}


def test_exact_permission_only_call():
    client = SimpleNamespace(call=Mock(return_value=RESPONSE))
    validate_completion_scope(client,SCOPE)
    client.call.assert_called_once_with(COMPLETION_SCOPE_FUNCTION,courseid=7,cmids=[42])


@pytest.mark.parametrize('response', [None,{},dict(RESPONSE,authorized=1),dict(RESPONSE,authorized=False),
    dict(RESPONSE,courseid=True),dict(RESPONSE,cmids=[43])])
def test_response_mismatch_denies(response):
    with pytest.raises(PermissionError):
        validate_completion_scope(SimpleNamespace(call=lambda *a,**kw:response),SCOPE)


@pytest.mark.parametrize('scope', [{},dict(SCOPE,module_ids=[True]),dict(SCOPE,course_id=-1),dict(SCOPE,extra=1)])
def test_bad_scope_does_not_call_source(scope):
    client=SimpleNamespace(call=Mock())
    with pytest.raises(PermissionError): validate_completion_scope(client,scope)
    client.call.assert_not_called()


@respx.mock
def test_saved_chart_and_listing_revoke_without_completion_recollection(stores,tmp_path):
    rt=runtime(stores); rt.cache_root=tmp_path
    chartstore=ChartStore(rt)
    identity=chartstore.save({'title':'Grades','course_id':7,'course_name':'Course',
        'as_of':'2026-09-22T12:00:00Z','timezone':'UTC','coverage':{},'rows':[], 'completion_scopes':[SCOPE]},
        dict(rt.result_binding(),course_id=7,completion_scopes=[SCOPE]), command='moodle.analytics.run')
    route=respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200,json=RESPONSE))
    with patch('lamb.moodle.runtime.MoodleScope'):
        assert chartstore.read(identity)['chart_id'] == identity
        assert chartstore.listing()['items'][0]['completion_scopes'] == [SCOPE]
        route.mock(return_value=Response(200,json={'exception':'required_capability_exception','errorcode':'nopermissions'}))
        with pytest.raises(PermissionError): chartstore.read(identity)
        assert chartstore.listing()['items'] == []
    assert all(b'local_lambanalytics_completion_scope' in call.request.content for call in route.calls)


@pytest.mark.parametrize('courses', [None,8])
def test_completion_scope_requires_matching_bound_course(stores,courses):
    rt=runtime(stores)
    binding=dict(rt.result_binding(),completion_scopes=[SCOPE])
    if courses: binding['course_id']=courses
    with patch('lamb.moodle.runtime.MoodleScope'), pytest.raises(PermissionError):
        rt.validate_result_binding(binding,'moodle.analytics.run')


@pytest.mark.parametrize('command,data', [
    ('moodle analytics result 00000000-0000-0000-0000-000000000001', {'course_id':7,'completion_scopes':[SCOPE]}),
    ('moodle chart list',{'items':[{'course_id':7,'completion_scopes':[SCOPE]}]}),
    ('moodle analytics runs',{'items':[{'course_id':7,'completion_scopes':[SCOPE]}]}),
    ('moodle analytics start activity-completion --course 7',{'course_id':7,'completion_scopes':[SCOPE]}),
    ('moodle analytics run activity-completion --course 7',{'course_id':7,'completion_scopes':[SCOPE],
        'processed_students':25,'continue_command':'moodle analytics continue 00000000-0000-0000-0000-000000000001 --step 1'}),
    ('moodle analytics continue 00000000-0000-0000-0000-000000000001 --step 0',{'course_id':7,'completion_scopes':[SCOPE]}),
])
def test_liteshell_preserves_completion_scope(stores,command,data):
    import asyncio
    from lamb.aac.liteshell.shell import LiteShell
    rt=runtime(stores)
    shell=LiteShell('','','fixture@test',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    with patch.object(rt,'execute',return_value=data):
        result=asyncio.run(shell.execute(command))
    assert result.success,result.error
    assert result.result_binding['completion_scopes'] == [SCOPE]
