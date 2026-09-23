import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.quiz_tasks import execute
from lamb.moodle.analytics.quiz_run import QuizCheckpoints
from lamb.moodle.forum_activity import TaskCancelled
from lamb.moodle.charts import ChartStore
from tests.test_moodle_quiz_run import store, Client, context


def setup(tmp_path):
    s = store(tmp_path)
    binding = {'generation': 'one', 'base_url': 'https://fixture.test', 'moodle_user_id': 3}
    rt = SimpleNamespace(cache_root=tmp_path/'moodle', store=SimpleNamespace(organization_id=1, owner_id=2),
        result_binding=lambda: dict(binding), validate_result_binding=lambda *a: None)
    c = Client()
    def call(key, **params):
        with patch('lamb.moodle.analytics.quiz_tasks.QuizCheckpoints', return_value=s), \
             patch('lamb.moodle.analytics.quiz_tasks.authorize', side_effect=lambda *a: c.checkpoint()), \
             patch('lamb.moodle.analytics.quiz_run.quiz_context', side_effect=context):
            return execute(rt, None, c, 3, key, params)
    start = call('analytics.start', course_id=9, quiz_id=7, group_id=0,
                 attempt_policy='all_finished', language='en', tz='UTC')
    return s, rt, c, call, start


def test_exact_step_replay_and_single_publication(tmp_path):
    s, rt, c, call, initial = setup(tmp_path)
    identity = initial['run_id']
    assert initial['remaining_collection_steps'] is None
    first = call('analytics.continue', run_id=identity, step=0)
    assert first['processed_attempt_records'] == 5 and first['status'] == 'running'
    calls = len(c.calls)
    assert call('analytics.continue', run_id=identity, step=0) == first
    assert len(c.calls) == calls
    final = call('analytics.continue', run_id=identity, step=1)
    calls = len(c.calls)
    assert call('analytics.continue', run_id=identity, step=1) == final
    assert len(c.calls) == calls and len(list(ChartStore(rt).root.glob('*.json'))) == 1
    assert call('analytics.continue', run_id=identity, step=0) == first
    listing = call('analytics.runs')
    assert listing['items'][0]['status'] == 'published'
    assert listing['items'][0]['quiz_scopes'] == [{'course_id': 9, 'quiz_id': 7, 'group_id': 0}]
    for private in ('userid', 'students": [', 'fingerprint', 'timemodified', 'sumgrades'):
        assert private not in json.dumps([initial, first, final, listing])


def test_interrupted_public_step_keeps_original_five_page_target(tmp_path):
    s, rt, c, call, initial = setup(tmp_path)
    c.fail = 2
    with pytest.raises(TaskCancelled):
        call('analytics.continue', run_id=initial['run_id'], step=0)
    assert s.read(initial['run_id'])['state']['pages'] == 2
    c.fail = None
    recovered = call('analytics.continue', run_id=initial['run_id'], step=0)
    assert recovered['processed_attempt_records'] == 5
    assert s.read(initial['run_id'])['state']['pages'] == 5


def test_lost_step_ack_does_not_collect_another_batch(tmp_path):
    s, rt, c, call, initial = setup(tmp_path)
    original = s.replace
    def fail_ack(identity, state, **kwargs):
        if state.get('step_results'):
            raise OSError('Lost acknowledgement')
        return original(identity, state, **kwargs)
    with patch.object(s, 'replace', side_effect=fail_ack), pytest.raises(OSError):
        call('analytics.continue', run_id=initial['run_id'], step=0)
    assert s.read(initial['run_id'])['state']['finished_public_step'] == 0
    calls = len(c.calls)
    result = call('analytics.continue', run_id=initial['run_id'], step=0)
    assert result['processed_attempt_records'] == 5 and len(c.calls) == calls


def test_revocation_blocks_old_replay_and_hides_listing(tmp_path):
    s, rt, c, call, initial = setup(tmp_path)
    call('analytics.continue', run_id=initial['run_id'], step=0)
    c.denied = True
    with pytest.raises(PermissionError):
        call('analytics.continue', run_id=initial['run_id'], step=0)
    # A connection-level checkpoint also denies the entire listing, not just
    # individual records. No stale progress is returned.
    with pytest.raises(PermissionError):
        call('analytics.runs')


@pytest.mark.parametrize('step', [True, -1, 3, '0'])
def test_invalid_or_future_step_does_not_collect(tmp_path, step):
    s, rt, c, call, initial = setup(tmp_path)
    with pytest.raises(ValueError):
        call('analytics.continue', run_id=initial['run_id'], step=step)
    assert not c.calls
