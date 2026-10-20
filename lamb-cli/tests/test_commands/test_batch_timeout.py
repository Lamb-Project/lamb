import json
import httpx
import pytest
from typer.testing import CliRunner
from lamb_cli.main import app
from lamb_cli.errors import NetworkError
runner=CliRunner()

@pytest.mark.parametrize('options,seconds',[([],900.0),(['--timeout','123'],123.0)])
def test_batch_wait_is_configurable(httpx_mock,mock_token,options,seconds):
    httpx_mock.add_response(json={'runs':[],'count':0})
    result=runner.invoke(app,['test','run','7','-o','json',*options])
    assert result.exit_code==0,result.output
    assert json.loads(result.stdout)['count']==0
    assert httpx_mock.get_request().extensions['timeout']['read']==seconds

def test_timeout_does_not_retry_and_explains_saved_runs(httpx_mock,mock_token):
    httpx_mock.add_exception(httpx.ReadTimeout('slow batch'))
    result=runner.invoke(app,['test','run','7','--timeout','1','-o','json'])
    assert result.exit_code!=0
    assert isinstance(result.exception,NetworkError)
    assert 'server may still be processing' in str(result.exception)
    assert 'lamb test runs 7 -o json' in str(result.exception)
    assert len(httpx_mock.get_requests())==1

def test_invalid_wait_never_sends_request(httpx_mock,mock_token):
    result=runner.invoke(app,['test','run','7','--timeout','0'])
    assert result.exit_code!=0
    assert not httpx_mock.get_requests()
