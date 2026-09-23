from copy import deepcopy
import json
import pytest
from lamb.moodle.analytics.quiz_attempts import summarize_attempts


def attempt(identity,user,ordinal,mark,**changes):
    return {'id':identity,'quiz':7,'userid':user,'attempt':ordinal,'preview':False,
        'state':'finished','sumgrades':mark,'timestart':1000*ordinal,'timefinish':1000*ordinal+100,**changes}


ROWS=[attempt(1,101,1,5),attempt(2,101,2,8),attempt(3,101,3,None),
      attempt(4,102,1,0),attempt(5,103,1,None,state='inprogress',timefinish=0),
      attempt(6,104,1,10,preview=True),attempt(7,999,1,10)]


def summarize(rows=None,**options):
    return summarize_attempts(deepcopy(ROWS if rows is None else rows),[101,102,103,104],
        quiz_id=7,maximum=10,**{'policy':'first_finished','pass_percent':50,**options})


@pytest.mark.parametrize('policy,selected,graded,mean,passed',[
    ('first_finished',2,2,25,1),('latest_finished',2,1,0,0),
    ('best_scored_finished',2,2,40,1),('all_finished',4,3,130/3,2)])
def test_named_policies_keep_missing_zero_and_population_distinct(policy,selected,graded,mean,passed):
    data=summarize(policy=policy)
    assert data['selected_attempts']==selected and data['score_percent']['n']==graded
    assert data['score_percent']['mean']==pytest.approx(mean)
    assert data['ungraded_selected_attempts']==selected-graded
    assert data['ungraded_finished_attempts']==1
    if policy=='best_scored_finished':assert data['best_selection_complete'] is False
    assert data['passing_selected_attempts']==passed
    assert data['students_with_finished_attempt']==2
    assert data['finished_attempt_histogram']==[{'attempts':0,'students':2},{'attempts':1,'students':1},{'attempts':3,'students':1}]
    assert data['excluded']=={'preview':1,'outside_population':1}
    assert data['attempt_states']['inprogress']==1
    assert data['retry_1_to_2']['score_change_percentage_points']['mean']==30
    assert data['retry_1_to_2']['between_attempt_seconds']['mean']==900
    assert 'userid' not in json.dumps(data) and '101' not in json.dumps(data)


def test_missing_first_attempt_does_not_turn_second_and_third_into_retry_pair():
    data=summarize([attempt(1,101,2,2),attempt(2,101,3,10)])
    assert data['score_percent']['mean']==20
    assert data['retry_1_to_2']['score_change_percentage_points']['n']==0


def test_unknown_pass_threshold_and_empty_population_are_not_zero_failure():
    data=summarize([],pass_percent=None)
    assert data['score_percent']['mean'] is None and data['pass_rate_scored_attempts'] is None
    assert data['passing_selected_attempts'] is None
    assert data['finished_attempt_histogram']==[{'attempts':0,'students':4}]


@pytest.mark.parametrize('change',[{'id':True},{'quiz':8},{'preview':1},{'state':'unknown'},
    {'sumgrades':'NaN'},{'sumgrades':True},{'sumgrades':11},{'timefinish':999}])
def test_invalid_raw_evidence_fails(change):
    with pytest.raises(ValueError):summarize([attempt(1,101,1,5,**change)])


def test_duplicates_and_overlapping_attempts_fail():
    for rows in [[attempt(1,101,1,5)]*2,
                 [attempt(1,101,1,5),attempt(2,101,1,5)],
                 [attempt(1,101,1,5,timefinish=2100),attempt(2,101,2,8)]]:
        with pytest.raises(ValueError):summarize(rows)


def test_large_cohort_and_attempt_bound():
    rows=[attempt(user,user,1,10) for user in range(1,501)]
    data=summarize_attempts(rows,list(range(1,501)),quiz_id=7,maximum=10,policy='all_finished')
    assert data['score_percent']['n']==500 and data['score_bins'][-1]['attempts']==500
    with pytest.raises(ValueError):summarize(ROWS*1500)
