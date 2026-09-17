import copy
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from lamb.aac import learning_scenarios as ls
from lamb.aac.scenario_router import router
from lamb.auth_context import get_auth_context
from lamb.document_static import DocumentAwareStaticFiles


def auth(user=1, org=1):
    return SimpleNamespace(user={'id':user, 'email':f'{user}@test'}, organization={'id':org})

@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, 'ROOT', tmp_path/'static/public/.learning-scenarios')
    return ls.ScenarioStore(auth())


def test_lifecycle_default_duplicate_remove_and_isolation(store):
    first=store.create('Attention', 'Learning goals')
    store.default(first['id'])
    assert store.selection('default') == first['id']
    twin=store.create('Copy',store.get(first['id'])['content'])
    store.update(twin['id'],1,content='Independent')
    assert store.get(first['id'])['content']=='Learning goals'
    for foreign in [ls.ScenarioStore(auth(2)), ls.ScenarioStore(auth(1,2))]:
        assert foreign.list()['scenarios']==[]
        for operation in [lambda:foreign.get(first['id']),lambda:foreign.default(first['id']),lambda:foreign.update(first['id'],1,content='bad')]:
            with pytest.raises(HTTPException) as err: operation()
            assert err.value.status_code==404
    store.update(first['id'],1,archived=True)
    assert store.list()['default_id'] is None
    assert store.selection('default') is None
    assert len(store.list()['scenarios'])==1
    assert ls.ScenarioStore(auth()).get(twin['id'])['content']=='Independent'


def test_concurrent_edit_exactly_one_wins(store):
    item=store.create('Draft')
    def update(content):
        try: return store.update(item['id'],1,content=content)['revision']
        except HTTPException as exc: return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(update,['first','second']))==[2,409]
    assert store.get(item['id'])['revision']==2


def test_validation_and_symlink_denial(store, tmp_path):
    for title,content in [('', ''),('x'*201,''),('Valid','x'*20001),('Valid',None)]:
        with pytest.raises(HTTPException): store.create(title,content)
    for key in ['../scenarios.json','/etc/passwd','garbage']:
        with pytest.raises(HTTPException): store.get(key)
    store.create('safe')
    folder=ls.ROOT/'1'/'1'
    (folder/'scenarios.json').unlink()
    (folder/'scenarios.json').symlink_to(tmp_path/'outside')
    with pytest.raises(HTTPException): store.list()


def test_context_once_per_revision_pending_and_removal(store):
    item=store.create('Calculus','limits')
    agent=SimpleNamespace(skill_state={'learning_scenario_id':item['id']}, pending_action=None, conversation=[{'role':'user','content':'existing'}])
    ls.apply_scenario(agent,auth())
    first=copy.deepcopy(agent.conversation)
    ls.apply_scenario(agent,auth())
    assert agent.conversation==first
    store.update(item['id'],1,content='derivatives')
    agent.pending_action={'command':'original'}
    ls.apply_scenario(agent,auth())
    assert agent.conversation==first
    agent.pending_action=None
    ls.apply_scenario(agent,auth())
    assert agent.conversation[:len(first)]==first
    assert 'derivatives' in agent.conversation[-2]['content']
    store.update(item['id'],2,archived=True)
    ls.apply_scenario(agent,auth())
    assert 'no longer active' in agent.conversation[-2]['content']
    from lamb.aac.session_guidance import browser_session
    visible=browser_session({'conversation':agent.conversation,'skill_info':agent.skill_state})
    assert not any('[Application learning scenario context]' in m['content'] for m in visible['conversation'])


def test_api_crud_and_direct_static_denied(store):
    ls.ROOT.mkdir(parents=True, exist_ok=True)
    app=FastAPI();app.include_router(router,prefix='/aac')
    app.dependency_overrides[get_auth_context]=lambda:auth()
    app.mount('/static',DocumentAwareStaticFiles(directory=ls.ROOT.parents[1]))
    with TestClient(app) as client:
        item=client.post('/aac/learning-scenarios',json={'title':'API','content':'private'}).json()
        key=item['id'];base='/aac/learning-scenarios/'+key
        assert client.put(base,json={'revision':1,'content':'changed'}).status_code==200
        assert client.put(base,json={'revision':1,'title':'stale'}).status_code==409
        twin=client.post(base+'/duplicate',json={'title':'API copy'}).json()
        assert twin['content']=='changed' and twin['id']!=key
        assert client.put('/aac/learning-scenarios/default',json={'scenario_id':key}).json()['default_id']==key
        for path in ['public/.learning-scenarios/1/1/scenarios.json','Public/.LEARNING-SCENARIOS/1/1/scenarios.json']:
            assert client.get('/static/'+path).status_code==404
        app.dependency_overrides[get_auth_context]=lambda:auth(2)
        assert client.get(base).status_code==404
        assert client.post(base+'/duplicate',json={'title':'stolen'}).status_code==404
        app.dependency_overrides[get_auth_context]=lambda:auth()
        assert client.delete(base+'?revision=2').status_code==200
        assert client.get(base).status_code==404


def test_command_contract_and_approval():
    from lamb.aac.liteshell.shell import prepare_command
    from lamb.aac.authorization import ActionAuthorizer
    for verb in ['create Draft --content text','update ID --revision 1 --content text','remove ID --revision 1','duplicate ID --title Copy','default none','select SESSION none']:
        key,*_=prepare_command('lamb learning-scenario '+verb)
        assert ActionAuthorizer().check(key)=='ask'
    for verb in ['list','get ID','selected SESSION']:
        key,*_=prepare_command('lamb learning-scenario '+verb)
        assert ActionAuthorizer().check(key)=='auto'
    for verb in ['update ID --content text','remove ID','duplicate ID','update ID --revision 1']:
        with pytest.raises(ValueError): prepare_command('lamb learning-scenario '+verb)


def test_session_selection_preserves_history_and_blocks_pending(store):
    from lamb.aac.scenario_router import select, selected, Selection
    from contextlib import nullcontext
    from unittest.mock import Mock
    item=store.create('Selected')
    session={'organization_id':1,'conversation':[{'role':'user','content':'History'}], 'skill_info':{},'pending_action':None,'tool_audit':[{'success':True}]}
    manager=Mock();manager.get_session.return_value=session
    def save(*args,**kwargs):session['skill_info']=kwargs['skill_info']
    manager.update_conversation.side_effect=save
    with patch('lamb.aac.session_manager.AACSessionManager',return_value=manager),patch('lamb.aac.turn_lock.TurnLock',return_value=nullcontext()):
        assert select('session',Selection(scenario_id=item['id']),auth())['scenario']['id']==item['id']
        assert manager.update_conversation.call_args.args[2]==session['conversation']
        store.default(item['id']);store.default(None)
        assert selected('session',auth())['scenario_id']==item['id']
        session['pending_action']={'command':'saved'}
        with pytest.raises(HTTPException) as exc:select('session',Selection(),auth())
        assert exc.value.status_code==409
        session['organization_id']=2
        with pytest.raises(HTTPException) as exc:selected('session',auth())
        assert exc.value.status_code==404


@pytest.mark.anyio
async def test_navigation_checks_owner_before_emitting():
    from unittest.mock import AsyncMock
    from lamb.aac.liteshell.commands import frontend_open
    from lamb.aac.frontend import destination
    key='00000000-0000-0000-0000-000000000001'
    assert destination(['learning-scenario',key],{'tab':'edit'})['tab']=='edit'
    ctx=SimpleNamespace(http=SimpleNamespace(get=AsyncMock(side_effect=ValueError('404'))),frontend=AsyncMock())
    with pytest.raises(ValueError):await frontend_open(ctx,['learning-scenario',key],{})
    ctx.frontend.assert_not_awaited()
