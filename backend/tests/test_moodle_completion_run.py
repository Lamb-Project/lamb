from copy import deepcopy
from unittest.mock import patch
import pytest

from lamb.moodle.analytics.completion_run import start, advance
from lamb.moodle.analytics.completion_state import initial_cursor
from lamb.moodle.forum_activity import TaskCancelled, TaskLimit
from tests.test_moodle_completion_checkpoints import store
from tests.test_moodle_completion_state import row


class Client:
    before_request=None
    fail_at=None
    denied=False
    calls=[]
    def __init__(self):self.calls=[]
    def checkpoint(self):
        if self.denied:raise PermissionError('Revoked')
    def call(self, function, **params):
        self.checkpoint()
        if self.before_request:self.before_request()
        self.calls.append((function,params))
        if self.fail_at is not None and params.get('userid')==self.fail_at:raise TaskCancelled('Stop')
        state=(params.get('userid',1)-1)%4
        return {'statuses':[{'cmid':10,'tracking':2,'state':state,'istrackeduser':True,
            'isoverallcomplete':state!=0,'overrideby':None}], 'warnings':[]}


def context(client,owner,course,*,student_limit):
    client.call('verify_scope')
    return {'course_id':course,'course_name':'Fixture','population':{'student_rows':500},
        'disabled':0,'fingerprint':'stable','cursor':initial_cursor(range(1,501),[row(10)])}


def test_500_learner_execution_resumes_with_exact_counts_and_request_accounting(tmp_path):
    s=store(tmp_path);identity=start(s,7)['id'];c=Client()
    with patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=context):
        for step in range(20):
            result=advance(store(tmp_path),c,3,identity)
            assert result['state']['cursor']['next_student']==(step+1)*25
    state=result['state'];counts=state['cursor']['rows'][0]
    assert state['done'] and state['calls']==540 and state['steps']==20
    assert [counts[k] for k in ('incomplete','complete','complete_pass','complete_fail')]==[125]*4
    assert counts['overall_complete']==375 and c.before_request is None


def test_interruption_recovers_only_unacknowledged_learner(tmp_path):
    s=store(tmp_path);identity=start(s,7)['id'];c=Client();c.fail_at=4
    with patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=context):
        with pytest.raises(TaskCancelled):advance(s,c,3,identity)
        saved=s.read(identity)['state']
        assert saved['cursor']['next_student']==3 and saved['calls']==5
        assert c.before_request is None
        c.fail_at=None
        result=advance(s,c,3,identity)['state']
    assert result['cursor']['next_student']==28
    assert [p['userid'] for f,p in c.calls if 'userid' in p].count(4)==2
    assert sum(result['cursor']['rows'][0][k] for k in ('incomplete','complete','complete_pass','complete_fail'))==28


def test_revoked_permission_prevents_retained_counts_return_and_source_reads(tmp_path):
    s=store(tmp_path);identity=start(s,7)['id'];c=Client()
    with patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=context):
        advance(s,c,3,identity);before=len(c.calls);c.denied=True
        with pytest.raises(PermissionError):advance(s,c,3,identity)
    assert len(c.calls)==before and c.before_request is None


def test_inventory_drift_rejects_before_more_completion_reads(tmp_path):
    s=store(tmp_path);identity=start(s,7)['id'];c=Client()
    with patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=context):advance(s,c,3,identity)
    before=deepcopy(s.read(identity)['state']['cursor'])
    def changed(*args,**kwargs):return dict(context(*args,**kwargs),fingerprint='different')
    with patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=changed):
        with pytest.raises(ValueError,match='inventory changed'):advance(s,c,3,identity)
    assert s.read(identity)['state']['cursor']==before and c.calls[-1][0]=='verify_scope'


def test_inventory_change_at_end_withholds_success_and_done_flag(tmp_path):
    s=store(tmp_path);identity=start(s,7)['id'];c=Client();checks=0
    def changed(*args,**kwargs):
        nonlocal checks
        checks+=1
        return dict(context(*args,**kwargs),fingerprint='stable' if checks==1 else 'changed')
    with patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=changed):
        with pytest.raises(ValueError,match='inventory changed'):advance(s,c,3,identity)
    state=s.read(identity)['state']
    assert not state['done'] and state['cursor']['next_student']==25


def test_run_request_limit_is_persisted_before_network_and_restores_guard(tmp_path):
    s=store(tmp_path);identity=start(s,7)['id'];c=Client()
    with patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=context), \
         patch('lamb.moodle.analytics.completion_run.MAX_RUN_CALLS',3):
        with pytest.raises(TaskLimit,match='request_limit'):advance(s,c,3,identity)
    state=s.read(identity)['state']
    assert state['calls']==3 and state['cursor']['next_student']==2
    assert len(c.calls)==3 and c.before_request is None


def test_completed_retry_revalidates_without_recollecting(tmp_path):
    s=store(tmp_path);identity=start(s,7)['id'];c=Client()
    def small(*args,**kwargs):
        value=context(*args,**kwargs);value['cursor']=initial_cursor([1],[row(10)])
        return value
    with patch('lamb.moodle.analytics.completion_run.completion_context',side_effect=small):
        original=advance(s,c,3,identity)['state'];before=len(c.calls)
        final=advance(s,c,3,identity)['state']
    assert original['done'] and final['cursor']==original['cursor']
    assert final['completed_at']==original['completed_at'] and len(c.calls)==before+1


def test_step_limit_and_execution_lock_prevent_more_remote_work(tmp_path):
    s=store(tmp_path);identity=start(s,7)['id'];c=Client()
    with s.execution_lock():
        with pytest.raises(ValueError,match='busy'):advance(s,c,3,identity)
    with patch('lamb.moodle.analytics.completion_run.MAX_RUN_STEPS',0):
        with pytest.raises(TaskLimit,match='step_limit'):advance(s,c,3,identity)
    assert not c.calls
