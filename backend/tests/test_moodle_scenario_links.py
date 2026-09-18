from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from lamb.aac import learning_scenarios as scenarios
from lamb.aac.scenario_router import router
from lamb.auth_context import get_auth_context


def test_links_api_create_update_duplicate_clear_and_revision(tmp_path,monkeypatch):
    monkeypatch.setattr(scenarios,'ROOT',tmp_path)
    auth=SimpleNamespace(user={'id':7},organization={'id':1})
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_auth_context]=lambda:auth
    c=TestClient(app)
    created=c.post('/learning-scenarios',json={'title':'Demo','content':'Teacher context','links':{'moodle_course_id':10}})
    assert created.status_code==200
    item=created.json();url='/learning-scenarios/'+item['id']
    assert item['links']=={'moodle_course_id':10}
    copy=c.post(url+'/duplicate',json={'title':'Copy'}).json()
    assert copy['links']==item['links'] and copy['id']!=item['id']
    changed=c.put(url,json={'revision':1,'content':'Updated context'}).json()
    assert changed['links']==item['links']
    assert c.put(url,json={'revision':1,'links':{}}).status_code==409
    cleared=c.put(url,json={'revision':2,'links':{}}).json()
    assert cleared['links']=={} and cleared['content']=='Updated context'
    assert c.get('/learning-scenarios/'+copy['id']).json()['links']=={'moodle_course_id':10}
    auth.user['id']=8
    assert c.get(url).status_code==404


@pytest.mark.parametrize('links',[{'moodle_course_id':True},{'moodle_course_id':0},{'moodle_course_id':'10'},{'file_path':'/tmp/x'},[]])
def test_invalid_links_cannot_be_persisted(tmp_path,monkeypatch,links):
    monkeypatch.setattr(scenarios,'ROOT',tmp_path)
    store=scenarios.ScenarioStore(SimpleNamespace(user={'id':7},organization={'id':1}))
    with pytest.raises(HTTPException):store.create('Bad links','',links)
    assert store.list()['scenarios']==[]


def test_liteshell_link_commands_validate_before_execution():
    import asyncio
    from unittest.mock import AsyncMock
    from lamb.aac.liteshell.shell import prepare_command
    from lamb.aac.liteshell.commands import learning_scenario_update
    key='00000000-0000-0000-0000-000000000001'
    _,args,kwargs,_=prepare_command(f'lamb learning-scenario update {key} --revision 1 --moodle-course-id none')
    http=SimpleNamespace(put=AsyncMock(return_value={'links':{}}))
    asyncio.run(learning_scenario_update(SimpleNamespace(http=http),args,kwargs))
    assert http.put.call_args.kwargs['json']=={'revision':1,'links':{}}
    for bad in ('-1','0','abc'):
        with pytest.raises(ValueError):prepare_command(f'lamb learning-scenario update {key} --revision 1 --moodle-course-id {bad}')


def test_cli_create_and_clear_link():
    from unittest.mock import MagicMock,patch
    from typer.testing import CliRunner
    from lamb_cli.commands.learning_scenario import app
    client=MagicMock();client.post.return_value={};client.put.return_value={}
    with patch('lamb_cli.commands.learning_scenario.get_client') as get:
        get.return_value.__enter__.return_value=client
        result=CliRunner().invoke(app,['create','Demo','--moodle-course-id','10'])
        assert result.exit_code==0,result.output
        assert client.post.call_args.kwargs['json']['links']=={'moodle_course_id':10}
        result=CliRunner().invoke(app,['update','owned','--revision','1','--moodle-course-id','none'])
        assert result.exit_code==0,result.output
        assert client.put.call_args.kwargs['json']=={'revision':1,'links':{}}
