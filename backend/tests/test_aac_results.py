"""Bounded model views, faithful readback and owner/connection authority."""
import json
import os
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

import pytest
from lamb.aac import result_store as rs
from lamb.aac.liteshell.shell import LiteShell, ShellResult
from tests.test_aac_legacy import agent, message, tool, turn


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def store(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    monkeypatch.setenv('LAMB_DB_PATH', str(root))
    return rs.ResultStore(1, 1)


def saved(store, payload):
    meta = store.save(payload, origin={'command':'assistant.get', 'authority': {
        'version': 1, 'resources': [{'kind': 'assistant', 'id': 42}]}})
    return store.read(meta['result_id'])


def test_compaction_preserves_full_payload_and_controls(store):
    payload={'success':False,'error':'Provider refused request','code':'bad_request',
             'awaiting_user_confirmation':True,'action_executed':False,
             'data':{'id':42,'total':150,'body':'x'*100_000}}
    compact=rs.compact(payload,store=store,origin={'command':'assistant.get'})
    assert len(rs.encode(compact))<=rs.RESULT_BYTES
    for key in ('success','error','code','awaiting_user_confirmation','action_executed'):
        assert compact[key]==payload[key]
    assert compact['data']['id']==42 and compact['data']['total']==150
    assert store.read(compact['context_result']['result_id'])['payload']==payload
    assert rs.compact({'success':True},store=store,origin={})=={'success':True}


def test_cache_failure_does_not_repeat_or_hide_executed_write():
    payload={'success':True,'action_executed':True,'data':'x'*50_000}
    result=rs.compact(payload,store=None,origin={})
    assert result['success'] and result['action_executed']
    assert not result['context_result']['stored']
    assert 'repeat a write' in result['context_result']['notice']
    assert len(rs.encode(result))<=rs.RESULT_BYTES


def test_owner_org_expiry_integrity_and_paths(store, monkeypatch):
    envelope=saved(store, {'data':'private'})
    identity=envelope['id']
    for forbidden in (rs.ResultStore(1,2),rs.ResultStore(2,1)):
        with pytest.raises(PermissionError): forbidden.read(identity)
    for invalid in ('../secret','not-a-uuid'):
        with pytest.raises(PermissionError): store.read(invalid)
    path=store.folder/(identity+'.json')
    assert path.stat().st_mode & 0o777 == 0o600
    assert store.folder.stat().st_mode & 0o777 == 0o700
    with patch.object(rs.time,'time',return_value=envelope['expires_at']+1):
        with pytest.raises(PermissionError): store.read(identity)
    envelope['payload']['data']='tampered'
    path.write_text(json.dumps(envelope))
    with pytest.raises(PermissionError): store.read(identity)


def test_static_and_symlink_storage_denied(store, tmp_path):
    with pytest.raises(ValueError): rs.ResultStore(1,1,root=Path(rs.__file__).resolve().parents[2]/'static'/'results')
    link=tmp_path/'link';link.symlink_to(store.folder.parent)
    with pytest.raises(ValueError): rs.ResultStore(1,1,root=link)
    envelope=saved(store,{'data':'private'})
    path=store.folder/(envelope['id']+'.json')
    path.unlink();path.symlink_to(tmp_path/'secret')
    with pytest.raises(PermissionError): store.read(envelope['id'])


def test_quota_and_file_limit(store,monkeypatch):
    monkeypatch.setattr(rs,'MAX_RESULTS',2)
    first=saved(store,{'data':1})
    saved(store,{'data':2});third=saved(store,{'data':3})
    with pytest.raises(PermissionError): store.read(first['id'])
    assert len(list(store.folder.glob('*.json')))==2
    assert store.read(third['id'])==third
    monkeypatch.setattr(rs,'MAX_FILE_BYTES',300)
    with pytest.raises(ValueError): store.save({'data':'x'*1000},origin={})
    monkeypatch.setattr(rs,'MAX_FILE_BYTES',2000)
    monkeypatch.setattr(rs,'MAX_OWNER_BYTES',1400)
    saved(store,{'data':'x'*750})
    assert sum(p.stat().st_size for p in store.folder.glob('*.json'))<=1400


def test_unicode_string_readback_is_exact_and_each_page_bounded(store):
    original=('é🔎\\\"\n'*8000)+'END OF EVIDENCE'
    envelope=saved(store,{'data':{'odd/key~':original}})
    offset=0;text='';pages=0
    while True:
        page=rs.page(envelope,'/data/odd~1key~0',offset)
        assert len(rs.encode({'success':True,'data':page}))<=rs.RESULT_BYTES-512
        assert rs.compact({'success':True,'data':page},store=store,origin={})=={'success':True,'data':page}
        text+=page['text'];pages+=1
        if page['next_command'] is None:break
        offset=page['next_offset']
    assert text==original and pages>10
    for path in ('/data/odd~2key','data','/absent','/data/~'):
        with pytest.raises(ValueError):rs.page(envelope,path)
    for offset in (-1,True,10**7):
        with pytest.raises(ValueError):rs.page(envelope,'/data/odd~1key~0',offset)


def test_collection_pages_keep_indexes_counts_and_truthful_previews(store):
    rows=[{'id':i,'body':'y'*5000} for i in range(53)]
    envelope=saved(store,{'data':rows})
    seen=[];offset=0
    while True:
        page=rs.page(envelope,'/data',offset)
        assert page['total_items']==53
        assert len(rs.encode(page))<rs.RESULT_BYTES
        for item in page['items']:
            assert item['complete'] is False and item['read_command']
            seen.append(item['key'])
        if page['next_offset'] is None:break
        offset=page['next_offset']
    assert seen==list(range(53))
    assert rs.page(envelope,'/data/52/id')['value']==52
    assert rs.page(envelope,'/data',53)['items']==[]
    with pytest.raises(ValueError):rs.page(envelope,'/data/01')


@pytest.mark.anyio
@pytest.mark.parametrize('streaming',[False,True])
async def test_provider_bounded_transcript_full_and_reopen_prefix(store,streaming):
    a,provider,fake=agent([message(tools=[tool('lamb assistant get 42')]),message('done')])
    shell=LiteShell(server_url="",token="fixture",user_email="fixture@example.invalid",user_id=1,organization_id=1)
    fake.model_result=shell.model_result
    fake.execute.return_value=ShellResult(True,data={'id':42,'system_prompt':'x'*100_000})
    await turn(a,streaming)
    raw=next(m for m in a.conversation if m['role']=='tool')
    assert len(raw['content'])>100_000
    sent=next(m for m in provider.calls[-1]['messages'] if m['role']=='tool')
    assert len(sent['content'].encode())<=rs.RESULT_BYTES
    assert '_aac_model_content' not in sent
    assert sent['tool_call_id']==raw['tool_call_id']
    b,other,other_fake=agent([message('still done')])
    other_fake.model_result=shell.model_result
    b.conversation=json.loads(json.dumps(a.conversation))
    await turn(b,streaming)
    assert other.calls[0]['messages'][:len(provider.calls[-1]['messages'])]==provider.calls[-1]['messages']


@pytest.mark.anyio
async def test_confirmation_retains_exact_command_executes_once_and_bounds_reply(store):
    a,provider,fake=agent([message(tools=[tool('lamb assistant update 42 --description "reviewed text"')]),message('Approve?'),message('Saved')])
    shell=LiteShell(server_url="",token="fixture",user_email="fixture@example.invalid",user_id=1,organization_id=1);fake.model_result=shell.model_result
    fake.execute.return_value=ShellResult(True,data={'id':42,'system_prompt':'x'*100_000})
    await a.chat('Update it')
    assert a.pending_action['command']=='lamb assistant update 42 --description "reviewed text"'
    fake.execute.assert_not_awaited()
    await a.chat('yes')
    fake.execute.assert_awaited_once()
    assert not a.pending_action
    full=next(m for m in a.conversation if m.get('content','').startswith('[System: User approved.'))
    assert len(full['content'])>100_000
    sent=next(m for m in provider.calls[-1]['messages'] if m.get('content','').startswith('[System: User approved.'))
    assert len(sent['content'])<rs.RESULT_BYTES+100


def test_workflow_instructions_complete_or_rejected_before_activation(store):
    a,_,_=agent([]);a.skill_state={'context':{}}
    prompt=a.activate_skill('manage-learning-scenarios')
    result={'success':True,'skill_loaded':'manage-learning-scenarios','data':prompt}
    assert len(rs.encode(result))>rs.RESULT_BYTES
    assert rs.compact(result,store=store,origin={},trusted_workflow=True)==result
    a.skill_state={'context':{}}
    with patch('lamb.aac.skill_routing.load_skill',return_value={'metadata':{'id':'huge'},'prompt':'x'*40_000}):
        with pytest.raises(ValueError,match='not activated'):a.activate_skill('huge')
    assert 'active_snapshot' not in a.skill_state
    assert a.required_skill('result.read',['id'],{}) is None


def test_read_result_enforces_current_owner_and_role(store):
    from lamb.aac.result_reader import read_result
    identity=saved(store,{'data':'owned'})['id']
    auth=N(user={'id':1},organization={'id':1,'config':{}},is_system_admin=False,is_org_admin=False,
           can_access_assistant=lambda _: 'owner')
    with patch('lamb.aac.brief.role_axes',return_value={'layers':['creator']}):
        assert read_result(auth,identity,'/data')['text']=='owned'
        auth.user['id']=2
        with pytest.raises(PermissionError):read_result(auth,identity)
        auth.user['id']=1
        with patch('lamb.aac.pack_loader.allowed_commands',return_value=set()):
            with pytest.raises(PermissionError):read_result(auth,identity)


def test_moodle_readback_checks_revocation_course_and_post_read_change():
    from lamb.moodle.runtime import MoodleRuntime
    runtime=MoodleRuntime(N(organization_id=1,owner_id=1),cipher=N(decrypt=lambda *a,**k:'fixture'))
    binding={'generation':1};runtime.result_binding=lambda:binding
    runtime.available=lambda:{'moodle.forum.posts'}
    runtime.snapshot=lambda:{'record':{'base_url':'http://fixture','moodle_user_id':7,'token_encrypted':'fixture'}}
    with pytest.raises(PermissionError):runtime.validate_result_binding({'generation':2},'moodle.forum.posts')
    with patch('lamb.moodle.runtime.MoodleHTTPClient'),patch('lamb.moodle.runtime.MoodleScope') as scope:
        scope.return_value.require_teacher.side_effect=PermissionError('Revoked teacher role')
        with pytest.raises(PermissionError):runtime.validate_result_binding({**binding,'course_id':42},'moodle.forum.posts')
        scope.return_value.require_teacher.assert_called_once_with(42)
        scope.return_value.require_teacher.side_effect=lambda _:binding.update(generation=2)
        with pytest.raises(PermissionError):runtime.validate_result_binding({'generation':1,'course_id':42},'moodle.forum.posts')


@pytest.mark.anyio
async def test_oversized_pending_command_stays_exact_and_unexecuted(store):
    command='lamb assistant update 42 --description "'+'reviewed '*4000+'"'
    a,provider,fake=agent([message(tools=[tool(command)]),message('Approve?')])
    fake.model_result=LiteShell('', 'fixture', 'fixture@example.invalid', 1, user_id=1).model_result
    await a.chat('Propose the update')
    assert a.pending_action['command']==command
    fake.execute.assert_not_awaited()
    sent=json.loads(next(m for m in rs.provider_messages(a.conversation) if m['role']=='tool')['content'])
    assert sent['awaiting_user_confirmation'] and sent['action']=='assistant.update'
    assert 'approval' in sent['message'] and not sent['command_preview_complete']
    assert len(rs.encode(sent))<=rs.RESULT_BYTES
    assert store.read(sent['context_result']['result_id'])['payload']['command']==command


@pytest.mark.anyio
async def test_liteshell_readback_uses_authenticated_api_and_moodle_bindings(store):
    identity=saved(store,{'data':'private'})['id']
    shell=LiteShell('', 'fixture', 'fixture@example.invalid', 1, user_id=1)
    shell._http_client=N(get=AsyncMock(return_value={'text':'private'}))
    result=await shell.execute(f'lamb result read {identity} --path /data --offset 0')
    assert result.success
    shell._http_client.get.assert_awaited_once_with(f'/creator/aac/results/{identity}',params={'path':'/data','offset':0})
    runtime=N(result_binding=lambda:{'generation':1},context={'course_id':42},execute=lambda *a,**kw:{'body':'x'*20000})
    shell.moodle=runtime
    # Self catalogues must not accidentally bind an unrelated selected course.
    for key,expected in [('course.list',False),('forum.posts',True)]:
        with patch('lamb.aac.liteshell.shell.prepare_command',return_value=('moodle.'+key,[],{},False)):
            raw=await shell.execute('lamb moodle '+key)
            assert raw.success,raw.error
            assert ('course_id' in raw.result_binding)==expected
            projected=shell.model_result('lamb moodle '+key,raw.to_dict())
            envelope=store.read(projected['context_result']['result_id'])
            assert envelope['origin']['moodle']==raw.result_binding


@pytest.mark.anyio
async def test_result_endpoint_owner_denial_and_bad_pointer(store):
    from fastapi import HTTPException
    from lamb.aac.router import read_tool_result
    identity=saved(store,{'data':'private'})['id']
    auth=N(user={'id':1},organization={'id':1,'config':{}},is_system_admin=False,is_org_admin=False,
           can_access_assistant=lambda _: 'owner')
    with patch('lamb.aac.brief.role_axes',return_value={'layers':['creator']}):
        assert (await read_tool_result(identity,path='/data',offset=0,auth=auth))['text']=='private'
        with pytest.raises(HTTPException) as bad:
            await read_tool_result(identity,path='/absent',offset=0,auth=auth)
        assert bad.value.status_code==400
        auth.user['id']=2
        with pytest.raises(HTTPException) as denied:
            await read_tool_result(identity,path='/data',offset=0,auth=auth)
        assert denied.value.status_code==404
