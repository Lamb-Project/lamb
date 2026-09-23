import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.gradebook_tasks import execute
from lamb.moodle.forum_activity import TaskCancelled
from lamb.moodle.charts import ChartStore
from tests.test_moodle_gradebook_run import store, Client, context


def setup(tmp_path):
    s=store(tmp_path); c=Client()
    binding={'generation':'one','base_url':'https://fixture.test','moodle_user_id':3}
    rt=SimpleNamespace(cache_root=tmp_path/'moodle',store=SimpleNamespace(organization_id=1,owner_id=2),
        result_binding=lambda:dict(binding),validate_result_binding=lambda *args:None)
    def full_context(*args):
        value=context(*args)
        return dict(value,candidates=value['students'],excluded_students=[],
            candidate_basis='current_active_enrolments_with_role_shortname_student',
            population_basis='active_candidate_population_manual_item')
    def call(key,**params):
        with patch('lamb.moodle.analytics.gradebook_tasks.GradebookCheckpoints',return_value=s), \
                patch('lamb.moodle.analytics.gradebook_tasks.authorize',side_effect=lambda *a:c.checkpoint()), \
                patch('lamb.moodle.analytics.gradebook_run.gradebook_context',side_effect=full_context):
            return execute(rt,None,c,3,key,params)
    initial=call('analytics.start',course_id=7,grade_item_ids=[2,3],group_id=0,language='en',tz='UTC')
    return s,rt,c,call,initial


def test_exact_replay_and_single_publication_without_private_rows(tmp_path):
    s,rt,c,call,initial=setup(tmp_path)
    responses=[initial]
    for step in range(6):
        response=call('analytics.continue',run_id=initial['run_id'],step=step)
        count=len(c.calls)
        assert call('analytics.continue',run_id=initial['run_id'],step=step)==response
        assert len(c.calls)==count
        responses.append(response)
    assert response['chart_id']
    assert len(list(ChartStore(rt).root.glob('*.json')))==1
    listing=call('analytics.runs')
    assert listing['items'][0]['status']=='published'
    assert len(listing['items'][0]['gradebook_scopes'])==2
    for private in ('userid','students": [','fingerprint','rawgrade','timemodified'):
        assert private not in json.dumps(responses+[listing])


def test_interrupted_step_keeps_original_page_target(tmp_path):
    s,rt,c,call,initial=setup(tmp_path)
    c.fail=2
    with pytest.raises(TaskCancelled):call('analytics.continue',run_id=initial['run_id'],step=0)
    assert s.read(initial['run_id'])['state']['pages']==2
    c.fail=None
    response=call('analytics.continue',run_id=initial['run_id'],step=0)
    assert response['processed_grade_records']==5
    assert s.read(initial['run_id'])['state']['pages']==5


@pytest.mark.parametrize('step',[0,1,4,5])
def test_lost_ack_does_not_advance_pages_item_or_verification_phase(tmp_path,step):
    s,rt,c,call,initial=setup(tmp_path)
    for previous in range(step):call('analytics.continue',run_id=initial['run_id'],step=previous)
    original=s.replace
    def fail_ack(identity,state,**kwargs):
        if str(step) in state.get('step_results',{}):raise OSError('Lost acknowledgement')
        return original(identity,state,**kwargs)
    with patch.object(s,'replace',side_effect=fail_ack),pytest.raises(OSError):
        call('analytics.continue',run_id=initial['run_id'],step=step)
    state=s.read(initial['run_id'])['state']
    count=len(c.calls)
    response=call('analytics.continue',run_id=initial['run_id'],step=step)
    after=s.read(initial['run_id'])['state']
    assert (after['pages'],after['index'],after['phase'])==(state['pages'],state['index'],state['phase'])
    assert len(c.calls)==count
    assert response.get('chart_id') if step==5 else response['status']=='running'


def test_revocation_blocks_replay_and_listing(tmp_path):
    s,rt,c,call,initial=setup(tmp_path)
    call('analytics.continue',run_id=initial['run_id'],step=0)
    c.denied=True
    with pytest.raises(PermissionError):call('analytics.continue',run_id=initial['run_id'],step=0)
    with pytest.raises(PermissionError):call('analytics.runs')


@pytest.mark.parametrize('step',[True,-1,3,'0'])
def test_invalid_step_no_collection(tmp_path,step):
    s,rt,c,call,initial=setup(tmp_path)
    with pytest.raises(ValueError):call('analytics.continue',run_id=initial['run_id'],step=step)
    assert c.calls==[]
