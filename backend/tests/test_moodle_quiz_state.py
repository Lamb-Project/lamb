from copy import deepcopy
import pytest
from lamb.moodle.analytics.quiz_state import initial_cursor, advance_cursor


def page(ids=(1, 2), **changes):
    rows = [dict(id=i, quiz=7, userid=100+i, attempt=1, preview=False, state='finished',
                 sumgrades=0, timestart=100, timefinish=200, timemodified=200) for i in ids]
    return dict(schema_version=1, courseid=9, quizid=7, groupid=0, source='quiz_attempts',
                atomic_snapshot=False, collected_at=300, raw_maximum=10, grade_maximum=10,
                grading_method=1, throughid=3, next_afterid=ids[-1] if ids else 0,
                has_more=True, attempts=rows, **changes)


def changed_page(**changes):
    result = page()
    result.update(changes)
    return result


def test_atomic_pages_and_idempotent_replay():
    initial = initial_cursor(9, 7)
    first = advance_cursor(initial, 0, page())
    assert initial['records'] == [] and initial['throughid'] is None
    assert advance_cursor(first, 0, changed_page(collected_at=400)) == first
    last = page((3,))
    last['has_more'] = False
    final = advance_cursor(first, 2, last)
    assert final['done'] and [r['id'] for r in final['records']] == [1, 2, 3]
    assert advance_cursor(final, 2, last) == final
    assert len(first['records']) == 2


@pytest.mark.parametrize('changes', [
    {'courseid': 10}, {'quizid': True}, {'groupid': 1}, {'schema_version': True},
    {'atomic_snapshot': True}, {'has_more': 1}, {'throughid': 1}, {'next_afterid': 1},
    {'raw_maximum': float('nan')}, {'grade_maximum': 0}, {'grading_method': 99},
    {'attempts': []}, {'collected_at': 0},
])
def test_malformed_pages_leave_original_unchanged(changes):
    state = initial_cursor(9, 7)
    old = deepcopy(state)
    with pytest.raises(ValueError):
        advance_cursor(state, 0, changed_page(**changes))
    assert state == old


@pytest.mark.parametrize('changes', [
    {'id': 0}, {'userid': True}, {'quiz': 8}, {'attempt': 0}, {'preview': 1},
    {'state': 'unknown'}, {'sumgrades': '0'}, {'sumgrades': float('inf')},
    {'timestart': -1}, {'feedback': 'private'},
])
def test_malformed_attempt_rejected(changes):
    response = page()
    response['attempts'][0].update(changes)
    with pytest.raises(ValueError):
        advance_cursor(initial_cursor(9, 7), 0, response)


def test_drift_replay_order_and_capacity_fail_closed():
    state = advance_cursor(initial_cursor(9, 7), 0, page())
    response = page()
    response['attempts'][0]['sumgrades'] = 5
    with pytest.raises(ValueError, match='Acknowledged'):
        advance_cursor(state, 0, response)
    for key, value in [('throughid', 4), ('raw_maximum', 20)]:
        response = page((3,))
        response.update(has_more=False, **{key: value})
        with pytest.raises(ValueError):
            advance_cursor(state, 2, response)
    with pytest.raises(ValueError):
        advance_cursor(state, 1, page())
    state['records'] *= 5000
    response = page((3,))
    response['has_more'] = False
    with pytest.raises(ValueError, match='limit'):
        advance_cursor(state, 2, response)


def test_empty_source_is_done_not_missing_marks_or_zero_scores():
    response = changed_page(attempts=[], throughid=0, next_afterid=0, has_more=False)
    result = advance_cursor(initial_cursor(9, 7), 0, response)
    assert result['done'] and result['records'] == []
    assert advance_cursor(result, 0, response) == result
