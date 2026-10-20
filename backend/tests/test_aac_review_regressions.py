import asyncio
import json
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
import httpx
import pytest
from openai import APIError, BadRequestError
from lamb.aac.context_metrics import is_context_rejection, request_sizes
from lamb.aac.context_report import summarize
from lamb.aac.result_store import ResultStore, page, compact, provider_messages
from tests.test_aac_legacy import agent, message, turn, FakeStream


def test_stream_options_fallback_once_without_replaying_content_or_tools():
    a,p,_=agent([])
    error=BadRequestError('unsupported',response=httpx.Response(400,request=httpx.Request('POST','http://fixture')),
                          body={'error':{'message':'stream_options is not supported'}})
    p.chat.completions.create=AsyncMock(side_effect=[error,FakeStream(message('first')),FakeStream(message('second'))])
    assert asyncio.run(turn(a,True))=='first'
    assert asyncio.run(turn(a,True))=='second'
    calls=p.chat.completions.create.call_args_list
    assert 'stream_options' in calls[0].kwargs
    assert 'stream_options' not in calls[1].kwargs and 'stream_options' not in calls[2].kwargs
    assert calls[0].kwargs['messages']==calls[1].kwargs['messages']


def test_usage_compatibility_does_not_retry_unrelated_errors_or_midstream_failure():
    for midstream in (False,True):
        a,p,_=agent([])
        error=APIError('maximum context length exceeded',request=httpx.Request('POST','http://fixture'),body={'code':'context_length_exceeded'})
        class Broken(FakeStream):
            async def __aiter__(self):
                async for chunk in super().__aiter__():yield chunk
                raise error
        p.chat.completions.create=AsyncMock(return_value=Broken(message('partial')),side_effect=None if midstream else error)
        from lamb.aac.context_metrics import ContextSizeError
        with pytest.raises(ContextSizeError):asyncio.run(turn(a,True))
        assert p.chat.completions.create.await_count==1


def test_size_error_shapes_and_unrelated_value_errors():
    request=httpx.Request('POST','http://fixture')
    assert is_context_rejection(APIError('too big',request=request,body={'code':'context_length_exceeded'}))
    for text in ['Input token count exceeds maximum', 'requested 5000 tokens\nbut loaded context size is 1000']:
        assert is_context_rejection(BadRequestError(text,response=httpx.Response(400,request=request),body={'detail':text}))
    assert not is_context_rejection(ValueError('maximum context length'))


def test_string_page_uses_available_bytes_and_surrogates_are_lossless(tmp_path):
    storage=ResultStore(1,1,root=tmp_path)
    original='x'*40000+'\ud800'
    payload={'success':True,'action_executed':True,'data':original}
    result=compact(payload,store=storage,origin={'command':'assistant.update'})
    assert result['action_executed'] and result['context_result']['stored']
    env=storage.read(result['context_result']['result_id'])
    parts=[];offset=0
    while True:
        part=page(env,'/data',offset);parts.append(part['text'])
        if part['next_offset'] is None:break
        offset=part['next_offset']
    assert ''.join(parts)==original and len(parts)<10


def test_report_skips_invalid_records_and_does_not_crash_on_bad_usage(tmp_path):
    request={'session_id':'fixture','event':'context_request','data':dict(request_sizes({'messages':[]}),request_id='1',model='test')}
    response={'session_id':'fixture','event':'context_response','data':{'request_id':'1','outcome':'completed','usage':['bad']}}
    old={'session_id':'fixture','event':'context_request','data':{'measurement_version':1,'request_id':'old'}}
    path=tmp_path/'log.jsonl'
    path.write_bytes(b'\xff\n'+('\n'.join(map(json.dumps,[request,response,old]))+'\n').encode())
    result=summarize([path])
    assert result['requests']==1 and result['malformed_lines']==2
    assert result['requests_without_prompt_usage']==1


def test_approved_results_and_workflow_are_measured_without_sending_annotations():
    a,_,_=agent([])
    approved=a._result_message({'success':True,'data':'result'},'lamb assistant update 42 --description ok',role='user',prefix='[System: User approved. Action executed. Result: ',suffix=']')
    workflow={'role':'user','content':'[System: Workflow instructions]\nrecipe'}
    original=[approved,workflow]
    sent=provider_messages(original)
    assert not any(k.startswith('_aac_') for m in sent for k in m)
    result=request_sizes({'messages':sent},original)
    assert [r['command'] for r in result['tool_results']]==['assistant.update','workflow.instructions']


def test_results_endpoint_uses_real_jwt_dependency_and_enforces_owner(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from lamb.aac.router import router
    from lamb.auth import create_token
    from tests.test_auth_context import _make_user, _make_organization
    monkeypatch.setenv('LAMB_DB_PATH',str(tmp_path.resolve()))
    storage=ResultStore(10,1)
    identity=storage.save({'data':'owned evidence'},origin={'command':'assistant.get', 'authority': {
        'version': 1, 'resources': [{'kind': 'assistant', 'id': 42}]}})['result_id']
    app=FastAPI();app.include_router(router);client=TestClient(app)
    url=f'/aac/results/{identity}?path=/data'
    assert client.get(url).status_code in {401,403}
    token=create_token({'sub':'1','email':'fixture@test','role':'user'})
    with patch('lamb.auth_context._db') as database:
        database.get_creator_user_by_email.return_value=_make_user(email='fixture@test')
        database.get_organization_by_id.return_value=_make_organization()
        database.get_user_organization_role.return_value='member'
        database.get_assistant_by_id_with_publication.return_value = {'owner': 'fixture@test'}
        response=client.get(url,headers={'Authorization':'Bearer '+token})
        assert response.status_code==200,response.text
        assert response.json()['text']=='owned evidence'
        database.get_creator_user_by_email.return_value=_make_user(user_id=2,email='other@test')
        other=create_token({'sub':'2','email':'other@test','role':'user'})
        assert client.get(url,headers={'Authorization':'Bearer '+other}).status_code==404
        database.get_creator_user_by_email.return_value=_make_user(email='fixture@test')
        with patch('lamb.aac.result_reader.read_result',side_effect=ConnectionError('Temporary Moodle failure')):
            assert client.get(url,headers={'Authorization':'Bearer '+token}).status_code==503
