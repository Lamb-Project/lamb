import asyncio
from unittest.mock import patch
import pytest
import respx
from httpx import Response
from lamb.moodle.charts import ChartStore
from lamb.aac.liteshell.shell import LiteShell
from tests.test_moodle_store import stores
from tests.test_moodle_runtime import runtime

SCOPE = {'course_id': 7, 'quiz_id': 2, 'group_id': 3}
RESPONSE = {'authorized': True, 'courseid': 7, 'quizid': 2, 'groupid': 3}


@respx.mock
def test_saved_quiz_read_and_list_recheck_scope_without_attempt_collection(stores, tmp_path):
    rt = runtime(stores); rt.cache_root = tmp_path
    charts = ChartStore(rt)
    identity = charts.save({'title': 'Quiz', 'course_id': 7, 'course_name': 'Course',
        'as_of': '2026-09-23T12:00:00Z', 'timezone': 'UTC', 'coverage': {}, 'rows': [],
        'quiz_scopes': [SCOPE]}, dict(rt.result_binding(), course_id=7, quiz_scopes=[SCOPE]),
        command='moodle.analytics.run')
    route = respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200, json=RESPONSE))
    with patch('lamb.moodle.runtime.MoodleScope'):
        assert charts.read(identity)['chart_id'] == identity
        assert charts.listing()['items'][0]['quiz_scopes'] == [SCOPE]
        route.mock(return_value=Response(200, json={'exception': 'required_capability_exception', 'errorcode': 'nopermissions'}))
        with pytest.raises(PermissionError):
            charts.read(identity)
        assert charts.listing()['items'] == []
    from urllib.parse import parse_qs
    assert len(route.calls) == 4
    for call in route.calls:
        body = parse_qs(call.request.content.decode())
        assert body['wsfunction'] == ['local_lambanalytics_quiz_scope']
        assert body['quizid'] == ['2'] and body['groupid'] == ['3']


@pytest.mark.parametrize('extra', [
    {'quiz_scopes': [SCOPE]},
    {'course_id': 8, 'quiz_scopes': [SCOPE]},
    {'course_id': 7, 'quiz_scopes': {}},
    {'course_id': 7, 'quiz_scopes': [SCOPE]*21},
    {'course_id': 7, 'quiz_scopes': [dict(SCOPE, quiz_id=True)]},
])
def test_malformed_or_unbound_saved_quiz_denied(stores, extra):
    rt = runtime(stores)
    with patch('lamb.moodle.runtime.MoodleScope'), pytest.raises(PermissionError):
        rt.validate_result_binding(dict(rt.result_binding(), **extra), 'moodle.analytics.run')


@pytest.mark.parametrize('command,data', [
    ('moodle chart read 00000000-0000-0000-0000-000000000001', {'course_id': 7, 'quiz_scopes': [SCOPE]}),
    ('moodle analytics result 00000000-0000-0000-0000-000000000001', {'course_id': 7, 'quiz_scopes': [SCOPE]}),
    ('moodle chart list', {'items': [{'course_id': 7, 'quiz_scopes': [SCOPE]}]}),
])
def test_aac_result_retains_exact_quiz_binding(stores, command, data):
    rt = runtime(stores)
    shell = LiteShell('', '', 'fixture@test', 1, user_id=7, moodle=rt, allowed_commands=rt.available())
    with patch.object(rt, 'execute', return_value=data):
        result = asyncio.run(shell.execute(command))
    assert result.success, result.error
    assert result.result_binding['quiz_scopes'] == [SCOPE]
