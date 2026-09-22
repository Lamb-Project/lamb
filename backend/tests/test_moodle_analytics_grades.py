from unittest.mock import patch

import pytest

from lamb.moodle.analytics.grades import grade_distribution


class Client:
    def __init__(self, grades):
        self.response = {'assignments':[{'assignmentid':42, 'grades':[
            {'userid':i+1,'attemptnumber':0,'grade':g} for i,g in enumerate(grades)]}], 'warnings':[]}
    def checkpoint(self): pass
    def call(self, name, **kwargs):
        assert name == 'mod_assign_get_grades'
        assert kwargs == {'assignmentids':[42], 'since':0}
        return self.response


def collect(client, maximum=20, **overrides):
    assignment = {'id':42,'grade':maximum,'teamsubmission':0,'markingworkflow':1, **overrides}
    with patch('lamb.moodle.analytics.grades.validate_grade_scope'), \
         patch('lamb.moodle.analytics.grades.assignment_inventory', return_value=(7,'Course',[assignment])), \
         patch('lamb.moodle.analytics.grades._students', return_value=(set(range(1,7)),
             {'population_exhausted':True,'role_unknown':0,'student_rows':6})):
        return grade_distribution(client, 12, 7, 42)


def test_independent_histogram_and_statistics_oracle():
    result = collect(Client(['0','2','10','20','-1']))
    assert [r['count'] for r in result['rows']] == [1,1,0,0,0,1,0,0,0,1]
    assert result['metrics'] == {'valid_n':4,'missing_n':2,'population_n':6,'zero_n':1,
        'mean':40.0,'q1':7.5,'median':30.0,'q3':62.5}
    assert result['grade_released'] is None
    assert result['publication_status'] == 'not_collected'
    assert result['coverage']['ungraded_sentinel_records'] == 1
    assert 'userid' not in str(result)


def test_no_grades_warning_is_missing_not_denied():
    c = Client([])
    c.response = {'assignments':[], 'warnings':[{'item':'assignment','itemid':42,'warningcode':'3'}]}
    result = collect(c)
    assert result['metrics']['valid_n'] == 0 and result['metrics']['missing_n'] == 6
    assert result['metrics']['mean'] is None
    assert result['metrics']['zero_n'] == 0


def test_lowest_bin_does_not_imply_exact_zero():
    result = collect(Client(['0','1','-1']))
    assert result['rows'][0]['count'] == 2
    assert result['metrics']['zero_n'] == 1
    assert result['metrics']['missing_n'] == 4


@pytest.mark.parametrize('value', [None,True,'NaN','Infinity','no grade','-2','21'])
def test_invalid_values_do_not_turn_into_zero(value):
    with pytest.raises(ValueError): collect(Client([value]))


@pytest.mark.parametrize('maximum', [0,-1,None,True,'NaN'])
def test_scale_or_invalid_maximum_rejected(maximum):
    with pytest.raises(ValueError): collect(Client(['1']), maximum)


def test_denial_warning_propagates():
    c = Client([]); c.response['warnings'] = [{'warningcode':'1'}]
    with pytest.raises(PermissionError): collect(c)


def test_duplicate_or_wrong_scope_rejected():
    c = Client(['1','2']); c.response['assignments'][0]['grades'][1]['userid'] = 1
    with pytest.raises(ValueError): collect(c)
    c = Client(['1']); c.response['assignments'][0]['assignmentid'] = 43
    with pytest.raises(ValueError): collect(c)


def test_nonpopulation_grade_is_excluded_and_team_is_rejected():
    c = Client(['10']); c.response['assignments'][0]['grades'][0]['userid'] = 100
    result = collect(c)
    assert result['metrics']['valid_n'] == 0
    assert result['coverage']['excluded_nonpopulation_records'] == 1
    with pytest.raises(ValueError): collect(Client(['1']), teamsubmission=1)


def test_source_bound_and_missing_response_fail_closed():
    c = Client(['1']*1001)
    with pytest.raises(ValueError): collect(c)
    c.response = {'assignments':[], 'warnings':[]}
    with pytest.raises(ValueError): collect(c)
