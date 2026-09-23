from copy import deepcopy
import pytest
from lamb.moodle.analytics.gradebook_state import initial_cursor, advance_cursor
from lamb.moodle.analytics.assessment_comparison import summarize_assessment, compare_assessments
from tests.test_moodle_gradebook_state import page


def evidence(values=('0', '2.5', '5', '7.5', '10'), **metadata):
    p = page(tuple(range(1, len(values)+1)), upper=len(values), more=False)
    p['item'].update(metadata)
    for row, value in zip(p['grades'], values):
        row['finalgrade'] = value
    return advance_cursor(initial_cursor(7, 2), 0, p)


def test_exact_normalized_box_summary_and_explicit_pass_denominator():
    result = summarize_assessment(evidence(), list(range(11, 16)))
    m = result['metrics']
    assert [m[k] for k in ('min_pct', 'q1_pct', 'median_pct', 'q3_pct', 'max_pct', 'iqr_pct')] == [0,25,50,75,100,50]
    assert (m['pass_n'], m['pass_denominator_n'], m['pass_rate_pct']) == (2,5,40)
    assert m['submission_rate_pct'] is None
    assert 'userid' not in str(result)


def test_missing_null_excluded_override_and_outside_population():
    cursor = evidence(('9', None, '0', '10'))
    cursor['records'][0]['rawgrade'] = '2.5'
    cursor['records'][0]['overridden'] = 150
    cursor['records'][0]['hidden'] = 2000000000
    cursor['records'][2]['excluded'] = 160
    result = summarize_assessment(cursor, [11,12,13,99])
    m = result['metrics']
    assert (m['population_n'],m['graded_n'],m['missing_n'],m['excluded_n']) == (4,1,2,1)
    assert (m['no_record_n'],m['null_final_n'],m['outside_population_records_n']) == (1,1,1)
    assert m['median_pct'] == 90 and m['pass_rate_pct'] == 100
    assert m['missing_grade_rate_pct'] == pytest.approx(200/3)
    assert m['overridden_n'] == m['hidden_flag_n'] == 1
    assert result['grade_release_status'] == 'not_determined'


@pytest.mark.parametrize('metadata,reason', [({'needsupdate':1},'stale_final_grades'),
    ({'gradetype':2},'non_numeric_grade_type'), ({'grademax':'0'},'invalid_numeric_range')])
def test_unavailable_comparisons_keep_evidence_without_score_statistics(metadata, reason):
    result = summarize_assessment(evidence(**metadata), list(range(11,16)))
    assert reason in result['unavailable_reasons']
    assert result['metrics']['graded_n'] == 5
    assert result['metrics']['median_pct'] is result['metrics']['pass_rate_pct'] is None
    assert result['metrics']['valid_n'] == 0


def test_nonzero_minimum_and_unconfigured_pass():
    result = summarize_assessment(evidence(('10','15','20'), grademin='10', grademax='20', gradepass='10'), [11,12,13])
    assert result['metrics']['median_pct'] == 50
    assert result['metrics']['pass_n'] is result['metrics']['pass_denominator_n'] is None
    assert result['pass_basis'] == 'unavailable'


def test_empty_population_and_all_missing_are_not_zero_scores():
    empty = summarize_assessment(evidence(), [])['metrics']
    assert empty['population_n'] == 0 and empty['median_pct'] is empty['missing_grade_rate_pct'] is None
    missing = summarize_assessment(evidence((None,None)), [11,12,13])['metrics']
    assert missing['missing_n'] == 3 and missing['missing_grade_rate_pct'] == 100
    assert missing['median_pct'] is missing['pass_rate_pct'] is None


def test_selection_keeps_per_item_populations_without_inferred_difficulty():
    first = evidence()
    second = deepcopy(first)
    second['gradeitemid'] = second['item']['id'] = 3
    result = compare_assessments([(first,[11,12]),(second,[13,14,15])])
    assert [r['metrics']['population_n'] for r in result['rows']] == [2,3]
    assert result['difficulty_ranking'] is None
    with pytest.raises(ValueError, match='duplicates'):
        compare_assessments([(first,[]),(first,[])])
    second['groupid'] = 1
    with pytest.raises(ValueError, match='scope'):
        compare_assessments([(first,[]),(second,[])])


def test_incomplete_duplicate_population_unknown_flags_and_out_of_range_fail():
    cursor = evidence()
    with pytest.raises(ValueError, match='Complete'):
        summarize_assessment(cursor | {'done':False}, [11])
    with pytest.raises(ValueError, match='Duplicate'):
        summarize_assessment(cursor, [11,11])
    cursor['records'][0]['excluded'] = None
    with pytest.raises(ValueError):
        summarize_assessment(cursor,[11])
    cursor['records'][0]['excluded'] = 0
    cursor['records'][0]['finalgrade'] = '11'
    with pytest.raises(ValueError, match='outside'):
        summarize_assessment(cursor,[11])
