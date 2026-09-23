from types import SimpleNamespace
import asyncio
from unittest.mock import patch
import httpx
import pytest
import respx
from lamb.moodle.analytics.forum_evidence_authorization import validate_forum_evidence_scope
from lamb.moodle.analytics.client import FORUM_EVIDENCE_SCOPE_FUNCTION
from lamb.moodle.charts import ChartStore
from lamb.aac.liteshell.shell import LiteShell
from tests.test_moodle_analytics_client import client
from tests.test_moodle_store import stores
from tests.test_moodle_runtime import runtime

SCOPE = dict(course_id=7,forum_id=2,group_id=3,discussion_ids=[4,5])
RESPONSE = dict(authorized=True,courseid=7,forumid=2,groupid=3,discussionids=[4,5])


@pytest.mark.parametrize('size',[0,1,100,101,1000])
def test_bounded_exact_batches(size):
    calls=[]
    def call(function,**params):
        assert function == FORUM_EVIDENCE_SCOPE_FUNCTION
        calls.append(params)
        return dict(params,authorized=True)
    ids=list(range(1,size+1))
    validate_forum_evidence_scope(SimpleNamespace(call=call),SCOPE|{'discussion_ids':ids})
    assert len(calls)==max(1,(size+99)//100)
    assert [i for c in calls for i in c['discussionids']]==ids


@pytest.mark.parametrize('change',[{'discussion_ids':[True]}, {'discussion_ids':[1,1]},
    {'discussion_ids':list(range(1,1002))},{'course_id':True},{'extra':1}])
def test_invalid_scope_no_network(change):
    with pytest.raises(PermissionError):
        validate_forum_evidence_scope(SimpleNamespace(call=lambda *a,**k:pytest.fail('network')),SCOPE|change)


@pytest.mark.parametrize('change',[{'authorized':1},{'courseid':True},{'discussionids':[4.0,5]},
    {'discussionids':[5,4]},{'posts':[]},{'groupid':0}])
def test_response_must_match_exact_scope(change):
    with pytest.raises(PermissionError):
        validate_forum_evidence_scope(SimpleNamespace(call=lambda *a,**k:RESPONSE|change),SCOPE)


def test_transport_bounds_and_fixed_parameters():
    params=dict(courseid=7,forumid=2,groupid=3,discussionids=[4,5])
    for change in ({'discussionids':[True]},{'discussionids':list(range(1,102))},
                   {'wstoken':'override'},{'forumid':True},{'fields':'message'}):
        with client(lambda req:pytest.fail('network')) as source, pytest.raises(ValueError):
            source.call(FORUM_EVIDENCE_SCOPE_FUNCTION,**(params|change))
    with client(lambda req:httpx.Response(200,content=b'x'*16385)) as source, pytest.raises(ValueError,match='byte budget'):
        source.call(FORUM_EVIDENCE_SCOPE_FUNCTION,**params)


@respx.mock
def test_saved_read_list_and_revocation(stores,tmp_path):
    rt=runtime(stores);rt.cache_root=tmp_path
    charts=ChartStore(rt)
    identity=charts.save(dict(title='Forum',course_id=7,course_name='Course',as_of='2026-09-23T12:00:00Z',
        timezone='UTC',coverage={},rows=[],forum_scopes=[SCOPE]),
        dict(rt.result_binding(),course_id=7,forum_scopes=[SCOPE]),command='moodle.analytics.run')
    route=respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=httpx.Response(200,json=RESPONSE))
    with patch('lamb.moodle.runtime.MoodleScope'):
        assert charts.read(identity)['chart_id']==identity
        assert charts.listing()['items'][0]['forum_scopes']==[SCOPE]
        route.mock(return_value=httpx.Response(200,json={'exception':'error','errorcode':'nopermissions','message':'SECRET'}))
        with pytest.raises(PermissionError,match='no longer available'): charts.read(identity)
        assert charts.listing()['items']==[]
    assert len(route.calls)==4


@pytest.mark.parametrize('command,data',[
    ('moodle chart read 00000000-0000-0000-0000-000000000001',{'course_id':7,'forum_scopes':[SCOPE]}),
    ('moodle analytics result 00000000-0000-0000-0000-000000000001',{'course_id':7,'forum_scopes':[SCOPE]}),
    ('moodle chart list',{'items':[{'course_id':7,'forum_scopes':[SCOPE]}]}),
])
def test_aac_retains_forum_scope(stores,command,data):
    rt=runtime(stores)
    shell=LiteShell('','','fixture@test',1,user_id=7,moodle=rt,allowed_commands=rt.available())
    with patch.object(rt,'execute',return_value=data):
        result=asyncio.run(shell.execute(command))
    assert result.success,result.error
    assert result.result_binding['forum_scopes']==[SCOPE]


@pytest.mark.parametrize('extra',[
    {'forum_scopes':[SCOPE]}, {'course_id':8,'forum_scopes':[SCOPE]},
    {'course_id':7,'forum_scopes':{}}, {'course_id':7,'forum_scopes':[SCOPE]*21},
    {'course_id':7,'forum_scopes':[SCOPE|{'forum_id':True}]},
])
def test_malformed_saved_binding_denied(stores,extra):
    rt=runtime(stores)
    with patch('lamb.moodle.runtime.MoodleScope'),pytest.raises(PermissionError):
        rt.validate_result_binding(dict(rt.result_binding(),**extra),'moodle.analytics.run')
