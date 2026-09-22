from unittest.mock import patch

import pytest

from lamb.moodle.analytics.assignments import grading_queue
from lamb.moodle.forum_activity import TaskCancelled


class Client:
    readonly = True
    def __init__(self):
        self.assignments = [{'id': 1, 'name': 'Essay', 'teamsubmission': 0, 'markingworkflow': 1}]
        self.summary = dict(participantcount=6, submissiondraftscount=1,
                            submissionssubmittedcount=4, submissionsneedgradingcount=2, submissionsenabled=True)
        self.warning = False
        self.calls = []
    def checkpoint(self): pass
    def call(self, function, **params):
        self.calls.append((function, params))
        if function == 'mod_assign_get_assignments':
            return {'courses':[{'id':7, 'fullname':'Synthetic', 'assignments':self.assignments}]}
        return {'gradingsummary':self.summary, 'warnings':[{}] if self.warning else [],
                'lastattempt':{'private_response':'DO NOT RETAIN'}}


def collect(client):
    with patch('lamb.moodle.analytics.assignments.MoodleScope') as scope:
        scope.return_value.require_teacher.return_value = 7
        return grading_queue(client, 12, 7)


def test_grading_queue_retains_exact_counts_not_submission_content():
    client = Client(); result = collect(client)
    assert result['rows'][0]['needs_grading'] == 2
    assert result['rows'][0]['marking_workflow'] is True
    assert result['rows'][0]['grade_released'] is None
    assert result['metrics']['needs_grading'] == 2 and result['coverage']['complete']
    assert 'DO NOT RETAIN' not in str(result)
    assert client.calls[-1][1] == {'assignid':1,'userid':12,'groupid':0}


@pytest.mark.parametrize('bad', [None, -1, True, 7, '2'])
def test_unknown_or_inconsistent_count_is_not_zero(bad):
    client = Client(); client.summary['submissionsneedgradingcount'] = bad
    result = collect(client)
    assert result['rows'][0]['needs_grading'] is None
    assert not result['coverage']['complete']


def test_team_and_offline_are_explicit_exclusions():
    client = Client(); client.assignments[0]['teamsubmission'] = 1
    result = collect(client)
    assert result['rows'][0]['reason'] == 'team_submission_count_not_supported'
    assert len(client.calls) == 1
    client = Client(); client.summary['submissionsenabled'] = False
    assert collect(client)['rows'][0]['reason'] == 'online_submissions_disabled'


def test_warnings_and_zero_pending_are_distinct():
    client = Client(); client.warning = True
    assert collect(client)['rows'][0]['needs_grading'] is None
    client.warning = False; client.summary['submissionsneedgradingcount'] = 0
    assert collect(client)['rows'][0]['needs_grading'] == 0


def test_empty_and_capped_coverage():
    client = Client(); client.assignments = []
    result = collect(client)
    assert result['coverage']['complete'] and result['rows'] == []
    client.assignments = [{'id':i,'name':'Task','teamsubmission':1} for i in range(101)]
    result = collect(client)
    assert len(result['rows']) == 100 and result['coverage']['omitted_by_limit'] == 1


def test_cancel_and_denied_scope_withhold_result():
    client = Client(); client.checkpoint = lambda: (_ for _ in ()).throw(TaskCancelled())
    with pytest.raises(TaskCancelled): collect(client)
    with patch('lamb.moodle.analytics.assignments.MoodleScope') as scope:
        scope.return_value.require_teacher.side_effect = PermissionError()
        with pytest.raises(PermissionError): grading_queue(Client(), 12, 7)
