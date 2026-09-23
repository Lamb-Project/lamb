from copy import deepcopy
import pytest
from lamb.moodle.analytics.grade_trajectory import trajectory
from lamb.moodle.analytics.gradebook_state import initial_cursor,advance_cursor
from tests.test_moodle_gradebook_state import page

def evidence():
    result=[]
    for i,score in enumerate([2,4,6,8]):
        p=page((1,2),upper=2,more=False);p['gradeitemid']=p['item']['id']=i+2
        p['grades'][0]['finalgrade']=str(score);p['grades'][1]['finalgrade']='10'
        cursor=advance_cursor(initial_cursor(7,i+2),0,p)
        result.append(dict(cursor=cursor,students=[11,12],assessment_at=f'2026-09-{i+1:02d}T12:00:00+02:00',
            date_basis='explicit_instructor_date'))
    return result

def test_exact_trajectory_and_class_comparison_without_mutation():
    source=evidence();before=deepcopy(source);result=trajectory(source[::-1],11)
    assert source==before
    assert [r['score_pct'] for r in result['rows']]==[20,40,60,80]
    assert [r['class_median_pct'] for r in result['rows']]==[60,70,80,90]
    assert [r['rolling_mean_pct'] for r in result['rows']]==[None,None,40,60]
    assert result['slope_percentage_points_per_day']==20
    assert result['early_to_recent_change_percentage_points']==40

@pytest.mark.parametrize('defect,status',[('missing','null_final_grade'),('excluded','excluded_grade'),
    ('stale','unavailable_score'),('outside','outside_target_population')])
def test_gaps_are_not_zero_or_compressed(defect,status):
    source=evidence();item=source[1]
    if defect=='missing':item['cursor']['records'][0]['finalgrade']=None
    if defect=='excluded':item['cursor']['records'][0]['excluded']=1
    if defect=='stale':item['cursor']['item']['needsupdate']=1
    if defect=='outside':item['students']=[12]
    result=trajectory(source,11)
    assert result['rows'][1]['status']==status and result['rows'][1]['score_pct'] is None
    assert all(r['rolling_mean_pct'] is None for r in result['rows'])
    assert result['early_to_recent_change_percentage_points'] is None

def test_rejects_grade_clock_chronology_and_duplicate_selection():
    source=evidence();source[0]['date_basis']='grade_timemodified'
    with pytest.raises(ValueError):trajectory(source,11)
    source=evidence();source[1]=source[0]
    with pytest.raises(ValueError):trajectory(source,11)
    source=evidence();source[0]['assessment_at']='2026-09-01'
    with pytest.raises(ValueError):trajectory(source,11)

def test_two_points_or_tied_dates_do_not_claim_a_slope():
    assert trajectory(evidence()[:2],11)['slope_percentage_points_per_day'] is None
    source=evidence()
    for entry in source:entry['assessment_at']=source[0]['assessment_at']
    assert trajectory(source,11)['slope_percentage_points_per_day'] is None


def test_equal_instants_never_create_artificial_rolling_or_edge_order():
    source=evidence();source[1]['assessment_at']='2026-09-01T10:00:00Z'
    result=trajectory(source,11)
    assert [r['chronology_tied'] for r in result['rows']]==[True,True,False,False]
    assert all(r['rolling_mean_pct'] is None for r in result['rows'])
    assert result['early_to_recent_change_percentage_points'] is None
    assert result['distinct_scored_dates']==3
    # OLS is assessment-weighted and invariant under order of simultaneous items.
    assert trajectory(source[::-1],11)['slope_percentage_points_per_day']==result['slope_percentage_points_per_day']


def test_zero_nonzero_minimum_and_declining_scores():
    source=evidence()
    for i,entry in enumerate(source):
        entry['cursor']['item'].update(grademin='10',grademax='20',gradepass='16')
        entry['cursor']['records'][0]['finalgrade']=str(20-i*2.5)
        entry['cursor']['records'][1]['finalgrade']='10'
    result=trajectory(source,11)
    assert [r['score_pct'] for r in result['rows']]==[100,75,50,25]
    assert result['slope_percentage_points_per_day']==-25
    assert result['early_to_recent_change_percentage_points']==-50


@pytest.mark.parametrize('change',[{'student_id':True},{'rolling_window':True},{'rolling_window':1},
    {'edge_window':0},{'edge_window':11}])
def test_invalid_options_rejected(change):
    options=dict(student_id=11);options.update(change)
    with pytest.raises(ValueError):trajectory(evidence(),**options)


def test_missing_record_is_distinct_and_no_other_student_records_projected():
    source=evidence();source[0]['cursor']['records']=source[0]['cursor']['records'][1:]
    result=trajectory(source,11)
    assert result['rows'][0]['status']=='no_grade_record'
    assert result['rows'][0]['score_pct'] is None
    assert 'userid' not in str(result) and 'rawgrade' not in str(result)


def test_rejects_cross_course_and_malformed_date_evidence():
    source=evidence();source[0]['cursor']['courseid']=8
    with pytest.raises(ValueError):trajectory(source,11)
    for entry in ({},None,dict(evidence()[0],date_basis=[])):
        with pytest.raises(ValueError):trajectory([entry,evidence()[1]],11)
