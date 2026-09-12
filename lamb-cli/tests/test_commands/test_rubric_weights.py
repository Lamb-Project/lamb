"""Partial rubric edits preserve IDs and reject ambiguous/invalid weight changes."""
import copy
import json
from urllib.parse import parse_qs
import pytest
from typer.testing import CliRunner
from lamb_cli.main import app
from lamb_cli.commands.rubric import _apply_weights

CRITERIA=[{'id':'criterion-1','name':'Evidence','weight':50,'levels':[{'id':'level-1','score':3,'label':'Strong'}]},
          {'id':'criterion-2','name':'Reasoning','weight':50,'levels':[{'id':'level-2','score':1,'label':'Weak'}]}]

@pytest.mark.parametrize('weights',['{}','[]','{"Missing":100}','{"Evidence":-1}','{"Evidence":true}','{"Evidence":NaN}','{"Evidence":60}'])
def test_invalid_changes(weights):
    with pytest.raises(ValueError):_apply_weights(CRITERIA,weights)

def test_duplicate_names_rejected():
    with pytest.raises(ValueError):_apply_weights([CRITERIA[0],CRITERIA[0]],'{"Evidence":50}')

def test_cli_patches_weights_preserving_payload(mock_token,mock_server_url,httpx_mock):
    current={'rubric_data':{'title':'Original','description':'Keep me','criteria':CRITERIA,'maxScore':6,'metadata':{'subject':'Science'}}}
    httpx_mock.add_response(method='GET',url=mock_server_url+'/creator/rubrics/r1',json=current)
    httpx_mock.add_response(method='PUT',url=mock_server_url+'/creator/rubrics/r1',json={'rubric':{}})
    result=CliRunner().invoke(app,['rubric','update','r1','--weights','{"Evidence":60,"Reasoning":40}','-o','json'])
    assert result.exit_code==0,result.output
    form=parse_qs(httpx_mock.get_requests()[-1].content.decode())
    expected=copy.deepcopy(CRITERIA);expected[0]['weight']=60;expected[1]['weight']=40
    assert json.loads(form['criteria'][0])==expected
    assert form['description']==['Keep me']
    assert form['subject']==['Science']
    assert 'weights' not in form
    assert CRITERIA[0]['weight']==50
