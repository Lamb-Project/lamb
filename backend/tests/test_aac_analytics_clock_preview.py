"""Large saved charts must not lose their requested-zone snapshot timestamp."""
from copy import deepcopy
import pytest
from lamb.aac.result_store import ResultStore,compact,encode,RESULT_BYTES,provider_messages


@pytest.mark.parametrize('zone,local',[
    ('Europe/Madrid','2026-09-22T20:51:08+02:00'),
    ('Asia/Kathmandu','2026-09-23T00:36:08+05:45'),
    ('America/New_York','2026-09-22T14:51:08-04:00'),
])
def test_oversized_chart_keeps_local_clock_and_raw_evidence(tmp_path,zone,local):
    data={'chart_id':'chart','course_id':7,'course_name':'Fixture','group_id':0,
        'as_of':'2026-09-22T18:51:08+00:00','source':'fixture','watermark':9,
        'view_time':{'weekday_hour':[{'weekday':day,'hour':hour,'counts':'x'*120}
            for day in range(7) for hour in range(24)]},
        'schema_version':1,'recipe':{'id':'view-trends','version':1},
        'rows':[{'name':'2026-09-22','value':7}], 'title':'Daily views','coverage':{'complete':False},
        'as_of_local':local,'snapshot_date_label':f'{local} ({zone})','timezone':zone}
    payload={'success':True,'data':data};before=deepcopy(payload)
    store=ResultStore(1,2,root=tmp_path/'private')
    projected=compact(payload,store=store,origin={'command':'moodle.chart.read'})
    assert projected['context_result']['truncated']
    for key in ('as_of_local','snapshot_date_label','timezone'):
        assert projected['data'][key]==data[key]
    assert len(encode(projected))<=RESULT_BYTES
    assert payload==before
    assert store.read(projected['context_result']['result_id'])['payload']==before
    message={'role':'tool','content':encode(payload).decode(),'_aac_model_content':encode(projected).decode()}
    assert data['snapshot_date_label'] in provider_messages([message])[0]['content']


@pytest.mark.parametrize('provenance',[
    {'basis':'stored_course_defaults'},
    {'deadline_basis':'connected_account_effective',
     'deadline_provenance_caption':'Dates apply to the connected account, not verified course defaults.'},
])
def test_oversized_saved_chart_preserves_date_provenance(tmp_path,provenance):
    data={'title':'Fixture','timezone':'Europe/Madrid','course_id':7,'course_name':'Fixture',
        'chart_id':'saved','as_of':'2026-09-23T10:00:00Z','language':'en',
        'rows':[{'name':'x'*160,'due':1792888200} for _ in range(100)],
        'coverage':{'complete':True},'labels':['label']*12,'caption':'Fixture',
        'source':'fixture','recipe':'assignment-submissions-v1','limitations':[],**provenance}
    store=ResultStore(1,2,root=tmp_path/'private')
    payload={'success':True,'data':data}
    projected=compact(payload,store=store,origin={'command':'moodle.chart.read'})
    assert projected['context_result']['truncated']
    for key,value in provenance.items():
        assert projected['data'][key]==value
    assert store.read(projected['context_result']['result_id'])['payload']==payload
