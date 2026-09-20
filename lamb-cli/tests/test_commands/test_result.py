"""Private result readback uses the same bounded server pages as LiteShell."""
import json
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from lamb_cli.main import app


def test_read_page_and_follow_exact_json_pointer():
    identity='12345678-1234-1234-1234-123456789abc'
    client=MagicMock();client.__enter__.return_value=client
    client.get.return_value={'kind':'string','text':'évidence','next_offset':None}
    with patch('lamb_cli.commands.result.get_client',return_value=client):
        result=CliRunner().invoke(app,['result','read',identity,'--path','/data/odd~1key','--offset','4'])
    assert result.exit_code==0,result.output
    client.get.assert_called_once_with('/creator/aac/results/'+identity,params={'path':'/data/odd~1key','offset':4})
    assert json.loads(result.output)['text']=='évidence'


def test_bad_uuid_and_negative_offset_do_not_call_server():
    with patch('lamb_cli.commands.result.get_client') as client:
        for args in [['bad'],['12345678-1234-1234-1234-123456789abc','--offset','-1']]:
            result=CliRunner().invoke(app,['result','read',*args])
            assert result.exit_code!=0
        client.assert_not_called()
