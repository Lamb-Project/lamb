"""CLI half of the common Creator API contract exercised by AAC backend tests."""
import importlib,json,shlex
from pathlib import Path
from unittest.mock import MagicMock,patch
import pytest
from typer.testing import CliRunner
from lamb_cli.main import app

CASES=json.loads((Path(__file__).resolve().parents[3]/'backend/tests/fixtures/educator_parity_requests.json').read_text())

@pytest.mark.parametrize('command,method,path,kwargs',[c for c in CASES if c[0]!='whoami'])
def test_cli_requests_match_liteshell_contract(command,method,path,kwargs):
    tokens=shlex.split(command);module=importlib.import_module('lamb_cli.commands.'+tokens[0])
    client=MagicMock();client.__enter__.return_value=client
    getattr(client,method).return_value={'success':True,'rubric':{'title':'Preview'},'templates':[], 'plugins':[], 'knowledge_bases':[], 'messages':[]}
    if method=='delete':tokens+=['--confirm']
    with patch.object(module,'get_client',return_value=client):
        result=CliRunner().invoke(app,tokens)
    assert result.exit_code==0,str(result.exception)+' '+result.output
    getattr(client,method).assert_called_once_with(path,**kwargs)
