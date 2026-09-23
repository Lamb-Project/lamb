from copy import deepcopy
from datetime import datetime
import pytest
from lamb.moodle.analytics.forum_participation import summarize_forums


def post(identity, author=1, parent=None, created=100, **flags):
    return dict(id=identity, author_id=author, parent_id=parent, created=created,
                deleted=False, private=False, **flags)


def thread(posts, identity=1, complete=True):
    return dict(id=identity, forum_id=5, complete=complete, posts=posts)


def run(threads, **kwargs):
    params = dict(since=100, until=200, as_of=300, timezone='Europe/Madrid', inventory_complete=True)
    params.update(kwargs)
    return summarize_forums(threads, [1, 2, 3], **params)


def test_population_window_and_all_author_reply_semantics():
    data = [thread([post(1, created=90), post(2, parent=1, created=100),
                    post(3, author=9, parent=2, created=150), post(4, author=2, parent=1, created=200)]),
            thread([post(5, author=2, created=110)], identity=2)]
    original = deepcopy(data)
    result = run(data)
    assert data == original
    assert result['student_public_posts_in_window'] == 2
    assert result['students_without_observed_public_posts'] == 1
    assert result['student_rows'] == [
        dict(student_id=1, posts=1, replies=1, discussions_started=0, active_local_days=1),
        dict(student_id=2, posts=1, replies=0, discussions_started=1, active_local_days=1),
        dict(student_id=3, posts=0, replies=0, discussions_started=0, active_local_days=0)]
    first, second = result['discussion_rows']
    assert first['discussion_id'] == 2 and first['no_observed_public_replies'] is True
    assert second['observed_public_replies_as_of'] == 3
    assert second['seconds_since_last_observed_public_post'] == 100
    assert all(row['resolution_status'] == 'unknown' for row in result['discussion_rows'])


def test_private_deleted_redacted_and_incomplete_are_not_false_zero():
    private = post(2, parent=1); private['private'] = True
    deleted = post(3, parent=1); deleted['deleted'] = True
    redacted = post(4, parent=1, author=None)
    result = run([thread([post(1), private, deleted, redacted])])
    assert result['student_public_posts_in_window'] == 1
    assert result['discussion_rows'][0]['no_observed_public_replies'] is None
    assert result['coverage']['exclusions'] == {'private':1, 'deleted':1, 'redacted':1}
    assert not result['coverage']['collection_complete']
    assert run([thread([post(1)], complete=False)])['discussion_rows'][0]['no_observed_public_replies'] is None
    assert not run([], inventory_complete=False)['coverage']['collection_complete']


def test_missing_parent_and_missing_root_are_partial():
    for posts in ([post(2, parent=999)], []):
        row = run([thread(posts)])['discussion_rows'][0]
        assert not row['public_thread_complete'] and row['no_observed_public_replies'] is None


def test_dst_repeated_hour_counts_one_local_day():
    stamps = [int(datetime.fromisoformat(value).timestamp()) for value in
              ('2026-10-25T02:30:00+02:00', '2026-10-25T02:30:00+01:00')]
    result = run([thread([post(1, created=stamps[0]), post(2, parent=1, created=stamps[1])])],
                 since=stamps[0], until=stamps[1]+1, as_of=stamps[1]+100)
    assert result['student_rows'][0]['posts'] == 2
    assert result['student_rows'][0]['active_local_days'] == 1


@pytest.mark.parametrize('posts', [
    [post(1), post(1)], [post(True)], [post(1, author=True)],
    [post(1, created=301)], [post(1, parent=1)],
    [post(1, parent=2), post(2, parent=1)], [post(1), post(2)],
])
def test_invalid_graph_and_source_rejected(posts):
    with pytest.raises(ValueError): run([thread(posts)])


def test_source_text_never_projected_and_empty_is_explicit():
    source = post(1); source.update(message='SECRET BODY', subject='SECRET TITLE', author_name='PRIVATE')
    result = run([thread([source])])
    assert 'SECRET' not in repr(result) and 'PRIVATE' not in repr(result)
    empty = run([])
    assert empty['coverage']['collection_complete']
    assert empty['students_without_observed_public_posts'] == 3


def test_bounds_and_unknown_visibility():
    source = post(1); source['private'] = 0
    with pytest.raises(ValueError): run([thread([source])])
    with pytest.raises(ValueError): run([thread([], identity=i+1) for i in range(1001)])
    with pytest.raises(ValueError): run([], until=301)
    with pytest.raises(ValueError): run([], inventory_complete=None)
    with pytest.raises(ValueError): summarize_forums([], [1,1], since=0, until=1, as_of=1,
                                                    timezone='UTC', inventory_complete=True)


def test_500_student_oracle_and_post_bound():
    students = list(range(1, 501))
    threads = [thread([post(2*s-1, author=s), post(2*s, author=s, parent=2*s-1)], identity=s)
               for s in students]
    result = summarize_forums(threads, students, since=100, until=200, as_of=300,
                             timezone='UTC', inventory_complete=True)
    assert result['student_public_posts_in_window'] == 1000
    assert result['students_without_observed_public_posts'] == 0
    assert all(row['posts'] == 2 and row['replies'] == row['discussions_started'] == 1
               for row in result['student_rows'])
    assert not any(row['no_observed_public_replies'] for row in result['discussion_rows'])
    with pytest.raises(ValueError):
        run([thread([post(i+1, parent=1 if i else None) for i in range(10001)])])
