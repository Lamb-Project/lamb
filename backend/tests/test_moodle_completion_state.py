"""Checkpoint transition properties, independent of network and file storage."""
from copy import deepcopy
import json
import pytest

from lamb.moodle.analytics.completion_state import initial_cursor, advance_cursor


def row(identity):
    return {'cmid':identity,'tracking':2,'population_students':500,
        **{key:0 for key in ('incomplete','complete','complete_pass','complete_fail','unknown',
            'untracked','overridden','override_unknown','overall_complete','overall_unknown')}}


def response(state=1):
    return {'statuses':[{'cmid':identity,'tracking':2,'state':state,'istrackeduser':True,
        'isoverallcomplete':state != 0,'overrideby':None} for identity in (10,20)],'warnings':[]}


def test_initial_cursor_owns_independent_rows_and_stable_student_order():
    rows=[row(10),row(20)]
    state=initial_cursor([2,1],rows)
    assert state['students']==[1,2] and state['next_student']==0
    rows[0]['incomplete']=99
    assert state['rows'][0]['incomplete']==0


def test_late_invalid_activity_cannot_partially_increment_counts_or_cursor():
    before=initial_cursor([1,2],[row(10),row(20)])
    original=deepcopy(before)
    data=response(); data['statuses'][1]['tracking']=1
    with pytest.raises(ValueError,match='tracking changed'):advance_cursor(before,1,data)
    assert before==original


def test_replay_before_and_after_checkpoint_never_double_counts():
    before=initial_cursor([1,2],[row(10),row(20)])
    # An interrupted write leaves the previous durable state authoritative.
    first=advance_cursor(before,1,response())
    retried=advance_cursor(before,1,response())
    assert first==retried and before['next_student']==0
    # After durable replacement, stale retries return the acknowledged state.
    saved=json.loads(json.dumps(first))
    replay=advance_cursor(saved,1,response(3))
    assert replay==saved and replay is not saved
    assert replay['rows'][0]['complete']==1 and replay['rows'][0]['complete_fail']==0


@pytest.mark.parametrize('student',[0,3,True,2])
def test_unknown_or_out_of_order_learner_cannot_advance(student):
    state=initial_cursor([1,2],[row(10),row(20)])
    with pytest.raises(ValueError):advance_cursor(state,student,response())
    assert state['next_student']==0


def test_500_learner_serialized_checkpoints_match_single_pass():
    original=initial_cursor(range(1,501),[row(10),row(20)])
    continuous=deepcopy(original); resumed=deepcopy(original)
    for learner in range(1,501):
        data=response((learner-1)%4)
        continuous=advance_cursor(continuous,learner,data)
        resumed=advance_cursor(resumed,learner,data)
        if learner%17==0:
            resumed=json.loads(json.dumps(resumed))
            resumed=advance_cursor(resumed,learner,data)
    assert resumed==continuous and resumed['next_student']==500
    for counts in resumed['rows']:
        assert [counts[key] for key in ('incomplete','complete','complete_pass','complete_fail')]==[125]*4
        assert counts['overall_complete']==375


def test_missing_untracked_and_unknown_remain_separate_through_roundtrip():
    state=initial_cursor([1,2],[row(10),row(20)])
    data=response();data['statuses'][0]['istrackeduser']=False;data['statuses'].pop()
    state=json.loads(json.dumps(advance_cursor(state,1,data)))
    data=response();data['statuses'][0]['state']=True
    state=advance_cursor(state,2,data)
    assert state['rows'][0]['untracked']==1 and state['rows'][0]['unknown']==1
    assert state['rows'][1]['unknown']==1 and state['rows'][1]['complete']==1


@pytest.mark.parametrize('students', [[1,1],[True],[0],['1'],[None]])
def test_invalid_population_rejected(students):
    with pytest.raises(ValueError):initial_cursor(students,[row(10)])


def test_duplicate_module_inventory_rejected():
    with pytest.raises(ValueError):initial_cursor([1],[row(10),row(10)])


@pytest.mark.parametrize('index',[-1,3,True,'1'])
def test_invalid_saved_cursor_rejected(index):
    state=initial_cursor([1,2],[row(10)])
    state['next_student']=index
    with pytest.raises(ValueError,match='cursor'):advance_cursor(state,1,response())
