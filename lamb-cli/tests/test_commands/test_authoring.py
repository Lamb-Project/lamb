import json
from urllib.parse import parse_qs
import pytest
from typer.testing import CliRunner
from lamb_cli.main import app
runner=CliRunner()

def test_rubric_create_json(httpx_mock,mock_token):
    httpx_mock.add_response(json={'success':True,'rubric':{'rubric_id':'r1'}})
    result=runner.invoke(app,['rubric','create','Clarity','--criteria','[{"name":"Clarity"}]','-o','json'])
    assert result.exit_code==0,result.output
    assert json.loads(result.stdout)['rubric_id']=='r1'
    body=parse_qs(httpx_mock.get_request().content.decode());assert body['title']==['Clarity']


def test_rubric_edit_preserves(httpx_mock,mock_token):
    old={'title':'Old','description':'Keep','criteria':[{'name':'C'}],'metadata':{'subject':'Math'},'maxScore':10}
    httpx_mock.add_response(method='GET',json={'rubric_data':old})
    httpx_mock.add_response(method='PUT',json={'success':True})
    result=runner.invoke(app,['rubric','update','r1','--title','New','-o','json'])
    assert result.exit_code==0,result.output
    body=parse_qs(httpx_mock.get_requests()[-1].content.decode());assert body['description']==['Keep'];assert json.loads(body['criteria'][0])==old['criteria']

@pytest.mark.parametrize('criteria',['null','{}','[]','broken'])
def test_bad_rubric_input(criteria,mock_token):
    assert runner.invoke(app,['rubric','create','x','--criteria',criteria]).exit_code!=0


def test_file_and_rubric_binding(httpx_mock,mock_token):
    httpx_mock.add_response(method='GET',json={'valid':True})
    httpx_mock.add_response(method='GET',json={'rubric_id':'r1'})
    httpx_mock.add_response(method='POST',json={'assistant_id':1})
    result=runner.invoke(app,['assistant','create','x','--connector','openai','--llm','fake','--file-path','7/doc.md','--rubric-id','r1','--rubric-format','json','-o','json'])
    assert result.exit_code==0,result.output
    md=json.loads(json.loads(httpx_mock.get_requests()[-1].content)['metadata']);assert md['file_path']=='7/doc.md';assert md['rubric_id']=='r1';assert md['rubric_format']=='json'


def test_kb_upload_plugin_returns_evidence(httpx_mock,mock_token,tmp_path):
    file=tmp_path/'source.pdf';file.write_bytes(b'%PDF-example')
    httpx_mock.add_response(json={'job_id':'j1'})
    result=runner.invoke(app,['kb','upload','3',str(file),'--plugin','markitdown_ingest','-o','json'])
    assert result.exit_code==0,result.output
    data=json.loads(result.stdout);assert data['verification_required'];assert data['ingestion_response']==[{'job_id':'j1'}]
    assert b'%PDF-example' in httpx_mock.get_request().content


def test_attach_json(httpx_mock,mock_token,tmp_path):
    file=tmp_path/'source.md';file.write_text('fact')
    httpx_mock.add_response(json={'path':'7/abc.md','name':'source.md','size':4})
    result=runner.invoke(app,['aac','attach',str(file),'-o','json']);assert result.exit_code==0;assert json.loads(result.stdout)['path']=='7/abc.md'
