from unittest.mock import patch
import pytest
from lamb.moodle.analytics.forum_run import start, advance
from lamb.moodle.analytics.client import FORUM_POSTS_FUNCTION
from lamb.moodle.forum_activity import TaskCancelled, TaskLimit
from tests.test_moodle_forum_checkpoints import store
from tests.test_moodle_forum_state import page


class Client:
    before_request = None
    fail = None
    denied = False

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
        if function != FORUM_POSTS_FUNCTION:
            return
        after = params['afterid']
        if self.fail == (params['discussionid'], after):
            raise TaskCancelled('Stop')
        offset = (params['discussionid']-9)*10
        identity = after+1 if after else offset+1
        result = page((identity,), through=offset+3, more=identity<offset+3)
        result['discussionid'] = params['discussionid']
        result['posts'][0]['parent_id'] = None if identity == offset+1 else offset+1
        return result


def context(client, owner, scope):
    client.call('verify')
    return {'students': [10,11], 'population': {}, 'fingerprint': 'stable',
            'discussions': [{'discussion_id':9,'root_post_id':1},
                            {'discussion_id':10,'root_post_id':11}]}


@pytest.fixture
def setup(tmp_path):
    s = store(tmp_path)
    identity = start(s,7,8,since=100,until=150)['id']
    with patch('lamb.moodle.analytics.forum_run.forum_context', side_effect=context):
        yield s, identity, Client()


def test_disk_resume_across_discussions_and_completed_retry(setup, tmp_path):
    s, identity, c = setup
    first = advance(s,c,2,identity)['state']
    assert first['pages'] == first['posts'] == 5
    assert len(first['threads']) == 1 and first['cursor']['afterid'] == 12
    final = advance(store(tmp_path),c,2,identity)['state']
    assert final['done'] and final['posts'] == 6 and len(final['threads']) == 2
    assert final['cursor'] is None and final['calls'] == 10
    again = advance(store(tmp_path),c,2,identity)['state']
    assert again['completed_at'] == final['completed_at'] and again['calls'] == 11
    assert c.before_request is None


def test_interruption_public_step_keeps_original_page_budget(setup, tmp_path):
    s, identity, c = setup
    r = s.read(identity); r['state']['active_public_step'] = 'one'
    s.replace(identity,r['state'],expected_revision=r['revision'])
    c.fail = (9,2)
    with pytest.raises(TaskCancelled): advance(s,c,2,identity)
    assert s.read(identity)['state']['posts'] == 2
    assert c.before_request is None
    c.fail = None
    recovered = advance(store(tmp_path),c,2,identity)['state']
    assert recovered['pages'] == 5 and not recovered['done']
    assert recovered['finished_public_step'] == 'one'
    assert advance(s,c,2,identity)['state']['pages'] == 5


def test_revocation_and_context_drift_withhold_completion(setup):
    s, identity, c = setup
    advance(s,c,2,identity)
    c.denied = True
    with pytest.raises(PermissionError): advance(s,c,2,identity)
    c.denied = False
    def changed(*args): return dict(context(*args),fingerprint='changed')
    with patch('lamb.moodle.analytics.forum_run.forum_context',side_effect=changed):
        with pytest.raises(ValueError,match='inventory changed'): advance(s,c,2,identity)
    assert s.read(identity)['state']['posts'] == 5


def test_request_budget_persisted_before_failure(setup):
    s, identity, c = setup
    with patch('lamb.moodle.analytics.forum_run.MAX_RUN_CALLS',3):
        with pytest.raises(TaskLimit): advance(s,c,2,identity)
    state = s.read(identity)['state']
    assert state['calls'] == len(c.calls) == 3 and state['posts'] == 2
    assert c.before_request is None


def test_global_post_bound_not_per_discussion(setup):
    s, identity, c = setup
    with patch('lamb.moodle.analytics.forum_run.MAX_POSTS',4):
        with pytest.raises(ValueError,match='post bound'): advance(s,c,2,identity)
    assert s.read(identity)['state']['posts'] == 4


def test_empty_inventory_requires_authorized_context(setup):
    s, identity, c = setup
    def empty(*args): return dict(context(*args),discussions=[])
    with patch('lamb.moodle.analytics.forum_run.forum_context',side_effect=empty):
        state = advance(s,c,2,identity)['state']
    assert state['done'] and state['posts'] == state['pages'] == 0
    assert len(c.calls) == 2


def test_root_mismatch_is_not_acknowledged(setup):
    s, identity, c = setup
    def mismatch(*args):
        result = context(*args); result['discussions'][0]['root_post_id'] = 99
        return result
    with patch('lamb.moodle.analytics.forum_run.forum_context',side_effect=mismatch):
        with pytest.raises(ValueError,match='root differs'): advance(s,c,2,identity)
    assert s.read(identity)['state']['posts'] == 2


def test_post_collection_drift_withholds_done(setup):
    s, identity, c = setup
    advance(s,c,2,identity)
    count = 0
    def drift(*args):
        nonlocal count
        count += 1
        return dict(context(*args), fingerprint='stable' if count == 1 else 'changed')
    with patch('lamb.moodle.analytics.forum_run.forum_context',side_effect=drift):
        with pytest.raises(ValueError,match='inventory changed'): advance(s,c,2,identity)
    state = s.read(identity)['state']
    assert state['posts'] == 6 and not state['done']
    assert c.before_request is None


def test_locks_limits_and_existing_guard_prevent_requests(setup):
    s, identity, c = setup
    with s.execution_lock(), pytest.raises(ValueError,match='busy'):
        advance(s,c,2,identity)
    with patch('lamb.moodle.analytics.forum_run.MAX_RUN_STEPS',0), pytest.raises(TaskLimit):
        advance(s,c,2,identity)
    guard = lambda: None
    c.before_request = guard
    with pytest.raises(ValueError,match='existing request guard'): advance(s,c,2,identity)
    assert c.before_request is guard and c.calls == []


@pytest.mark.parametrize('change',[{'since':True},{'until':100},{'tz':'Invalid/Zone'},
                                  {'language':'xx'},{'forum_id':False}])
def test_invalid_start(tmp_path,change):
    args = dict(course_id=7,forum_id=8,since=100,until=150)
    args.update(change)
    with pytest.raises((ValueError,KeyError)): start(store(tmp_path),**args)
