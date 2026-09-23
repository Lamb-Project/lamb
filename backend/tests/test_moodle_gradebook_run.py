from unittest.mock import patch
import pytest
from lamb.moodle.analytics.gradebook_run import GradebookCheckpoints, start, advance
from lamb.moodle.analytics.client import GRADEBOOK_GRADES_FUNCTION
from lamb.moodle.results import ResultStore
from lamb.moodle.forum_activity import TaskCancelled, TaskLimit
from lamb.storage_lifecycle import OwnerStorage
from tests.test_moodle_gradebook_state import page


def store(tmp_path, **changes):
    params = dict(organization_id=1,owner_id=2,base_url='https://fixture.test',
        moodle_user_id=3,generation='one',root=tmp_path/'moodle')
    params.update(changes)
    return GradebookCheckpoints(ResultStore(**params))


class Client:
    before_request = None
    denied = False
    fail = None

    def __init__(self):
        self.calls = []

    def checkpoint(self):
        if self.denied:
            raise PermissionError('Revoked')

    def call(self, function, **params):
        self.checkpoint()
        if self.before_request:
            self.before_request()
        self.calls.append((function,params))
        if function != GRADEBOOK_GRADES_FUNCTION:
            return None
        after = params['afterid']
        if self.fail == after:
            raise TaskCancelled('Stop')
        result = page((after+1,),upper=6,more=after<5)
        result['gradeitemid'] = result['item']['id'] = params['gradeitemid']
        return result


def context(client, owner, scope):
    client.call('verify')
    return {'students':list(range(11,17)), 'fingerprint':'stable'}


def test_disk_resume_multi_item_and_final_revalidation(tmp_path):
    identity = start(store(tmp_path),7,[2,3])['id']
    c = Client()
    with patch('lamb.moodle.analytics.gradebook_run.gradebook_context',side_effect=context):
        first = advance(store(tmp_path),c,3,identity)['state']
        assert first['items'][0]['cursor']['afterid']==5 and not first['done']
        for _ in range(5):
            state = advance(store(tmp_path),c,3,identity)['state']
        assert state['done'] and state['pages']==12 and state['phase']=='done'
        assert [len(i['cursor']['records']) for i in state['items']] == [6,6]
        retry = advance(store(tmp_path),c,3,identity)['state']
        assert retry['completed_at']==state['completed_at'] and retry['items']==state['items']
        assert retry['calls']==state['calls']+2
    assert c.before_request is None


def test_interruption_revocation_and_resume(tmp_path):
    s=store(tmp_path); identity=start(s,7,[2,3])['id']; c=Client(); c.fail=2
    with patch('lamb.moodle.analytics.gradebook_run.gradebook_context',side_effect=context):
        with pytest.raises(TaskCancelled):advance(s,c,3,identity)
        assert s.read(identity)['state']['items'][0]['cursor']['afterid']==2
        assert c.before_request is None
        c.denied=True
        before=len(c.calls)
        with pytest.raises(PermissionError):advance(s,c,3,identity)
        assert len(c.calls)==before
        c.denied=False; c.fail=None
        for _ in range(6):
            state=advance(store(tmp_path),c,3,identity)['state']
            if state['done']:break
        assert state['done']


def test_population_drift_withholds_completion(tmp_path):
    s=store(tmp_path); identity=start(s,7,[2,3])['id']; c=Client(); count=0
    def drift(*args):
        nonlocal count
        count+=1
        return dict(context(*args),fingerprint='stable' if count==1 else 'changed')
    with patch('lamb.moodle.analytics.gradebook_run.gradebook_context',side_effect=drift):
        with pytest.raises(ValueError,match='population changed'):advance(s,c,3,identity)
    assert not s.read(identity)['state']['done'] and c.before_request is None


def test_request_and_step_budgets_and_executor_lock(tmp_path):
    s=store(tmp_path); identity=start(s,7,[2,3])['id']; c=Client()
    with s.execution_lock(), pytest.raises(ValueError,match='busy'):advance(s,c,3,identity)
    with patch('lamb.moodle.analytics.gradebook_run.MAX_RUN_STEPS',0), pytest.raises(TaskLimit):
        advance(s,c,3,identity)
    assert c.calls==[]
    with patch('lamb.moodle.analytics.gradebook_run.gradebook_context',side_effect=context), \
            patch('lamb.moodle.analytics.gradebook_run.MAX_RUN_CALLS',3):
        with pytest.raises(TaskLimit,match='request_limit'):advance(s,c,3,identity)
    assert s.read(identity)['state']['calls']==len(c.calls)==3
    assert c.before_request is None


def test_owner_generation_quota_and_lifecycle(tmp_path):
    s=store(tmp_path)
    with patch('lamb.moodle.analytics.checkpoints.time.time',return_value=100):
        expired=start(s,7,[2,3])
    live=start(s,7,[2,3])
    with pytest.raises(PermissionError):store(tmp_path,generation='other').read(live['id'])
    inventory=OwnerStorage(1,2,root=tmp_path).inspect()['stores']['gradebook_runs']
    assert inventory['records']==2 and inventory['quota_bytes']==32*1024*1024
    OwnerStorage(1,2,root=tmp_path).clean()
    assert not s._path(expired['id']).exists() and s.read(live['id'])==live


def test_final_pass_detects_earlier_item_population_change(tmp_path):
    s=store(tmp_path); identity=start(s,7,[2,3])['id']; c=Client()
    with patch('lamb.moodle.analytics.gradebook_run.gradebook_context',side_effect=context):
        for _ in range(4):state=advance(s,c,3,identity)['state']
    assert state['phase']=='verify' and not state['done']
    with patch('lamb.moodle.analytics.gradebook_run.gradebook_context',
               side_effect=lambda *args:dict(context(*args),fingerprint='changed')):
        with pytest.raises(ValueError,match='population changed'):advance(s,c,3,identity)
    assert not s.read(identity)['state']['done']


def test_existing_request_guard_is_never_replaced(tmp_path):
    s=store(tmp_path); identity=start(s,7,[2,3])['id']; c=Client()
    guard=lambda:None
    c.before_request=guard
    with pytest.raises(ValueError,match='existing request guard'):advance(s,c,3,identity)
    assert c.before_request is guard and not c.calls


@pytest.mark.parametrize('ids', [[2],[2,2],[True,3],list(range(1,22)),['2',3]])
def test_explicit_selection_required(tmp_path,ids):
    with pytest.raises(ValueError):start(store(tmp_path),7,ids)
