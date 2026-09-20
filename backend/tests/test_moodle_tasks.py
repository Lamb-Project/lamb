import asyncio
import json
import threading
from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from lamb.moodle.forum_activity import GuardedClient, TaskCancelled, forum_activity, validate_request
from lamb.moodle.results import ResultStore, evidence_page, summary, MODEL_PAGE_BYTES
from lamb.moodle.contract import prepare_moodle
from lamb.aac.authorization import ActionAuthorizer


PARAMS = {'all_courses': True, 'course_ids': (), 'month': '2026-09', 'tz': 'UTC', 'max_posts': 200}
STAMP = int(datetime(2026, 9, 10, tzinfo=timezone.utc).timestamp())


class Fixture:
    readonly = True

    def __init__(self):
        self.calls = []
        self.courses = [1, 2]
        self.student = set()
        self.fail_forums = set()
        self.pages = {}
        self.messages = {}
        self.post_time = STAMP

    def call(self, function, **params):
        self.calls.append((function, params))
        if function == 'core_enrol_get_users_courses':
            return [{'id': i, 'fullname': f'Course {i}', 'shortname': f'C{i}'} for i in self.courses]
        if function == 'core_user_get_course_user_profiles':
            course = params['userlist'][0]['courseid']
            return [{'id': 70, 'roles': [{'shortname': 'student' if course in self.student else 'editingteacher'}]}]
        if function == 'mod_forum_get_forums_by_courses':
            course = params['courseids'][0]
            return [{'id': course * 10, 'course': course, 'name': f'Forum {course}'}]
        if function == 'mod_forum_get_forum_discussions':
            forum = params['forumid']
            if forum in self.fail_forums:
                raise RuntimeError('upstream error with token=should-not-be-exposed')
            return {'discussions': self.pages.get((forum, params['page']), [{'id': forum*10, 'discussion': forum*10}])}
        if function == 'mod_forum_get_discussion_posts':
            did = params['discussionid']
            return {'posts': [{'id': did*10, 'discussionid': did, 'timecreated': self.post_time,
                'subject': 'Fixture', 'message': self.messages.get(did, '<p>A question</p>'), 'author': {'id': 4}}]}
        raise AssertionError(function)


def run(raw=None, params=None, **guard):
    raw = raw or Fixture()
    return forum_activity(GuardedClient(raw, revalidate=lambda: None, **guard), 70, params or PARAMS)


def test_cross_course_traversal_ignores_mutable_selection_and_checks_roles_first():
    raw = Fixture()
    result = run(raw)
    assert result['coverage']['complete']
    assert {p['course_id'] for p in result['posts']} == {1, 2}
    for course in (1, 2):
        check = next(i for i, (f, p) in enumerate(raw.calls) if f == 'core_user_get_course_user_profiles' and p['userlist'][0]['courseid'] == course)
        inventory = next(i for i, (f, p) in enumerate(raw.calls) if f == 'mod_forum_get_forums_by_courses' and p['courseids'] == [course])
        assert check < inventory
    assert not any('view' in f or 'add_' in f for f, _ in raw.calls)


def test_excluded_course_is_not_fetched_or_claimed_empty():
    raw = Fixture(); raw.student.add(2)
    result = run(raw)
    assert not result['coverage']['complete']
    assert result['coverage']['courses'] == {'ok': 1, 'excluded': 1}
    assert not any(f == 'mod_forum_get_forums_by_courses' and p['courseids'] == [2] for f, p in raw.calls)


def test_failed_forum_does_not_hide_success_or_leak_raw_error():
    raw = Fixture(); raw.fail_forums.add(10)
    result = run(raw)
    assert result['courses'][0]['status'] == 'partial'
    assert result['courses'][1]['status'] == 'ok'
    assert 'should-not-be-exposed' not in json.dumps(result)


def test_discussion_paging_includes_later_pages():
    raw = Fixture(); raw.courses = [1]
    raw.pages[(10, 0)] = [{'id': n, 'discussion': n} for n in range(100, 150)]
    raw.pages[(10, 1)] = [{'id': 150, 'discussion': 150}]
    result = run(raw)
    assert len(result['posts']) == 51
    assert result['coverage']['complete']
    assert [p['page'] for f, p in raw.calls if f == 'mod_forum_get_forum_discussions'] == [0, 1, 0, 1]


@pytest.mark.parametrize('guard,limit', [({'max_calls': 4}, 'request_or_time_limit'), ({'max_seconds': 0}, None)])
def test_shared_call_and_time_limits(guard, limit):
    if limit is None:
        from lamb.moodle.forum_activity import TaskLimit
        with pytest.raises(TaskLimit): run(**guard)
    else:
        result = run(**guard)
        assert not result['coverage']['complete']
        assert result['budget']['requests_used'] <= guard['max_calls']
        assert result['budget']['stopped_reason'] == limit


def test_post_cap_reports_partial_and_unchecked_courses():
    result = run(params={**PARAMS, 'max_posts': 1})
    assert len(result['posts']) == 1 and not result['coverage']['complete']
    assert result['budget']['stopped_reason'] == 'step_post_limit'


def test_half_open_window_and_timezone_are_explicit():
    params = {**PARAMS, 'month': '2026-10', 'tz': 'Europe/Madrid'}
    start, end = validate_request(params)
    assert end.timestamp() - start.timestamp() == 31*86400 + 3600  # DST transition
    raw = Fixture(); raw.post_time = int(end.timestamp())
    assert not run(raw, params)['posts']
    raw.post_time = int(start.timestamp())
    with patch('lamb.moodle.forum_traversal.now', return_value='2026-12-01T00:00:00+00:00'):
        assert len(run(raw, params)['posts']) == 2


@pytest.mark.parametrize('args', ['--month September', '--month 2026-13', '--since 2026-09-01', '--month 2026-09 --tz Mars/Base', '--month 2026-09 --until 2026-10-01'])
def test_invalid_date_requests_do_not_execute(args):
    with pytest.raises(ValueError): prepare_moodle('moodle news --all-courses ' + args)


def test_task_alias_and_authorization_use_same_contract():
    for prefix in ('moodle news', 'moodle forum activity'):
        spec, values = prepare_moodle(prefix + ' --all-courses --month 2026-09')
        assert spec.key == 'news' and values['tz'] == 'UTC'
        assert ActionAuthorizer().check('moodle.' + spec.key) == 'auto'
    with pytest.raises(ValueError): prepare_moodle('moodle news --month 2026-09')
    with pytest.raises(ValueError): prepare_moodle('moodle news --all-courses --course 1 --month 2026-09')


def test_cancel_and_revocation_stop_before_next_remote_call():
    cancel = threading.Event(); cancel.set(); raw = Fixture()
    with pytest.raises(TaskCancelled): run(raw, cancel=cancel)
    assert not raw.calls
    def revoked(): raise PermissionError('revoked')
    with pytest.raises(PermissionError): forum_activity(GuardedClient(raw, revalidate=revoked), 70, PARAMS)
    assert not raw.calls


def store(tmp_path, **changes):
    return ResultStore(1, 7, **({'base_url': 'https://moodle.test', 'moodle_user_id': 70, 'generation': 1, 'root': tmp_path} | changes))


def test_immutable_evidence_owner_account_generation_and_expiry(tmp_path):
    original = run(); st = store(tmp_path); identity = st.save(original)
    original['posts'].clear()
    assert len(st.read(identity)['posts']) == 2
    for options in ({'generation': 2}, {'moodle_user_id': 71}, {'base_url': 'https://other.test'}):
        with pytest.raises(PermissionError): store(tmp_path, **options).read(identity)
    other = ResultStore(1, 8, base_url='https://moodle.test', moodle_user_id=70, generation=1, root=tmp_path)
    with pytest.raises(PermissionError): other.read(identity)
    with patch('lamb.moodle.results.time.time', return_value=10**12):
        with pytest.raises(PermissionError): st.read(identity)
    with pytest.raises(PermissionError): st.read('../../outside')


def test_unicode_budget_and_all_message_fragments_reconstruct_source():
    raw = Fixture(); raw.messages[100] = '<p>' + ('你好<&>' * 4000) + '</p>'
    snapshot = run(raw)
    response = summary('fixture', snapshot)
    assert len(json.dumps(response, ensure_ascii=False).encode()) <= MODEL_PAGE_BYTES
    offset = 0; fragments = []
    while True:
        page = evidence_page('fixture', snapshot, offset)
        assert len(json.dumps(page, ensure_ascii=False).encode()) <= MODEL_PAGE_BYTES
        fragments.extend(p['html_fragment'] for p in page['items'] if p['type'] == 'post_fragment' and p['id'] == 1000)
        if page['next_offset'] is None: break
        assert page['next_offset'] > offset
        offset = page['next_offset']
    assert ''.join(fragments) == raw.messages[100]


def test_result_retention_and_symlinks(tmp_path):
    st = store(tmp_path)
    with patch('lamb.moodle.results.MAX_RESULTS', 2):
        ids = [st.save(run()) for _ in range(3)]
    with pytest.raises(PermissionError): st.read(ids[0])
    assert st.read(ids[-1])['coverage']['complete']
    file = st.folder / (ids[-1] + '.json')
    assert file.stat().st_mode & 0o777 == 0o600
    file.unlink(); file.symlink_to(tmp_path / 'outside')
    with pytest.raises(PermissionError): st.read(ids[-1])


def test_runtime_keeps_selection_and_revalidates_evidence_instructor(tmp_path, stores):
    from tests.test_moodle_runtime import runtime
    from lamb.moodle.runtime import MoodleRuntime
    rt = runtime(stores); rt.cache_root = tmp_path
    rt.context.update(course_id=999, generation=rt.snapshot()['generation'])
    raw = Fixture()
    with patch('lamb.moodle.runtime.MoodleHTTPClient') as client:
        client.return_value.__enter__.return_value = raw
        result = rt.execute('news', PARAMS)
        assert rt.context['course_id'] == 999
        assert rt.execute('evidence', {'result_id': result['result_id']})['coverage']['complete']
        raw.student.add(2)
        with pytest.raises(PermissionError): rt.execute('evidence', {'result_id': result['result_id']})


def test_runtime_mid_read_disconnect_never_publishes_snapshot(tmp_path, stores):
    from tests.test_moodle_runtime import runtime
    rt = runtime(stores); rt.cache_root = tmp_path
    raw = Fixture(); original = raw.call
    def call(function, **params):
        result = original(function, **params)
        if function == 'mod_forum_get_discussion_posts': rt.store.disconnect()
        return result
    raw.call = call
    with patch('lamb.moodle.runtime.MoodleHTTPClient') as client:
        client.return_value.__enter__.return_value = raw
        with pytest.raises(PermissionError): rt.execute('news', PARAMS)
    # Recovery metadata may exist, but no post fetched after revocation is
    # retained and no result is accessible through the disconnected runtime.
    for path in tmp_path.rglob('*.json'):
        envelope = json.loads(path.read_text())
        snapshot = envelope.get('snapshot', envelope.get('state', {}).get('snapshot', {}))
        assert not snapshot.get('posts')
    with pytest.raises(PermissionError): rt.execute('runs', {})


def test_shell_cancellation_signals_the_worker_before_more_reads():
    from lamb.aac.liteshell.shell import LiteShell
    started, finished = threading.Event(), threading.Event()
    class Slow:
        def result_binding(self): return {'generation':1}
        def execute(self, key, params, *, cancel, **kwargs):
            started.set()
            if not cancel.wait(2): raise AssertionError('Cancellation flag not delivered')
            finished.set()
            raise TaskCancelled()
    async def exercise():
        shell = LiteShell('', '', 'fixture@test', 1, user_id=7, moodle=Slow())
        task = asyncio.create_task(shell.execute('moodle news --all-courses --month 2026-09'))
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert await asyncio.to_thread(finished.wait, 2)
    asyncio.run(exercise())


from tests.test_moodle_store import stores
