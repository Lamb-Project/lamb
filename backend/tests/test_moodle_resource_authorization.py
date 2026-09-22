from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from moodle_cli.client.exceptions import MoodleAPIError
from lamb.moodle.analytics.authorization import validate_resource_scope
from lamb.moodle.analytics.client import SCOPE_FUNCTION
from tests.test_moodle_store import stores
from tests.test_moodle_runtime import runtime
from lamb.moodle.charts import ChartStore
from unittest.mock import patch
import respx
from httpx import Response

SCOPE = {'course_id':7,'group_id':2,'module_ids':[10,11]}
RESPONSE = {'authorized':True,'courseid':7,'groupid':2,'cmids':[10,11]}


def test_saved_scope_checks_exact_resources_without_recollecting_events():
    client=SimpleNamespace(call=Mock(return_value=RESPONSE))
    validate_resource_scope(client,SCOPE)
    client.call.assert_called_once_with(SCOPE_FUNCTION,courseid=7,groupid=2,cmids=[10,11])


@pytest.mark.parametrize('response', [None,{},dict(RESPONSE,authorized=False),dict(RESPONSE,authorized=1),
    dict(RESPONSE,groupid=3),dict(RESPONSE,cmids=[10]),dict(RESPONSE,courseid=8)])
def test_changed_or_missing_authorization_fails_closed(response):
    with pytest.raises(PermissionError):validate_resource_scope(SimpleNamespace(call=lambda *a,**kw:response),SCOPE)


def test_removed_plugin_or_permissions_is_denial_not_empty_evidence():
    client=SimpleNamespace(call=Mock(side_effect=MoodleAPIError('denied',error_code='nopermissions')))
    with pytest.raises(PermissionError):validate_resource_scope(client,SCOPE)


@pytest.mark.parametrize('scope', [{},dict(SCOPE,module_ids=[True]),dict(SCOPE,module_ids=[10,10]),
    dict(SCOPE,group_id=-1),dict(SCOPE,extra='ignored')])
def test_invalid_binding_rejected_before_network(scope):
    client=SimpleNamespace(call=Mock())
    with pytest.raises(PermissionError):validate_resource_scope(client,scope)
    client.call.assert_not_called()


@respx.mock
def test_saved_chart_and_listing_withheld_after_resource_permission_revocation(stores,tmp_path):
    rt=runtime(stores)
    rt.cache_root=tmp_path
    chartstore=ChartStore(rt)
    binding=dict(rt.result_binding(),course_id=7,resource_scopes=[SCOPE])
    identity=chartstore.save({'title':'Synthetic','course_id':7,'course_name':'Course',
        'as_of':'2026-09-22T12:00:00Z','timezone':'UTC','coverage':{},'rows':[]},binding,command='moodle.analytics.run')
    route=respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200,json=RESPONSE))
    with patch('lamb.moodle.runtime.MoodleScope'):
        assert chartstore.read(identity)['chart_id'] == identity
        route.mock(return_value=Response(200,json={'exception':'required_capability_exception','errorcode':'nopermissions'}))
        with pytest.raises(PermissionError): chartstore.read(identity)
        assert chartstore.listing()['items'] == []
    assert len(route.calls) == 3


def test_resource_binding_without_matching_course_is_rejected(stores):
    rt=runtime(stores)
    with pytest.raises(PermissionError):
        rt.validate_result_binding(dict(rt.result_binding(),resource_scopes=[SCOPE]),'moodle.analytics.run')


@pytest.mark.parametrize('command,data', [
    ('moodle analytics run resource-reach --course 7 --since 2026-09-01 --group 2',
     {'chart_id':'saved','title':'Resource reach','resource_scopes':[SCOPE]}),
    ('moodle analytics result 00000000-0000-0000-0000-000000000001',
     {'course_id':7,'resource_scopes':[SCOPE]}),
    ('moodle chart list',{'items':[{'course_id':7,'resource_scopes':[SCOPE]}]}),
])
def test_liteshell_preserves_resource_scope_in_generic_result_binding(stores,command,data):
    import asyncio
    from lamb.aac.liteshell.shell import LiteShell
    rt=runtime(stores)
    shell=LiteShell('','','fixture@test',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    with patch.object(rt,'execute',return_value=data):
        result=asyncio.run(shell.execute(command))
    assert result.success,result.error
    assert result.result_binding['resource_scopes'] == [SCOPE]
