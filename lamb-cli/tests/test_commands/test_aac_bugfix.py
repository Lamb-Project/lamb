"""CLI contract regressions for #469 (including superseded #460/#461)."""
import json
import pytest
from typer.testing import CliRunner
from lamb_cli.main import app

runner = CliRunner()

@pytest.mark.parametrize('command,published',[('publish',True),('unpublish',False)])
def test_publication_json_and_request(httpx_mock,mock_token,command,published):
    httpx_mock.add_response(json={'success':True,'message':'updated'})
    result=runner.invoke(app,['assistant',command,'42','-o','json'])
    assert result.exit_code==0,result.output
    assert json.loads(result.stdout)['published'] is published
    request=httpx_mock.get_request()
    assert request.method=='PUT'
    assert json.loads(request.content)=={'publish_status':published}

@pytest.mark.parametrize('status',[401,403,404,409,422,500,503])
def test_publication_http_failure_nonzero(httpx_mock,mock_token,status):
    httpx_mock.add_response(status_code=status,json={'detail':'denied'})
    result=runner.invoke(app,['assistant','publish','42','-o','json'])
    assert result.exit_code!=0
    assert '"published": true' not in result.stdout

def test_publication_semantic_failure_nonzero(httpx_mock,mock_token):
    httpx_mock.add_response(json={'success':False,'error':'not allowed'})
    result=runner.invoke(app,['assistant','publish','42','-o','json'])
    assert result.exit_code!=0

@pytest.mark.parametrize('org',[None,'other-campus'])
def test_user_create_org_and_json(httpx_mock,mock_token,org):
    httpx_mock.add_response(json={'id':7,'email':'person@example.test','organization_id':12})
    args=['user','create','person@example.test','Test User','synthetic-password','-o','json']
    if org: args+=['--org',org]
    result=runner.invoke(app,args)
    assert result.exit_code==0,result.output
    assert json.loads(result.stdout)['organization_id']==12
    assert httpx_mock.get_request().url.params.get('org')==org

@pytest.mark.parametrize('domain',['example.test','example.local','example.invalid','example.com'])
def test_whoami_serialized_identity(httpx_mock,mock_token,domain):
    httpx_mock.add_response(json={'id':7,'email':'person@'+domain,'name':'Test'})
    result=runner.invoke(app,['whoami','-o','json'])
    assert result.exit_code==0,result.output
    assert json.loads(result.stdout)['email']=='person@'+domain

@pytest.mark.parametrize('command,args,suffix',[
    ('chats',['--page','2','--per-page','5','--search','some text'],'/chats'),
    ('chat-detail',['chat-123'],'/chats/chat-123'),
    ('stats',['--start-date','2026-01-01'],'/stats'),
    ('timeline',['--period','week'],'/timeline'),
])
def test_analytics_cli_endpoint(httpx_mock,mock_token,command,args,suffix):
    httpx_mock.add_response(json={'chats':[],'stats':{},'data':[]})
    result=runner.invoke(app,['analytics',command,'12',*args,'-o','json'])
    assert result.exit_code==0,result.output
    json.loads(result.stdout)
    assert httpx_mock.get_request().url.path=='/creator/analytics/assistant/12'+suffix


def test_update_json_preserves_custom_metadata_and_prompt(httpx_mock,mock_token):
    existing={'id':42,'name':'Tutor','system_prompt':'Keep me', 'metadata':json.dumps({'custom':'keep','capabilities':{'custom_cap':True},'llm':'old','connector':'openai'})}
    httpx_mock.add_response(method='GET',json=existing)
    httpx_mock.add_response(method='PUT',json={'success':True,'message':'Updated'})
    result=runner.invoke(app,['assistant','update','42','--llm','new','--description','','-o','json'])
    assert result.exit_code==0,result.output
    assert json.loads(result.stdout)['success'] is True
    body=json.loads(httpx_mock.get_requests()[-1].content)
    assert body['description']==''
    assert 'system_prompt' not in body
    metadata=json.loads(body['metadata'])
    assert metadata['custom']=='keep'
    assert metadata['capabilities']['custom_cap'] is True


@pytest.mark.parametrize('extra',[{'first_message':'Here is **my analysis**','stats':{'tool_calls':1}}, {'error':'Startup provider unavailable'}])
def test_skill_start_json_remains_machine_readable(httpx_mock,mock_token,extra):
    response={'id':'session-123','assistant_id':42,**extra}
    httpx_mock.add_response(json=response)
    result=runner.invoke(app,['aac','start','--skill','test-and-evaluate','--assistant','42','-o','json'])
    assert result.exit_code==0,result.output
    assert json.loads(result.stdout)==response
