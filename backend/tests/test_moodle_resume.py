"""Resume semantics, independent totals, failures and persisted restart recovery."""
import json
import threading
from unittest.mock import patch
import pytest

from lamb.moodle.forum_activity import GuardedClient, TaskCancelled
from lamb.moodle.runs import RunStore, CheckpointError
from lamb.moodle.results import summary, MODEL_PAGE_BYTES
from tests.test_moodle_tasks import Fixture, PARAMS, STAMP, store


class LargeFixture(Fixture):
    def __init__(self, counts=(125, 130)):
        super().__init__()
        self.courses = list(range(1, len(counts) + 1))
        self.counts = counts
        self.change = False

    @property
    def expected(self):
        return {did * 10 for i, count in enumerate(self.counts, 1) for did in range(i*10000, i*10000+count)}

    def call(self, function, **params):
        if function == 'mod_forum_get_forum_discussions':
            self.calls.append((function, params))
            ci = params['forumid'] // 10
            ids = list(range(ci * 10000, ci * 10000 + self.counts[ci-1]))
            if self.change: ids = list(reversed(ids))
            offset = params['page'] * params['perpage']
            return {'discussions': [{'id': n, 'discussion': n} for n in ids[offset:offset+params['perpage']]]}
        return super().call(function, **params)


def execute(tmp_path, raw, prior=None, *, params=None, cancel=None, **limits):
    client = GuardedClient(raw, revalidate=lambda: None, cancel=cancel, **limits)
    runs = RunStore(store(tmp_path))
    result = runs.execute(client, 70, params=params or PARAMS if prior is None else None,
                          result_id=prior)
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= MODEL_PAGE_BYTES
    return result


def finish(tmp_path, raw, result, **limits):
    results = [result]
    while result['continue_command']:
        assert len(results) <= 12, 'Run did not stop at its overall ceiling'
        result = execute(tmp_path, raw, result['result_id'], **limits)
        results.append(result)
    return results


def test_large_multi_course_run_crosses_call_limit_and_matches_independent_oracle(tmp_path):
    raw = LargeFixture()
    result = execute(tmp_path, raw)
    assert not result['coverage']['complete']
    assert result['continue_command'] and result['budget']['requests_used'] <= 160
    assert result['budget']['stopped_reason'] == 'request_or_time_limit'
    old = store(tmp_path).read(result['result_id'])
    results = finish(tmp_path, raw, result)
    final = store(tmp_path).read(results[-1]['result_id'])
    assert results[-1]['coverage']['complete']
    assert {p['id'] for p in final['posts']} == raw.expected
    assert len(final['posts']) == len(raw.expected) == 255
    assert final['coverage']['discussions_checked'] == 255
    assert store(tmp_path).read(result['result_id']) == old
    assert all(r['budget']['requests_used'] <= 160 for r in results)
    # Retrying a consumed handle returns exactly the same next evidence ID.
    repeated = execute(tmp_path, raw, result['result_id'])
    assert repeated['result_id'] == results[1]['result_id']


def test_one_large_thread_crosses_post_limit_without_restarting_or_duplicating(tmp_path):
    raw = Fixture(); raw.courses = [1]; original = raw.call
    def call(function, **params):
        if function == 'mod_forum_get_discussion_posts':
            raw.calls.append((function, params))
            return {'posts': [{'id': n, 'discussionid': 100, 'timecreated': STAMP,
                'subject': 'Synthetic', 'message': f'Post {n}'} for n in range(1, 251)]}
        return original(function, **params)
    raw.call = call
    first = execute(tmp_path, raw)
    assert first['coverage']['posts_found'] == 200
    assert first['budget']['stopped_reason'] == 'step_post_limit'
    final = finish(tmp_path, raw, first)[-1]
    assert final['coverage']['complete'] and final['coverage']['posts_found'] == 250
    assert sum(f == 'mod_forum_get_discussion_posts' for f, _ in raw.calls) == 1


def test_worker_death_reloads_checkpoint_and_recovery_handle(tmp_path, monkeypatch):
    raw = LargeFixture((20,))
    original = RunStore.save
    class WorkerDied(BaseException): pass
    def save(self, run):
        original(self, run)
        if len(run['state']['snapshot']['posts']) == 8: raise WorkerDied()
    monkeypatch.setattr(RunStore, 'save', save)
    with pytest.raises(WorkerDied): execute(tmp_path, raw)
    monkeypatch.setattr(RunStore, 'save', original)
    run = RunStore(store(tmp_path)).listing()['runs'][0]
    assert run['continue_command']
    assert len(RunStore(store(tmp_path)).read(run['run_id'])['state']['snapshot']['posts']) == 8
    final = execute(tmp_path, raw, run['result_id'])
    assert final['coverage']['complete'] and final['coverage']['posts_found'] == 20
    assert final['run']['step'] == 1  # recovering work, not starting a second step
    posts = store(tmp_path).read(final['result_id'])['posts']
    assert {p['id'] for p in posts} == raw.expected


def test_cancel_saves_private_recovery_then_continues(tmp_path):
    raw = LargeFixture((20,)); event = threading.Event(); original = raw.call
    def call(function, **params):
        result = original(function, **params)
        if function == 'mod_forum_get_discussion_posts' and params['discussionid'] == 10008:
            event.set()
        return result
    raw.call = call
    with pytest.raises(TaskCancelled): execute(tmp_path, raw, cancel=event)
    recent = RunStore(store(tmp_path)).listing()['runs'][0]
    partial = store(tmp_path).read(recent['result_id'])
    assert partial['budget']['stopped_reason'] == 'interrupted'
    assert len(partial['posts']) == 8
    raw.call = original
    final = execute(tmp_path, raw, recent['result_id'])
    assert final['coverage']['complete'] and final['coverage']['posts_found'] == 20


def test_revoked_teacher_role_denies_resume_and_idempotent_replay(tmp_path):
    raw = LargeFixture((20,))
    first = execute(tmp_path, raw, max_calls=10)
    second = execute(tmp_path, raw, first['result_id'], max_calls=10)
    raw.student.add(1)
    before = len(raw.calls)
    for identity in (first['result_id'], second['result_id']):
        with pytest.raises(PermissionError): execute(tmp_path, raw, identity)
    assert not any(f.startswith('mod_forum_') for f, _ in raw.calls[before:])


def test_connection_binding_expiry_and_nonowner_reject_before_reading(tmp_path):
    raw = LargeFixture((20,)); first = execute(tmp_path, raw, max_calls=10)
    for change in ({'generation': 2}, {'moodle_user_id': 71}, {'base_url': 'https://other.test'}):
        with pytest.raises(PermissionError):
            RunStore(store(tmp_path, **change)).execute(GuardedClient(raw, revalidate=lambda: None), 70, result_id=first['result_id'])
    with patch('lamb.moodle.runs.time.time', return_value=10**12):
        assert RunStore(store(tmp_path)).listing()['runs'] == []
        with pytest.raises(PermissionError): execute(tmp_path, raw, first['result_id'])


def test_changed_pages_finish_partial_instead_of_skipping_silently(tmp_path):
    raw = LargeFixture((60,)); first = execute(tmp_path, raw, max_calls=15)
    raw.change = True
    final = finish(tmp_path, raw, first)[-1]
    snapshot = store(tmp_path).read(final['result_id'])
    assert not final['continue_command'] and not final['coverage']['complete']
    assert snapshot['courses'][0]['forums'][0]['reason'] == 'discussion_paging_changed'


def test_repeat_pages_terminate_and_never_duplicate(tmp_path):
    raw = LargeFixture((100,)); original = raw.call
    def call(function, **params):
        if function == 'mod_forum_get_forum_discussions': params['page'] = 0
        return original(function, **params)
    raw.call = call
    final = finish(tmp_path, raw, execute(tmp_path, raw))[-1]
    assert not final['coverage']['complete'] and final['coverage']['posts_found'] == 50
    assert final['coverage']['traversal_finished']


def test_overlarge_thread_is_terminal_for_that_forum_not_endless_resume(tmp_path):
    raw = Fixture(); raw.messages[100] = 'x' * (2 * 1024 * 1024)
    final = execute(tmp_path, raw)
    assert not final['continue_command'] and not final['coverage']['complete']
    assert final['coverage']['courses'] == {'partial': 1, 'ok': 1}
    assert 'response_size_limit' in json.dumps(store(tmp_path).read(final['result_id']))


def test_overall_step_and_request_limits_are_terminal(tmp_path):
    raw = LargeFixture((100,))
    with patch('lamb.moodle.runs.MAX_STEPS', 2):
        result = execute(tmp_path, raw, max_calls=10)
        result = execute(tmp_path, raw, result['result_id'], max_calls=10)
        assert not result['continue_command'] and not result['coverage']['complete']
        assert result['budget']['stopped_reason'] == 'run_step_limit'
    with patch('lamb.moodle.runs.MAX_RUN_CALLS', 9):
        result = execute(tmp_path, raw)
        assert not result['continue_command'] and result['budget']['stopped_reason'] == 'run_request_limit'
        assert result['budget']['total_requests_used'] == 9


def test_run_lock_refuses_overlap_and_retention_is_bounded(tmp_path):
    runs = RunStore(store(tmp_path))
    with runs.lock():
        with pytest.raises(ValueError, match='already running'):
            execute(tmp_path, Fixture())
    with patch('lamb.moodle.runs.MAX_RUNS', 2):
        for _ in range(3): execute(tmp_path, Fixture())
    assert len(runs.listing()['runs']) == 2
    for path in runs.folder.glob('*.json'): assert path.stat().st_mode & 0o777 == 0o600


def test_initial_cutoff_excludes_posts_created_after_start(tmp_path):
    raw = Fixture()
    from datetime import datetime, timezone
    raw.post_time = int(datetime.now(timezone.utc).timestamp()) + 60
    result = execute(tmp_path, raw)
    assert result['coverage']['posts_found'] == 0
    assert result['window']['observed_before'] < result['window']['until']


def test_checkpoint_failure_is_not_converted_to_empty_or_success(tmp_path, monkeypatch):
    original = RunStore.save
    def save(self, run):
        if run['state']['snapshot']['posts']: raise CheckpointError('disk full')
        original(self, run)
    monkeypatch.setattr(RunStore, 'save', save)
    with pytest.raises(CheckpointError): execute(tmp_path, Fixture())


def test_restart_between_final_result_and_manifest_commit_recovers_completed_run(tmp_path, monkeypatch):
    original = RunStore.save
    class WorkerDied(BaseException): pass
    def save(self, run):
        if run['state']['done'] and run['working'] is None:
            raise WorkerDied()  # result saved, final run manifest not yet replaced
        original(self, run)
    monkeypatch.setattr(RunStore, 'save', save)
    with pytest.raises(WorkerDied): execute(tmp_path, Fixture())
    monkeypatch.setattr(RunStore, 'save', original)
    recovered = RunStore(store(tmp_path)).listing()['runs'][0]
    assert recovered['continue_command'] and not recovered['finished']
    final = execute(tmp_path, Fixture(), recovered['result_id'])
    assert final['coverage']['complete'] and final['coverage']['posts_found'] == 2
    again = execute(tmp_path, Fixture(), recovered['result_id'])
    assert again == final


def test_new_task_commands_parse_as_reads_without_confirmation():
    from lamb.aac.liteshell.shell import prepare_command
    from lamb.aac.authorization import ActionAuthorizer
    for text, expected in [('moodle runs','moodle.runs'),
            ('moodle continue 11111111-1111-4111-8111-111111111111','moodle.continue')]:
        key, _, _, _ = prepare_command(text)
        assert key == expected
        assert ActionAuthorizer().check(key) == 'auto'
    with pytest.raises(ValueError): prepare_command('moodle continue ../../another-user')


def test_restart_after_final_step_does_not_reuse_previous_pause_reason(tmp_path, monkeypatch):
    raw = LargeFixture((20,))
    first = execute(tmp_path, raw, max_calls=10)
    assert first['budget']['stopped_reason']
    original = RunStore.save
    class WorkerDied(BaseException): pass
    def save(self, run):
        original(self, run)
        if run['state']['done'] and run['working'] is not None: raise WorkerDied()
    monkeypatch.setattr(RunStore, 'save', save)
    with pytest.raises(WorkerDied): execute(tmp_path, raw, first['result_id'])
    monkeypatch.setattr(RunStore, 'save', original)
    final = execute(tmp_path, raw, first['result_id'])
    assert final['coverage']['complete'] and final['budget']['stopped_reason'] is None
