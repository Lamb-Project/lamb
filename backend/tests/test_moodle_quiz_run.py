from unittest.mock import patch
import pytest
from lamb.moodle.analytics.quiz_run import QuizCheckpoints, start, advance
from lamb.moodle.analytics.client import QUIZ_ATTEMPTS_FUNCTION
from lamb.moodle.results import ResultStore
from lamb.moodle.forum_activity import TaskCancelled, TaskLimit
from lamb.storage_lifecycle import OwnerStorage
from tests.test_moodle_quiz_state import page


def store(tmp_path, **changes):
    params = dict(organization_id=1, owner_id=2, base_url='https://fixture.test',
                  moodle_user_id=3, generation='one', root=tmp_path/'moodle')
    params.update(changes)
    return QuizCheckpoints(ResultStore(**params))


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
        self.calls.append((function, params))
        if function != QUIZ_ATTEMPTS_FUNCTION:
            return None
        after = params['afterid']
        if self.fail == after:
            raise TaskCancelled('Stop')
        result = page((after+1,))
        result.update(throughid=6, has_more=after < 5)
        return result


def context(client, owner, scope):
    client.call('verify')
    return {'students': list(range(101, 107)), 'population': {'student_rows': 6}, 'fingerprint': 'stable'}


def test_bounded_disk_resume_and_completed_retry(tmp_path):
    s = store(tmp_path)
    identity = start(s, 9, 7, policy='all_finished')['id']
    c = Client()
    with patch('lamb.moodle.analytics.quiz_run.quiz_context', side_effect=context):
        first = advance(s, c, 3, identity)['state']
        assert not first['done'] and first['cursor']['afterid'] == 5 and first['calls'] == 7
        final = advance(store(tmp_path), c, 3, identity)['state']
        assert final['done'] and len(final['cursor']['records']) == 6 and final['calls'] == 10
        again = advance(store(tmp_path), c, 3, identity)['state']
    assert again['completed_at'] == final['completed_at'] and again['cursor'] == final['cursor']
    assert again['calls'] == 11 and c.before_request is None


def test_interruption_and_revocation_preserve_acknowledged_rows(tmp_path):
    s = store(tmp_path); identity = start(s, 9, 7, policy='first_finished')['id']; c = Client()
    c.fail = 2
    with patch('lamb.moodle.analytics.quiz_run.quiz_context', side_effect=context):
        with pytest.raises(TaskCancelled):
            advance(s, c, 3, identity)
        assert s.read(identity)['state']['cursor']['afterid'] == 2
        assert c.before_request is None
        c.denied = True
        count = len(c.calls)
        with pytest.raises(PermissionError):
            advance(s, c, 3, identity)
        assert len(c.calls) == count
        c.denied = False; c.fail = None
        final = advance(s, c, 3, identity)['state']
    assert final['done'] and len(final['cursor']['records']) == 6


def test_population_drift_after_collection_withholds_completion(tmp_path):
    s = store(tmp_path); identity = start(s, 9, 7, policy='first_finished')['id']; c = Client()
    calls = 0
    def drift(*args):
        nonlocal calls
        calls += 1
        return dict(context(*args), fingerprint='stable' if calls == 1 else 'changed')
    with patch('lamb.moodle.analytics.quiz_run.quiz_context', side_effect=drift):
        with pytest.raises(ValueError, match='population changed'):
            advance(s, c, 3, identity)
    assert not s.read(identity)['state']['done'] and c.before_request is None


def test_request_budget_is_saved_before_network_and_guard_restored(tmp_path):
    s = store(tmp_path); identity = start(s, 9, 7, policy='first_finished')['id']; c = Client()
    with patch('lamb.moodle.analytics.quiz_run.quiz_context', side_effect=context), \
            patch('lamb.moodle.analytics.quiz_run.MAX_RUN_CALLS', 3):
        with pytest.raises(TaskLimit, match='request_limit'):
            advance(s, c, 3, identity)
    state = s.read(identity)['state']
    assert state['calls'] == len(c.calls) == 3 and state['cursor']['afterid'] == 2
    assert c.before_request is None


def test_quiz_storage_is_separate_owner_bound_and_expires(tmp_path):
    s = store(tmp_path)
    with patch('lamb.moodle.analytics.checkpoints.time.time', return_value=100):
        expired = start(s, 9, 7, policy='first_finished')
    live = start(s, 9, 7, policy='first_finished')
    with pytest.raises(PermissionError):
        store(tmp_path, generation='other').read(live['id'])
    from tests.test_moodle_completion_checkpoints import store as completion_store
    with pytest.raises(PermissionError):
        completion_store(tmp_path).read(live['id'])
    inventory = OwnerStorage(1, 2, root=tmp_path).inspect()['stores']['quiz_runs']
    assert inventory['records'] == 2 and inventory['quota_bytes'] == 16*1024*1024
    OwnerStorage(1, 2, root=tmp_path).clean()
    assert not s._path(expired['id']).exists() and s.read(live['id']) == live


def test_lock_and_step_limit_prevent_remote_calls(tmp_path):
    s = store(tmp_path); identity = start(s, 9, 7, policy='first_finished')['id']; c = Client()
    with s.execution_lock(), pytest.raises(ValueError, match='busy'):
        advance(s, c, 3, identity)
    with patch('lamb.moodle.analytics.quiz_run.MAX_RUN_STEPS', 0), pytest.raises(TaskLimit):
        advance(s, c, 3, identity)
    assert c.calls == []


def test_maximum_record_population_fits_bounded_storage(tmp_path):
    s = store(tmp_path)
    rows = page()['attempts'][:1] * 10000
    saved = s.create({'records': rows})
    assert len(s.read(saved['id'])['state']['records']) == 10000
    for _ in range(3):
        s.create({})
    with pytest.raises(ValueError, match='quota'):
        s.create({})
    with pytest.raises(ValueError, match='storage limit'):
        s.replace(saved['id'], {'oversize': 'x' * s.max_bytes}, expected_revision=0)
    assert s.read(saved['id']) == saved
