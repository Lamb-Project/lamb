import asyncio
from unittest.mock import patch
import httpx
import pytest
import respx
from lamb.moodle.charts import ChartStore
from lamb.aac.liteshell.shell import LiteShell
from tests.test_moodle_store import stores
from tests.test_moodle_runtime import runtime

SCOPE = dict(course_id=7,grade_item_id=2,group_id=3)
RESPONSE = dict(authorized=True,courseid=7,gradeitemid=2,groupid=3)


@respx.mock
def test_saved_gradebook_read_and_list_recheck_only_authority(stores,tmp_path):
    rt=runtime(stores);rt.cache_root=tmp_path
    charts=ChartStore(rt)
    identity=charts.save(dict(title='Assessment comparison',course_id=7,course_name='Course',
        as_of='2026-09-23T12:00:00Z',timezone='UTC',coverage={},rows=[],gradebook_scopes=[SCOPE]),
        dict(rt.result_binding(),course_id=7,gradebook_scopes=[SCOPE]),command='moodle.analytics.run')
    route=respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=httpx.Response(200,json=RESPONSE))
    with patch('lamb.moodle.runtime.MoodleScope'):
        assert charts.read(identity)['chart_id']==identity
        assert charts.listing()['items'][0]['gradebook_scopes']==[SCOPE]
        route.mock(return_value=httpx.Response(200,json={'exception':'error','errorcode':'nopermissions','message':'SECRET'}))
        with pytest.raises(PermissionError,match='no longer available'):charts.read(identity)
        assert charts.listing()['items']==[]
    assert len(route.calls)==4
    for call in route.calls:
        body=call.request.content.decode()
        assert 'wsfunction=local_lambanalytics_gradebook_scope' in body
        assert 'gradebook_grades' not in body and 'gradebook_population' not in body


@pytest.mark.parametrize('command,data',[
    ('moodle chart read 00000000-0000-0000-0000-000000000001',{'course_id':7,'gradebook_scopes':[SCOPE]}),
    ('moodle analytics result 00000000-0000-0000-0000-000000000001',{'course_id':7,'gradebook_scopes':[SCOPE]}),
    ('moodle chart list',{'items':[{'course_id':7,'gradebook_scopes':[SCOPE]},{'course_id':7,'gradebook_scopes':[SCOPE]}]}),
])
def test_aac_retains_exact_gradebook_scope(stores,command,data):
    rt=runtime(stores)
    shell=LiteShell('','','fixture@test',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    with patch.object(rt,'execute',return_value=data):
        result=asyncio.run(shell.execute(command))
    assert result.success,result.error
    assert result.result_binding['gradebook_scopes']==[SCOPE]


@pytest.mark.parametrize('extra',[
    {'gradebook_scopes':[SCOPE]}, {'course_id':8,'gradebook_scopes':[SCOPE]},
    {'course_id':7,'gradebook_scopes':{}}, {'course_id':7,'gradebook_scopes':[]},
    {'course_id':7,'gradebook_scopes':[SCOPE]*21},
    {'course_id':7,'gradebook_scopes':[SCOPE|{'grade_item_id':True}]},
])
def test_invalid_saved_bindings_denied(stores,extra):
    rt=runtime(stores)
    with patch('lamb.moodle.runtime.MoodleScope'),pytest.raises(PermissionError):
        rt.validate_result_binding(dict(rt.result_binding(),**extra),'moodle.analytics.run')


@respx.mock
def test_duplicate_scopes_denied(stores):
    rt=runtime(stores)
    respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=httpx.Response(200,json=RESPONSE))
    with patch('lamb.moodle.runtime.MoodleScope'),pytest.raises(PermissionError,match='Duplicate'):
        rt.validate_result_binding(dict(rt.result_binding(),course_id=7,gradebook_scopes=[SCOPE,SCOPE]),'moodle.analytics.run')


def test_listing_can_bind_multiple_comparisons_without_truncating_scope(stores):
    rt=runtime(stores)
    scopes=[dict(SCOPE,grade_item_id=i) for i in range(1,41)]
    with patch('lamb.moodle.runtime.MoodleScope'), \
            patch('lamb.moodle.analytics.gradebook_authorization.validate_gradebook_scope') as validate:
        rt.validate_result_binding(dict(rt.result_binding(),course_ids=[7],gradebook_scopes=scopes),'moodle.chart.list')
        assert validate.call_count==40
        with pytest.raises(PermissionError):
            rt.validate_result_binding(dict(rt.result_binding(),course_ids=[7],gradebook_scopes=scopes),'moodle.analytics.run')
