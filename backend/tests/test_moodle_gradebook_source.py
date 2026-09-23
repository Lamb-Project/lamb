from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from moodle_cli.client.readonly import READ_ALLOWLIST
from lamb.moodle.analytics.client import GRADEBOOK_SCOPE_FUNCTION, GRADEBOOK_GRADES_FUNCTION, MAX_EVENT_BYTES
from lamb.moodle.analytics.gradebook_authorization import validate_gradebook_scope
from tests.test_moodle_analytics_client import client

SCOPE = {'course_id': 7, 'grade_item_id': 2, 'group_id': 0}
RESPONSE = {'authorized': True, 'courseid': 7, 'gradeitemid': 2, 'groupid': 0}


def test_exact_authority_without_grade_read():
    source = SimpleNamespace(call=Mock(return_value=RESPONSE))
    validate_gradebook_scope(source, SCOPE)
    source.call.assert_called_once_with(GRADEBOOK_SCOPE_FUNCTION, courseid=7, gradeitemid=2, groupid=0)


@pytest.mark.parametrize('change', [{'authorized': 1}, {'courseid': 8}, {'gradeitemid': 3},
    {'groupid': 1}, {'gradeitemid': 2.0}, {'grades': []}])
def test_mismatched_authority_denied(change):
    with pytest.raises(PermissionError):
        validate_gradebook_scope(SimpleNamespace(call=lambda *a, **k: RESPONSE | change), SCOPE)


@pytest.mark.parametrize('change', [{'course_id': True}, {'grade_item_id': 0}, {'group_id': -1}, {'extra': 1}])
def test_invalid_scope_never_calls(change):
    with pytest.raises(PermissionError):
        validate_gradebook_scope(SimpleNamespace(call=lambda *a, **k: pytest.fail('Unexpected source call')), SCOPE | change)


@pytest.mark.parametrize('function,budget', [(GRADEBOOK_SCOPE_FUNCTION, 4096), (GRADEBOOK_GRADES_FUNCTION, MAX_EVENT_BYTES)])
def test_bounded_transport_preserves_readonly(function, budget):
    before = set(READ_ALLOWLIST)
    with client(lambda request: httpx.Response(200, json=RESPONSE)) as source:
        assert source.call(function, courseid=7, gradeitemid=2) == RESPONSE
    assert set(READ_ALLOWLIST) == before
    with client(lambda request: httpx.Response(200, content=b'x' * (budget+1))) as source:
        with pytest.raises(ValueError, match='byte budget'):
            source.call(function, courseid=7, gradeitemid=2)


@pytest.mark.parametrize('change', [{'courseid': True}, {'gradeitemid': '2'}, {'gradeitemid': 0},
    {'groupid': -1}, {'wstoken': 'override'}, {'fields': 'feedback'}, {'userid': 1}])
@pytest.mark.parametrize('function', [GRADEBOOK_SCOPE_FUNCTION, GRADEBOOK_GRADES_FUNCTION])
def test_invalid_parameters_never_request(function, change):
    with client(lambda request: pytest.fail('Unexpected network request')) as source:
        with pytest.raises(ValueError):
            source.call(function, **({'courseid': 7, 'gradeitemid': 2} | change))


@pytest.mark.parametrize('change', [{'limit': 201}, {'limit': True}, {'limit': 0}, {'afterid': 2},
    {'afterid': -1}, {'throughid': -1}, {'afterid': 4, 'throughid': 3}])
def test_invalid_page_bounds(change):
    with client(lambda request: pytest.fail('Unexpected network request')) as source:
        with pytest.raises(ValueError):
            source.call(GRADEBOOK_GRADES_FUNCTION, **({'courseid': 7, 'gradeitemid': 2} | change))


def test_scope_does_not_accept_paging_or_leak_denial_text():
    with client(lambda request: pytest.fail('Unexpected network request')) as source:
        with pytest.raises(ValueError):
            source.call(GRADEBOOK_SCOPE_FUNCTION, courseid=7, gradeitemid=2, limit=1)
    with client(lambda request: httpx.Response(200, json={'exception': 'error', 'errorcode': 'nopermissions', 'message': 'SECRET'})) as source:
        with pytest.raises(PermissionError, match='no longer available') as error:
            validate_gradebook_scope(source, SCOPE)
        assert 'SECRET' not in str(error.value)
