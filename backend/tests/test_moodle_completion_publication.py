import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from lamb.moodle.analytics.completion_run import start, publish
from lamb.moodle.charts import ChartStore
from tests.test_moodle_completion_checkpoints import store
from tests.test_moodle_completion_state import row


def fixture(tmp_path, language='en'):
    checkpoints=store(tmp_path)
    record=start(checkpoints,7,language=language,tz='Europe/Madrid');state=record['state']
    counts=row(10)
    counts.update(name='Activity',availability_configured=False,learner_eligibility='not_collected',
        population_students=4,incomplete=1,complete=1,complete_pass=1,complete_fail=1,overall_complete=3,
        private_extra='DO_NOT_PUBLISH')
    state.update(done=True,completed_at='2026-09-22T12:00:00+00:00',
        cursor={'students':[91234561,91234562,91234563,91234564],'next_student':4,'rows':[counts]},
        context={'course_id':7,'course_name':'Fixture','disabled':0,'fingerprint':'PRIVATE_FINGERPRINT',
            'population':{'student_rows':4,'users_scanned':5,'role_unknown':0,'population_exhausted':True,
                'private_extra':'DO_NOT_PUBLISH'}})
    checkpoints.replace(record['id'],state,expected_revision=0)
    binding={'generation':'one','base_url':'https://fixture.test','moodle_user_id':3,'policy':{'enabled':True}}
    runtime=SimpleNamespace(cache_root=tmp_path/'moodle',store=SimpleNamespace(organization_id=1,owner_id=2),
        result_binding=lambda:dict(binding),validate_result_binding=lambda *args:None)
    client=SimpleNamespace(checkpoint=lambda:None)
    return checkpoints,runtime,client,record['id']


@pytest.mark.parametrize('language',['en','es','ca','eu'])
def test_finished_projection_preserves_scope_date_language_but_no_private_cursor(tmp_path,language):
    s,rt,c,identity=fixture(tmp_path,language)
    result=publish(s,rt,c,identity)
    saved=ChartStore(rt).read(result['chart_id'])
    assert saved['language']==language and saved['timezone']=='Europe/Madrid'
    assert saved['collection_run_id']==result['collection_run_id']==identity
    assert saved['collection_completed_at']==saved['as_of']=='2026-09-22T12:00:00+00:00'
    assert saved['completion_scopes']==[{'course_id':7,'module_ids':[10]}]
    assert saved['rows'][0]['overall_complete']==3 and len(saved['completion_columns'])==13
    assert saved['rows'][0]['overall_by_state'] is None
    encoded=json.dumps(saved)
    for private in ('9123456','DO_NOT_PUBLISH','PRIVATE_FINGERPRINT','next_student'):
        assert private not in encoded
    again=publish(s,rt,c,identity)
    assert again==result and len(list(ChartStore(rt).root.glob('*.json')))==1


def test_lost_chart_save_response_recovers_reserved_publication(tmp_path):
    s,rt,c,identity=fixture(tmp_path)
    original=ChartStore.save
    def saved_then_failed(charts,*args,**kwargs):
        original(charts,*args,**kwargs)
        raise OSError('lost response')
    with patch.object(ChartStore,'save',saved_then_failed):
        with pytest.raises(OSError):publish(s,rt,c,identity)
    frozen=s.read(identity)['state']['publication']
    result=publish(s,rt,c,identity)
    assert result['chart_id']==frozen['id'] and len(list(ChartStore(rt).root.glob('*.json')))==1


def test_failed_final_acknowledgment_recovers_same_chart(tmp_path):
    s,rt,c,identity=fixture(tmp_path);original=s.replace
    def replace(key,state,**kwargs):
        if state.get('published'):raise OSError('checkpoint interrupted')
        return original(key,state,**kwargs)
    with patch.object(s,'replace',side_effect=replace):
        with pytest.raises(OSError):publish(s,rt,c,identity)
    frozen=s.read(identity)['state']['publication']
    assert publish(s,rt,c,identity)['chart_id']==frozen['id']
    assert len(list(ChartStore(rt).root.glob('*.json')))==1


def test_permission_revocation_after_publication_withholds_saved_result(tmp_path):
    s,rt,c,identity=fixture(tmp_path);publish(s,rt,c,identity)
    rt.validate_result_binding=lambda *_:(_ for _ in ()).throw(PermissionError('Revoked'))
    with pytest.raises(PermissionError,match='Revoked'):publish(s,rt,c,identity)


def test_changed_connection_or_owner_cannot_adopt_run(tmp_path):
    s,rt,c,identity=fixture(tmp_path)
    rt.result_binding=lambda:{'generation':'two','base_url':'https://fixture.test','moodle_user_id':3}
    with pytest.raises(PermissionError,match='another connection'):publish(s,rt,c,identity)
    assert not list((tmp_path/'moodle'/'charts').glob('**/*.json'))


def test_unfinished_run_cannot_publish_even_if_marked_done_incorrectly(tmp_path):
    s,rt,c,identity=fixture(tmp_path);record=s.read(identity);state=record['state']
    state['cursor']['next_student']=3
    s.replace(identity,state,expected_revision=record['revision'])
    with pytest.raises(ValueError,match='not finished'):publish(s,rt,c,identity)
    assert not list((tmp_path/'moodle'/'charts').glob('**/*.json'))


@pytest.mark.parametrize('defect',[None,'missing','boolean','state_total','overall_total','unknown_total'])
def test_overall_cross_tab_projection_checks_marginals_and_strips_extras(tmp_path,defect):
    s,rt,c,identity=fixture(tmp_path);record=s.read(identity);state=record['state']
    matrix={key:{'true':int(key!='incomplete'),'false':int(key=='incomplete'),'unknown':0,
        'actor_id':'PRIVATE_ACTOR'} for key in ('incomplete','complete','complete_pass','complete_fail')}
    matrix['private_students']=['PRIVATE_STUDENT']
    if defect=='missing':matrix['complete'].pop('unknown')
    if defect=='boolean':matrix['complete']['true']=True
    if defect=='state_total':matrix['complete']['true']=2
    if defect=='overall_total':matrix['complete'].update(true=0,false=1)
    if defect=='unknown_total':matrix['incomplete'].update(false=0,unknown=1)
    state['cursor']['rows'][0]['overall_by_state']=matrix
    s.replace(identity,state,expected_revision=record['revision'])
    if defect:
        with pytest.raises(ValueError,match='breakdown'):publish(s,rt,c,identity)
        assert not list((tmp_path/'moodle'/'charts').glob('**/*.json'))
    else:
        result=publish(s,rt,c,identity)
        assert result['rows'][0]['overall_by_state']['complete_fail']['true']==1
        assert 'PRIVATE_' not in json.dumps(result)
