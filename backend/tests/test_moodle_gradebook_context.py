from types import SimpleNamespace
from unittest.mock import Mock, patch
import httpx
import pytest
from lamb.moodle.analytics.gradebook_context import gradebook_context, target_batch
from lamb.moodle.analytics.client import GRADEBOOK_POPULATION_FUNCTION
from tests.test_moodle_analytics_client import client

SCOPE = {'course_id':7,'grade_item_id':2,'group_id':0}


def response(ids, **changes):
    return dict(schema_version=1, courseid=7, gradeitemid=2, groupid=0,
        included_userids=ids, excluded_userids=[], population_basis='active_candidate_population_manual_item',
        collected_at=100, atomic_snapshot=False, **changes)


def test_context_batches_and_fingerprint_ignore_observation_clock():
    students = set(range(1,502))
    source = SimpleNamespace(call=Mock(side_effect=lambda function, **p: response(p['userids'])), checkpoint=Mock())
    with patch('lamb.moodle.analytics.gradebook_context.validate_gradebook_scope') as auth, \
            patch('lamb.moodle.analytics.gradebook_context.MoodleScope'), \
            patch('lamb.moodle.analytics.gradebook_context._students',return_value=(students,{'population_exhausted':True,'role_unknown':0})):
        first = gradebook_context(source,3,SCOPE)
        assert [len(call.kwargs['userids']) for call in source.call.call_args_list] == [200,200,101]
        assert auth.call_count == 2
        source.call.side_effect = lambda function, **p: response(p['userids']) | {'collected_at':200}
        second = gradebook_context(source,3,SCOPE)
        assert first['fingerprint'] == second['fingerprint']
        assert first['students'] == sorted(students)
        assert second['first_observed_at'] == 200


@pytest.mark.parametrize('change', [{'included_userids':[1,1]}, {'included_userids':[True]},
    {'included_userids':[2]}, {'included_userids':[]}, {'excluded_userids':[1]},
    {'courseid':8}, {'gradeitemid':2.0}, {'schema_version':True}, {'atomic_snapshot':True},
    {'population_basis':'current_access'}, {'collected_at':0}])
def test_partition_or_contract_mismatch(change):
    source = SimpleNamespace(call=lambda *a,**k: response([1]) | change)
    with pytest.raises(ValueError):
        target_batch(source,SCOPE,[1])


def test_empty_population_is_verified_and_incomplete_roster_fails():
    source=SimpleNamespace(call=Mock(return_value=response([])),checkpoint=Mock())
    with patch('lamb.moodle.analytics.gradebook_context.validate_gradebook_scope'), \
            patch('lamb.moodle.analytics.gradebook_context.MoodleScope'), \
            patch('lamb.moodle.analytics.gradebook_context._students',return_value=(set(),{'population_exhausted':True,'role_unknown':0})) as roster:
        assert gradebook_context(source,3,SCOPE)['students']==[]
        source.call.assert_called_once_with(GRADEBOOK_POPULATION_FUNCTION,courseid=7,gradeitemid=2,groupid=0,userids=[])
        roster.return_value=(set(),{'population_exhausted':False,'role_unknown':0})
        with pytest.raises(ValueError,match='Complete'):
            gradebook_context(source,3,SCOPE)


@pytest.mark.parametrize('change', [{'userids':[True]}, {'userids':[1,1]}, {'userids':list(range(1,202))},
    {'userids':'1'}, {'courseid':True}, {'gradeitemid':0}, {'groupid':-1}, {'wstoken':'override'}])
def test_population_transport_rejects_bad_requests(change):
    with client(lambda request:pytest.fail('Unexpected request')) as source:
        with pytest.raises(ValueError):
            source.call(GRADEBOOK_POPULATION_FUNCTION,**({'courseid':7,'gradeitemid':2,'userids':[1]}|change))


def test_population_response_byte_budget():
    with client(lambda request:httpx.Response(200,content=b'x'*16385)) as source:
        with pytest.raises(ValueError,match='byte budget'):
            source.call(GRADEBOOK_POPULATION_FUNCTION,courseid=7,gradeitemid=2,userids=[])
