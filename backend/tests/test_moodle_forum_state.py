from copy import deepcopy
import pytest
from lamb.moodle.analytics.forum_state import initial_cursor, advance_cursor, normalized_thread
from lamb.moodle.analytics.forum_participation import summarize_forums


def page(ids=(1,2), through=3, more=True):
    return dict(schema_version=1, courseid=7, forumid=8, discussionid=9, groupid=0,
        throughid=through, next_afterid=ids[-1] if ids else 0, has_more=more,
        posts=[dict(id=i, parent_id=1 if i>1 else None, author_id=10,
                    created=100+i, modified=100+i) for i in ids],
        source='forum_posts', timestamp_basis='stored_creation',
        population='visible_public_nondeleted_posts', atomic_snapshot=False, collected_at=200)


def test_page_replay_and_completed_reducer_bridge():
    original = initial_cursor(7,8,9)
    first = advance_cursor(original,0,page())
    assert not original['records']
    replay = page(); replay['collected_at'] = 201
    assert advance_cursor(first,0,replay) == first
    with pytest.raises(ValueError,match='unfinished'): normalized_thread(first)
    final = advance_cursor(first,2,page((3,),more=False))
    assert advance_cursor(final,2,page((3,),more=False)) == final
    result = summarize_forums([normalized_thread(final)], [10,11], since=100,until=150,
                             as_of=200,timezone='UTC',inventory_complete=True)
    assert result['student_public_posts_in_window'] == 3
    assert result['student_rows'][0]['replies'] == 2
    assert result['students_without_observed_public_posts'] == 1


@pytest.mark.parametrize('change', [
    {'courseid':8}, {'forumid':9}, {'discussionid':10}, {'groupid':1},
    {'schema_version':True}, {'atomic_snapshot':True}, {'timestamp_basis':'display_time'},
    {'population':'all_posts'}, {'source':'other'}, {'has_more':1},
    {'next_afterid':3}, {'throughid':1}, {'posts':[]}, {'collected_at':99},
])
def test_invalid_page_is_atomic(change):
    state = initial_cursor(7,8,9); before=deepcopy(state)
    with pytest.raises(ValueError): advance_cursor(state,0,page()|change)
    assert state == before


@pytest.mark.parametrize('change', [
    {'id':True}, {'parent_id':1}, {'author_id':0}, {'created':True},
    {'modified':201}, {'message':'PRIVATE'}, {'parent_id':4},
])
def test_bad_row_rejected(change):
    source=page(); source['posts'][0].update(change)
    with pytest.raises(ValueError): advance_cursor(initial_cursor(7,8,9),0,source)


def test_changed_replay_scope_watermark_and_order_fail():
    state=advance_cursor(initial_cursor(7,8,9),0,page())
    changed=page(); changed['posts'][0]['author_id']=99
    with pytest.raises(ValueError,match='changed'): advance_cursor(state,0,changed)
    with pytest.raises(ValueError): advance_cursor(state,1,page((2,)))
    with pytest.raises(ValueError,match='upper ID'): advance_cursor(state,2,page((3,),through=4,more=False))
    with pytest.raises(ValueError): advance_cursor(state,2,page((3,),more=False)|{'collected_at':199})


def test_empty_and_deleted_tail_end_safely():
    empty=advance_cursor(initial_cursor(7,8,9),0,page((),through=0,more=False))
    assert empty['done'] and normalized_thread(empty)['posts']==[]
    state=advance_cursor(initial_cursor(7,8,9),0,page())
    terminal=page((),more=False); terminal['next_afterid']=2
    final=advance_cursor(state,2,terminal)
    assert final['done'] and len(final['records'])==2


def test_page_and_storage_bounds():
    with pytest.raises(ValueError):
        advance_cursor(initial_cursor(7,8,9),0,page(tuple(range(1,202)),through=202))
    state=initial_cursor(7,8,9);state['records']=[{}]*10000
    with pytest.raises(ValueError,match='storage bound'): advance_cursor(state,0,page())
