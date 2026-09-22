from unittest.mock import patch
from types import SimpleNamespace
import pytest
from lamb.moodle.analytics.access import course_access


class Client:
    readonly = True
    def __init__(self, pages): self.pages = iter(pages); self.calls = []
    def checkpoint(self): pass
    def call(self, function, **params): self.calls.append((function,params)); return next(self.pages)


def user(identity, value=None, **extra):
    return {'id':identity,'roles':[{'shortname':'student'}], 'lastcourseaccess':value,
            'lastaccess':999, 'email':'DO_NOT_RETAIN', **extra}


def collect(client, **params):
    with patch('lamb.moodle.analytics.access.MoodleScope') as scope, patch('lamb.moodle.analytics.access.time.time',return_value=1000):
        scope.return_value.require_teacher.return_value=7
        scope.return_value.own_courses.return_value={7:SimpleNamespace(fullname='Synthetic course')}
        return course_access(client, 12, 7, since=500, **params)


def test_recency_uses_course_access_not_site_access():
    result = collect(Client([[user(1,700),user(2,100),user(3,0),user(4)]]))
    assert result['metrics'] == {'recent':1,'older':1,'no_course_access_recorded':1,'unknown':1}
    assert result['course_name'] == 'Synthetic course'
    assert not result['coverage']['complete']
    assert 'DO_NOT_RETAIN' not in str(result) and 'lastaccess' not in str(result['rows'])


def test_teacher_and_unknown_role_do_not_become_inactive_students():
    result = collect(Client([[user(1,0,roles=[{'shortname':'editingteacher'}]),{'id':2}]]))
    assert result['rows'] == [] and result['coverage']['role_unknown'] == 1
    assert result['coverage']['non_student_rows'] == 1
    assert not result['coverage']['complete']


def test_historical_window_cannot_be_reconstructed():
    with pytest.raises(ValueError): collect(Client([]), until=900)


def test_population_pagination_and_cap_are_explicit():
    client = Client([[user(i,600) for i in range(1,201)], [user(201,600)]])
    result = collect(client)
    assert result['coverage']['complete'] and result['metrics']['recent'] == 201
    assert {'name':'limitfrom','value':200} in client.calls[1][1]['options']
    result=collect(Client([[user(i+1+p*200,600) for i in range(200)] for p in range(5)]))
    assert not result['coverage']['population_exhausted'] and not result['coverage']['complete']


def test_duplicate_pages_fail_instead_of_double_counting():
    with pytest.raises(ValueError): collect(Client([[user(1,600),user(1,600)]]))


@pytest.mark.parametrize('value', [True,-1,1001,'700'])
def test_invalid_or_hidden_timestamp_stays_unknown(value):
    assert collect(Client([[user(1,value)]]))['rows'][0]['status'] == 'unknown'
