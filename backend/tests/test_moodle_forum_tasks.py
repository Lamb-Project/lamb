import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.forum_tasks import execute, authorize, evidence_scope
from lamb.moodle.charts import ChartStore
from lamb.moodle.forum_activity import TaskCancelled
from tests.test_moodle_forum_run import Client, context
from tests.test_moodle_forum_checkpoints import store


def setup(tmp_path,recipe='forum-participation'):
    s=store(tmp_path);c=Client()
    binding=dict(generation='one',base_url='https://fixture.test',moodle_user_id=3)
    rt=SimpleNamespace(cache_root=tmp_path/'moodle',store=SimpleNamespace(organization_id=1,owner_id=2),
        result_binding=lambda:dict(binding),validate_result_binding=lambda *a:None)
    def call(key,**params):
        with patch('lamb.moodle.analytics.forum_tasks.ForumCheckpoints',return_value=s), \
             patch('lamb.moodle.analytics.forum_tasks.authorize',side_effect=lambda *a:c.checkpoint()), \
             patch('lamb.moodle.analytics.forum_run.forum_context',side_effect=context):
            return execute(rt,None,c,3,key,params)
    initial=call('analytics.start',course_id=7,forum_id=8,group_id=0,since=100,until=150,
                 recipe=recipe,language='en',tz='UTC')
    return s,rt,c,call,initial


@pytest.mark.parametrize('recipe',['forum-participation','forum-discussions'])
def test_exact_step_replay_and_publication(tmp_path,recipe):
    s,rt,c,call,initial=setup(tmp_path,recipe)
    identity=initial['run_id']
    first=call('analytics.continue',run_id=identity,step=0)
    assert first['processed_post_records']==5 and first['completed_discussions']==1
    count=len(c.calls)
    assert call('analytics.continue',run_id=identity,step=0)==first
    assert len(c.calls)==count
    final=call('analytics.continue',run_id=identity,step=1)
    assert final['recipe']['id']==recipe
    assert call('analytics.continue',run_id=identity,step=1)==final
    listing=call('analytics.runs')
    assert listing['items'][0]['status']=='published'
    assert len(list(ChartStore(rt).root.glob('*.json')))==1
    for private in ('student_id','author_id','fingerprint','threads','"records"'):
        assert private not in json.dumps([initial,first,listing])


def test_interrupted_step_and_lost_ack_keep_batch_target(tmp_path):
    s,rt,c,call,initial=setup(tmp_path);identity=initial['run_id']
    c.fail=(9,2)
    with pytest.raises(TaskCancelled):call('analytics.continue',run_id=identity,step=0)
    assert s.read(identity)['state']['pages']==2
    c.fail=None
    original=s.replace
    def fail_ack(identity,state,**kw):
        if state.get('step_results'):raise OSError('lost acknowledgement')
        return original(identity,state,**kw)
    with patch.object(s,'replace',side_effect=fail_ack),pytest.raises(OSError):
        call('analytics.continue',run_id=identity,step=0)
    assert s.read(identity)['state']['pages']==5
    result=call('analytics.continue',run_id=identity,step=0)
    assert result['processed_post_records']==5


def test_revocation_denies_saved_step_and_inventory(tmp_path):
    s,rt,c,call,initial=setup(tmp_path)
    call('analytics.continue',run_id=initial['run_id'],step=0)
    c.denied=True
    with pytest.raises(PermissionError):call('analytics.continue',run_id=initial['run_id'],step=0)
    with pytest.raises(PermissionError):call('analytics.runs')


@pytest.mark.parametrize('step',[True,-1,3,'0'])
def test_bad_step_never_collects(tmp_path,step):
    s,rt,c,call,initial=setup(tmp_path)
    with pytest.raises(ValueError):call('analytics.continue',run_id=initial['run_id'],step=step)
    assert not c.calls


def test_authorize_checks_every_inventory_discussion_without_post_collection():
    c=Client()
    state={'scope':dict(course_id=7,forum_id=8,group_id=0),
           'context':{'discussions':[{'discussion_id':10},{'discussion_id':9}]}}
    expected=dict(state['scope'],discussion_ids=[9,10])
    assert evidence_scope(state)==expected
    with patch('lamb.moodle.analytics.forum_tasks.validate_forum_evidence_scope') as check, \
         patch('lamb.moodle.analytics.forum_tasks.MoodleScope') as role:
        authorize(c,3,state)
        check.assert_called_once_with(c,expected)
        role.return_value.require_teacher.assert_called_once_with(7)
    assert c.calls==[]


def test_command_lock_prevents_duplicate_execution(tmp_path):
    from lamb.private_storage import file_lock
    s,rt,c,call,initial=setup(tmp_path)
    with file_lock(s.folder/'commands',blocking=False),pytest.raises(ValueError,match='busy'):
        call('analytics.continue',run_id=initial['run_id'],step=0)
    assert c.calls==[]
