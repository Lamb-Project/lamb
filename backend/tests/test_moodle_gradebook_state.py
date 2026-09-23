from copy import deepcopy
import pytest
from lamb.moodle.analytics.gradebook_state import (
    initial_cursor, advance_cursor, ROW_INTS, ROW_DECIMALS, ITEM_INTS, ITEM_DECIMALS)


def page(ids=(1, 2), *, upper=3, more=True):
    item = dict.fromkeys(ITEM_INTS, 0)
    item.update(dict.fromkeys(ITEM_DECIMALS, '0.00000'))
    item.update(id=2, gradetype=1, grademax='10.00000', gradepass='6.00000',
                itemtype='manual', itemmodule=None, has_calculation=False)
    rows = []
    for identity in ids:
        row = dict.fromkeys(ROW_INTS, 0)
        row.update(dict.fromkeys(ROW_DECIMALS, None))
        row.update(id=identity, userid=identity+10, rawgrade='2.50000', finalgrade='9.00000')
        rows.append(row)
    return dict(schema_version=1, courseid=7, gradeitemid=2, groupid=0,
        throughid=upper, next_afterid=ids[-1] if ids else 0, has_more=more,
        item=item, item_fingerprint='a'*64, grades=rows, collected_at=100,
        atomic_snapshot=False, source='stored_grade_items_and_grade_grades')


def test_pages_and_replay_are_atomic_and_preserve_raw_values():
    initial = initial_cursor(7, 2)
    first = page()
    state = advance_cursor(initial, 0, first)
    assert initial['records'] == []
    replay = advance_cursor(state, 0, first | {'collected_at': 110})
    assert replay == state and replay is not state
    last = page((3,), more=False)
    last['collected_at'] = 120
    last['grades'][0].update(rawgrade=None, finalgrade=None)
    done = advance_cursor(state, 2, last)
    assert done['done'] and len(done['records']) == 3
    assert done['first_observed_at'] == 100 and done['last_observed_at'] == 120
    assert done['records'][0]['rawgrade'] == '2.50000'
    assert done['records'][0]['finalgrade'] == '9.00000'
    assert done['records'][2]['finalgrade'] is None
    assert advance_cursor(done, 2, last) == done


@pytest.mark.parametrize('change', [
    {'schema_version': True}, {'courseid': True}, {'courseid': 8}, {'gradeitemid': 3},
    {'groupid': 1}, {'throughid': 1}, {'next_afterid': 1}, {'has_more': 1},
    {'atomic_snapshot': True}, {'source': 'grade_report'}, {'collected_at': 0},
    {'item_fingerprint': 'invalid'}, {'grades': []}, {'grades': [{}]},
])
def test_bad_pages_leave_state_untouched(change):
    state = initial_cursor(7, 2)
    before = deepcopy(state)
    with pytest.raises(ValueError):
        advance_cursor(state, 0, page() | change)
    assert state == before


@pytest.mark.parametrize('value', [True, 1.0, 'NaN', 'Infinity', '1e9', '', ' 2', '9'*65])
def test_malformed_grade_decimal(value):
    p = page()
    p['grades'][0]['finalgrade'] = value
    with pytest.raises(ValueError):
        advance_cursor(initial_cursor(7, 2), 0, p)


@pytest.mark.parametrize('change', [{'gradepass': '7.00000'}, {'needsupdate': 1}, {'grademax': '20.00000'}])
def test_metadata_changes_rejected_even_with_same_hash(change):
    state = advance_cursor(initial_cursor(7, 2), 0, page())
    last = page((3,), more=False)
    last['item'].update(change)
    with pytest.raises(ValueError, match='item changed'):
        advance_cursor(state, 2, last)


def test_changed_replay_duplicate_learner_and_new_upper_are_rejected():
    state = advance_cursor(initial_cursor(7, 2), 0, page())
    changed = page()
    changed['grades'][0]['finalgrade'] = '8.00000'
    with pytest.raises(ValueError, match='Acknowledged'):
        advance_cursor(state, 0, changed)
    last = page((3,), more=False)
    last['grades'][0]['userid'] = 11
    with pytest.raises(ValueError, match='Duplicate'):
        advance_cursor(state, 2, last)
    with pytest.raises(ValueError, match='upper ID changed'):
        advance_cursor(state, 2, page((3,), upper=4, more=False))


def test_empty_item_and_stale_values_are_evidence_not_zero_or_recalculated():
    empty = page((), upper=0, more=False)
    result = advance_cursor(initial_cursor(7, 2), 0, empty)
    assert result['done'] and result['records'] == []
    stale = page((1,), upper=1, more=False)
    stale['item']['needsupdate'] = 1
    result = advance_cursor(initial_cursor(7, 2), 0, stale)
    assert result['item']['needsupdate'] == 1 and result['records'][0]['finalgrade'] == '9.00000'


def test_limit_and_out_of_order(monkeypatch):
    import lamb.moodle.analytics.gradebook_state as module
    monkeypatch.setattr(module, 'MAX_RECORDS', 1)
    with pytest.raises(ValueError, match='limit'):
        advance_cursor(initial_cursor(7, 2), 0, page())
    with pytest.raises(ValueError, match='Out-of-order'):
        advance_cursor(initial_cursor(7, 2), 2, page((3,), more=False))
