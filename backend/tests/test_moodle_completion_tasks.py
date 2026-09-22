from types import SimpleNamespace
from unittest.mock import patch
import json
import pytest

from lamb.moodle.analytics.completion_tasks import execute
from lamb.moodle.analytics.completion_run import advance as real_advance
from lamb.moodle.analytics.checkpoints import CompletionCheckpoints
from lamb.moodle.results import ResultStore
from lamb.moodle.contract import prepare_moodle
from tests.test_moodle_completion_run import Client, context


def fixture(tmp_path):
    results=ResultStore(1,2,base_url='https://fixture.test',moodle_user_id=3,generation='one',root=tmp_path/'moodle')
    runtime=SimpleNamespace(cache_root=tmp_path/'moodle',store=SimpleNamespace(organization_id=1,owner_id=2))
    return results,runtime,Client()


@pytest.fixture
def authority():
    with patch('lamb.moodle.analytics.completion_tasks.MoodleScope'), \
         patch('lamb.moodle.analytics.completion_tasks.validate_completion_scope'), \
         patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=context):yield


def begin(rt,results,c):
    return execute(rt,results,c,3,'analytics.start',{'course_id':7,'language':'es','tz':'Europe/Madrid'})


def test_start_listing_progress_and_exact_step_retry_are_minimized(tmp_path,authority):
    results,rt,c=fixture(tmp_path);initial=begin(rt,results,c)
    assert initial['processed_students']==0 and initial['population_students'] is None
    assert initial['remaining_students'] is None and initial['remaining_collection_steps'] is None
    params={'run_id':initial['run_id'],'step':0}
    first=execute(rt,results,c,3,'analytics.continue',params)
    assert first['processed_students']==25 and first['population_students']==500
    assert first['remaining_students']==475 and first['remaining_collection_steps']==19
    before=len(c.calls)
    assert execute(rt,results,c,3,'analytics.continue',params)==first
    assert len(c.calls)==before
    listed=execute(rt,results,c,3,'analytics.runs',{})['items']
    assert listed[0]['continue_command'].endswith('--step 1')
    assert listed[0]['completion_scopes']==[{'course_id':7,'module_ids':[10]}]
    for forbidden in ('"students":','"cursor":','"rows":','fingerprint','publication'):
        assert forbidden not in json.dumps([initial,first,listed])


def test_lost_executor_response_does_not_collect_another_batch(tmp_path,authority):
    results,rt,c=fixture(tmp_path);initial=begin(rt,results,c);params={'run_id':initial['run_id'],'step':0}
    def fail_after(*args,**kwargs):
        real_advance(*args,**kwargs)
        raise OSError('lost response')
    with patch('lamb.moodle.analytics.completion_tasks.advance',side_effect=fail_after):
        with pytest.raises(OSError):execute(rt,results,c,3,'analytics.continue',params)
    before=len(c.calls)
    recovered=execute(rt,results,c,3,'analytics.continue',params)
    assert recovered['processed_students']==25 and len(c.calls)==before


def test_interrupted_public_step_keeps_its_original_target(tmp_path,authority):
    from lamb.moodle.forum_activity import TaskCancelled
    results,rt,c=fixture(tmp_path);initial=begin(rt,results,c);params={'run_id':initial['run_id'],'step':0}
    c.fail_at=4
    with pytest.raises(TaskCancelled):execute(rt,results,c,3,'analytics.continue',params)
    c.fail_at=None
    recovered=execute(rt,results,c,3,'analytics.continue',params)
    assert recovered['processed_students']==25


def test_revocation_omits_runs_and_blocks_cached_step(tmp_path,authority):
    results,rt,c=fixture(tmp_path);initial=begin(rt,results,c);params={'run_id':initial['run_id'],'step':0}
    execute(rt,results,c,3,'analytics.continue',params)
    with patch('lamb.moodle.analytics.completion_tasks.validate_completion_scope',side_effect=PermissionError('Revoked')):
        assert execute(rt,results,c,3,'analytics.runs',{})['items']==[]
        with pytest.raises(PermissionError):execute(rt,results,c,3,'analytics.continue',params)


def test_wrong_step_does_not_collect(tmp_path,authority):
    results,rt,c=fixture(tmp_path);initial=begin(rt,results,c)
    with pytest.raises(ValueError,match='exact continuation'):
        execute(rt,results,c,3,'analytics.continue',{'run_id':initial['run_id'],'step':9})
    assert not c.calls


def test_new_command_contracts_validate_scope_timezone_and_step():
    key,params=prepare_moodle('moodle analytics start activity-completion --course 7 --tz Europe/Madrid --language ca')
    assert key.key=='analytics.start' and params['language']=='ca'
    assert prepare_moodle('moodle analytics runs')[0].key=='analytics.runs'
    for command in ('moodle analytics start resource-reach --course 7',
        'moodle analytics start activity-completion --course 7 --tz invalid',
        'moodle analytics continue ../bad --step 0',
        'moodle analytics continue 12345678-1234-1234-1234-123456789abc',
        'moodle analytics continue 12345678-1234-1234-1234-123456789abc --step -1'):
        with pytest.raises(ValueError):prepare_moodle(command)


def test_multiple_public_steps_publish_one_chart_and_preserve_old_step_retry(tmp_path,authority):
    from lamb.moodle.charts import ChartStore
    results,rt,c=fixture(tmp_path)
    rt.result_binding=lambda:{'generation':'one','base_url':'https://fixture.test','moodle_user_id':3}
    rt.validate_result_binding=lambda *args:None
    def source_context(*args,**kwargs):
        value=context(*args,**kwargs)
        value['cursor']['students']=list(range(1,27))
        value['population']['student_rows']=26
        value['cursor']['rows'][0].update(name='Activity',population_students=26,
            availability_configured=False,learner_eligibility='not_collected')
        return value
    initial=begin(rt,results,c);identity=initial['run_id']
    with patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=source_context):
        first=execute(rt,results,c,3,'analytics.continue',{'run_id':identity,'step':0})
        final=execute(rt,results,c,3,'analytics.continue',{'run_id':identity,'step':1})
        assert execute(rt,results,c,3,'analytics.continue',{'run_id':identity,'step':0})==first
        assert execute(rt,results,c,3,'analytics.continue',{'run_id':identity,'step':1})==final
    assert first['processed_students']==25 and 'chart_id' not in first
    assert first['remaining_students']==1 and first['remaining_collection_steps']==1
    assert final['rows'][0]['population_students']==26
    assert [final['rows'][0][key] for key in ('incomplete','complete','complete_pass','complete_fail')]==[7,7,6,6]
    assert len(list(ChartStore(rt).root.glob('*.json')))==1
    item=execute(rt,results,c,3,'analytics.runs',{})['items'][0]
    assert item['status']=='published' and item['continue_command'] is None
