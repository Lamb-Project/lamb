import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.gradebook_run import start, publish
from lamb.moodle.analytics.gradebook_state import advance_cursor
from lamb.moodle.charts import ChartStore
from tests.test_moodle_gradebook_run import store
from tests.test_moodle_gradebook_state import page


def fixture(tmp_path, language='en', count=2):
    s=store(tmp_path); record=start(s,7,list(range(2,count+2)),language=language,tz='Europe/Madrid')
    state=record['state']
    for i,item in enumerate(state['items']):
        p=page((1,2),upper=2,more=False)
        p['gradeitemid']=p['item']['id']=item['scope']['grade_item_id']
        p['item']['needsupdate']=int(i==0)
        p['grades'][0]['userid']=91234561
        p['grades'][1].update(userid=91234562,finalgrade=None)
        item['cursor']=advance_cursor(item['cursor'],0,p)
        item['context']={'students':[91234561,91234562,91234563],'candidates':[91234561,91234562,91234563],
            'excluded_students':[],'population_basis':'active_candidate_population_manual_item',
            'candidate_basis':'current_active_enrolments_with_role_shortname_student','private_extra':'PRIVATE_SENTINEL'}
    state.update(done=True,started_at='2026-09-23T10:00:00+00:00',completed_at='2026-09-23T10:01:00+00:00')
    s.replace(record['id'],state,expected_revision=0)
    binding={'generation':'one','base_url':'https://fixture.test','moodle_user_id':3}
    rt=SimpleNamespace(cache_root=tmp_path/'moodle',store=SimpleNamespace(organization_id=1,owner_id=2),
        result_binding=lambda:dict(binding),validate_result_binding=lambda *args:None)
    return s,rt,SimpleNamespace(checkpoint=lambda:None),record['id']


@pytest.mark.parametrize('language',['en','es','ca','eu'])
def test_aggregate_only_localized_immutable_snapshot(tmp_path,language):
    s,rt,c,identity=fixture(tmp_path,language)
    result=publish(s,rt,c,identity)
    saved=ChartStore(rt).read(result['chart_id'])
    assert saved['as_of_local']=='2026-09-23T12:01:00+02:00'
    assert saved['language']==language and saved['metrics']['comparable_assessments']==1
    assert saved['coverage']['collection_complete'] and not saved['coverage']['complete']
    assert saved['rows'][0]['metrics']['median_pct'] is None
    assert saved['rows'][1]['metrics']['median_pct']==90
    assert saved['rows'][1]['metrics']['missing_n']==2
    assert saved['gradebook_scopes']==[dict(course_id=7,grade_item_id=i,group_id=0) for i in (2,3)]
    for private in ('9123456','PRIVATE_SENTINEL','userid','fingerprint','rawgrade'):
        assert private not in json.dumps(saved)
    assert publish(s,rt,c,identity)==result
    assert len(list(ChartStore(rt).root.glob('*.json')))==1


def test_maximum_selection_fits_saved_snapshot_limit(tmp_path):
    s,rt,c,identity=fixture(tmp_path,count=20)
    result=publish(s,rt,c,identity)
    assert len(result['rows'])==20 and result['next_offset'] is None


def test_lost_save_response_and_ack_retry_reuse_exact_chart(tmp_path):
    s,rt,c,identity=fixture(tmp_path)
    original=ChartStore.save
    def lost(*args,**kwargs):
        original(*args,**kwargs)
        raise OSError('Lost response')
    with patch.object(ChartStore,'save',lost),pytest.raises(OSError):publish(s,rt,c,identity)
    frozen=s.read(identity)['state']['publication']
    replace=s.replace
    def lost_ack(key,state,**kwargs):
        if state.get('published'):raise OSError('Lost acknowledgement')
        return replace(key,state,**kwargs)
    with patch.object(s,'replace',lost_ack),pytest.raises(OSError):publish(s,rt,c,identity)
    assert publish(s,rt,c,identity)['chart_id']==frozen['id']
    assert len(list(ChartStore(rt).root.glob('*.json')))==1


def test_revocation_and_connection_change_deny(tmp_path):
    s,rt,c,identity=fixture(tmp_path)
    publish(s,rt,c,identity)
    def deny(*args):raise PermissionError('Revoked')
    rt.validate_result_binding=deny
    with pytest.raises(PermissionError):publish(s,rt,c,identity)
    rt.result_binding=lambda:{'generation':'other'}
    with pytest.raises(PermissionError,match='another connection'):publish(s,rt,c,identity)


@pytest.mark.parametrize('defect',['unfinished','naive','reversed','scope'])
def test_invalid_evidence_never_saves(tmp_path,defect):
    s,rt,c,identity=fixture(tmp_path)
    record=s.read(identity); state=record['state']
    if defect=='unfinished':state['items'][0]['cursor']['done']=False
    if defect=='naive':state['completed_at']='2026-09-23T10:01:00'
    if defect=='reversed':state['completed_at']='2026-09-22T10:01:00+00:00'
    if defect=='scope':state['items'][0]['scope']['grade_item_id']=99
    s.replace(identity,state,expected_revision=record['revision'])
    with pytest.raises(ValueError):publish(s,rt,c,identity)
    assert not list((tmp_path/'moodle'/'charts').glob('**/*.json'))
