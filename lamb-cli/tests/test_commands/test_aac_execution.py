import json
import pytest
from typer.testing import CliRunner
from lamb_cli.main import app

runner = CliRunner()

@pytest.mark.parametrize('args,method,path,body', [
    (['mode', 'session', 'auto'], 'PUT', '/execution', {'mode': 'auto'}),
    (['new-task', 'session'], 'PUT', '/execution', {'new_task': True}),
    (['report', 'session', 'report'], 'GET', '/reports/report', None),
    (['changes', 'session'], 'GET', '/changes', None),
])
def test_execution_controls_and_readback(httpx_mock, mock_token, args, method, path, body):
    httpx_mock.add_response(json={'status': 'ok'})
    result = runner.invoke(app, ['aac', *args])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {'status': 'ok'}
    request = httpx_mock.get_request()
    assert request.method == method and request.url.path == '/creator/aac/sessions/session' + path
    if body:
        assert json.loads(request.content) == body
