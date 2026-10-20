"""Failures reported in Claude-Dick's 20 September review, through real parsers."""
import asyncio
import io
import json
import uuid
import zipfile
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from openai import APIError, BadRequestError
from lamb.aac.liteshell.shell import LiteShell, prepare_command
from lamb.moodle.imports import PreparedImport, load_receipt, store_for_runtime
from lamb.moodle.import_delivery import deliver
from lamb.moodle.documents import Download, validate_archive
from lamb.moodle.runs import RunStore
from tests.test_moodle_resume import LargeFixture, execute, finish
from tests.test_moodle_tasks import Fixture, store
from tests.test_moodle_import import source, review
from tests.test_moodle_store import stores


def test_reply_between_steps_does_not_abandon_remaining_discussions(tmp_path):
    raw = LargeFixture((120,)); original = raw.call; replies = 0
    def call(fn, **kw):
        value = original(fn, **kw)
        if fn == 'mod_forum_get_forum_discussions':
            for row in value['discussions']: row.update(numreplies=replies, timemodified=replies)
        return value
    raw.call = call
    first = execute(tmp_path, raw, max_calls=70)
    assert 0 < first['coverage']['posts_found'] < 120
    replies = 1
    final = finish(tmp_path, raw, first)[-1]
    assert final['coverage']['complete'] and final['coverage']['posts_found'] == 120


@pytest.mark.parametrize('target', ['core_enrol_get_users_courses', 'mod_forum_get_forums_by_courses', 'mod_forum_get_discussion_posts'])
def test_transient_read_failure_retains_cursor_and_retry_is_exact(tmp_path, target):
    raw = LargeFixture((30,)); original = raw.call; failed = False
    def call(fn, **kw):
        nonlocal failed
        if fn == target and not failed:
            failed = True
            raise httpx.ReadTimeout('PRIVATE remote error')
        return original(fn, **kw)
    raw.call = call
    # Discovery can fail before a traversal cursor exists. Its private recovery
    # handle still exists and must permit continuation on the next attempt.
    if target == 'core_enrol_get_users_courses':
        with pytest.raises(httpx.ReadTimeout): execute(tmp_path, raw)
        first = RunStore(store(tmp_path)).listing()['runs'][0]
    else:
        first = execute(tmp_path, raw)
        assert first['budget']['stopped_reason'] == 'temporary_moodle_error'
        assert first['continue_command']
    final = finish(tmp_path, raw, first)[-1]
    assert final['coverage']['complete'] and final['coverage']['posts_found'] == 30
    assert {p['id'] for p in store(tmp_path).read(final['result_id'])['posts']} == raw.expected


def test_recovery_handle_survives_results_churn_and_terminal_limit_is_truthful(tmp_path):
    first = execute(tmp_path, LargeFixture((30,)), max_calls=10)
    evidence = store(tmp_path)
    for _ in range(25): evidence.save({'synthetic': True})
    assert evidence.read(first['result_id'])
    assert len(list(evidence.folder.glob('*.json'))) == 16
    final = finish(tmp_path, LargeFixture((30,)), first)[-1]
    assert final['coverage']['complete']
    with patch('lamb.moodle.runs.MAX_RUN_CALLS', 5):
        stopped = execute(tmp_path, LargeFixture((30,)))
    assert not stopped['coverage']['traversal_finished'] and not stopped['continue_command']


def test_short_page_does_not_omit_later_visible_discussions(tmp_path):
    raw = Fixture(); raw.courses = [1]
    raw.pages[(10, 1)] = [{'id': 101, 'discussion': 101}]
    final = execute(tmp_path, raw)
    assert final['coverage']['complete'] and final['coverage']['posts_found'] == 2


@pytest.mark.parametrize('command', ['moodle assign list --course-id 10 --course-id 20', 'moodle calendar events --course-id 10 --course-id 20'])
def test_actual_repeatable_parser_binding_roundtrips_and_checks_every_course(tmp_path, command):
    from lamb.moodle.runtime import MoodleRuntime
    from lamb.aac.result_store import ResultStore
    key, _, params, _ = prepare_command(command)
    assert params['course_id'] == (10, 20)
    binding = {'generation': 1, 'base_url': 'https://moodle.test', 'moodle_user_id': 7}
    rt = N(result_binding=lambda: dict(binding), context={}, execute=lambda *a, **kw: {'body': 'x'*20000})
    shell = LiteShell('', 'fixture', 'fixture@test', 1, user_id=1, moodle=rt)
    result = asyncio.run(shell.execute(command))
    assert result.success, result.error
    saved = ResultStore(1,1,root=tmp_path)
    identity = saved.save(result.data, origin={'moodle': result.result_binding})['result_id']
    restored = saved.read(identity)['origin']['moodle']
    assert restored['course_ids'] == [10,20]
    runtime = MoodleRuntime(N(organization_id=1,owner_id=1),cipher=N(decrypt=lambda *a, **kw:'fixture'))
    runtime.result_binding=lambda: dict(binding); runtime.available=lambda:{key}
    runtime.snapshot=lambda:{'record':{'base_url':'https://moodle.test','moodle_user_id':7,'token_encrypted':'fixture'}}
    with patch('lamb.moodle.runtime.MoodleHTTPClient'), patch('lamb.moodle.runtime.MoodleScope') as scope:
        runtime.validate_result_binding(restored,key)
        assert [c.args[0] for c in scope.return_value.require_teacher.call_args_list] == [10,20]
        scope.return_value.require_teacher.side_effect=PermissionError('revoked')
        with pytest.raises(PermissionError): runtime.validate_result_binding(restored,key)


def replacement(tmp_path):
    from lamb.moodle.import_store import ImportStore
    storage = ImportStore(1,7,tmp_path)
    binding={'generation':1,'base_url':'https://moodle.test','moodle_user_id':7,'policy':{'allow_grade_write':False}}
    rt=N(result_binding=lambda:dict(binding),store=N(organization_id=1,owner_id=7),cache_root=tmp_path)
    old={'import_id':str(uuid.uuid4()), 'status':'completed','revision':1,'binding':binding,
         'destination':{'single_file':False,'kb_id':12},'source':{'kind':'page','course_id':10,'source_url':'https://moodle.test/mod/page/view.php?id=22'},
         'review':{'source_hash':'old'},'result':{'file_registry_id':43}}
    storage.put('receipts',old['import_id'],old)
    data={'binding':dict(binding),'destination':old['destination'],'source':old['source'],
          'review':{'source_hash':'new','converted_hash':'new'},'previous':{k:old[k] for k in ('import_id','revision','result','destination')}}
    approval=storage.review(data)
    return PreparedImport(Download('page.md',b'new','text/markdown'),data,storage),rt,old,binding


@pytest.mark.parametrize('failure', ['403','connect','job'])
def test_failed_refresh_restores_completed_revision_and_never_retries_approval(tmp_path,failure):
    from lamb.aac.liteshell.http_client import APIResponseError
    prepared,rt,old,_=replacement(tmp_path)
    error={'403':APIResponseError(403,'denied'),'connect':httpx.ConnectError('offline')}.get(failure)
    http=N(post=AsyncMock(side_effect=error,return_value={'status':'processing','file_registry_id':44}),get=AsyncMock(return_value={'status':'failed'}),delete=AsyncMock())
    result=asyncio.run(deliver(prepared,http,rt,7))
    assert result['status']=='failed' and result['previous_revision_retained']==1
    assert load_receipt(rt,old['import_id'])==old
    again=asyncio.run(deliver(prepared,http,rt,7))
    assert again==result and http.post.await_count==1
    http.delete.assert_not_awaited()


def test_uncertain_timeout_stays_unknown_without_duplicate_upload(tmp_path):
    prepared,rt,old,_=replacement(tmp_path)
    http=N(post=AsyncMock(side_effect=httpx.ReadTimeout('unknown outcome')),delete=AsyncMock())
    with pytest.raises(httpx.ReadTimeout):asyncio.run(deliver(prepared,http,rt,7))
    assert load_receipt(rt,old['import_id'])['status']=='outcome_unknown'
    again=asyncio.run(deliver(prepared,http,rt,7))
    assert again['status']=='outcome_unknown' and http.post.await_count==1
    http.delete.assert_not_awaited()


def test_durable_receipts_survive_rotation_but_approvals_do_not(tmp_path):
    prepared,rt,old,binding=replacement(tmp_path)
    binding['generation']=2;binding['policy']={'allow_grade_write':True}
    assert load_receipt(rt,old['import_id'])['revision']==1
    http=N(post=AsyncMock())
    with pytest.raises(PermissionError):asyncio.run(deliver(prepared,http,rt,7))
    http.post.assert_not_awaited()
    binding['moodle_user_id']=99
    with pytest.raises(PermissionError):load_receipt(rt,old['import_id'])


@respx.mock
def test_metadata_listing_downloads_only_selected_page_and_rejects_kind_confusion(source):
    rt,state,_=source
    state['content']=b'x'*(11*1024*1024)
    rows=rt.execute('page.list',{'course_id':10})
    assert rows and len(respx.calls)>0
    assert all('pluginfile.php' not in str(c.request.url) for c in respx.calls)
    assert all(b'mod_page_get_pages_by_courses' not in c.request.content for c in respx.calls)
    with pytest.raises(ValueError,match='10 MiB'):
        review(rt,f"moodle import page {rows[0]['source_ref']} --single-file")
    with pytest.raises(PermissionError,match='different document type'):
        review(rt,f"moodle import book {rows[0]['source_ref']} --single-file")


def test_optional_provenance_is_dependency_free_and_private_root_failure_is_harmless(monkeypatch):
    import builtins, sys
    from lamb import document_provenance
    original=builtins.__import__
    def denied(name,*args,**kw):
        if name.startswith(('moodle_cli','lamb.moodle')):raise AssertionError('student path imported connector')
        return original(name,*args,**kw)
    monkeypatch.setattr(builtins,'__import__',denied)
    monkeypatch.setattr(document_provenance,'private_root',lambda: (_ for _ in ()).throw(ValueError('bad path')))
    assert document_provenance.single_provenance('7/owned.txt','still grounded')=={}


def test_disguised_archive_and_html_losses_are_visible():
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('big',b'x'*(51*1024*1024))
    for suffix in ('.pdf','.csv','.docx'):
        with pytest.raises(ValueError,match='Expanded'):validate_archive(data.getvalue(),suffix)
    from lamb.moodle.html_document import convert_html
    text,loss=convert_html('<p>mc<sup>2</sup> ![x](https://outside.test)</p><ol start="5"><li>Number</li></ol><a href="/tokenpluginfile.php/SECRET/file">Private</a>','https://moodle.test')
    assert 'SECRET' not in text and r'\!\[x\]' in text and '^(2)' in text
    assert loss['formatting']>=2 and loss['authenticated_links']==1


def test_replacement_does_not_delete_reused_file_id(tmp_path):
    prepared,rt,old,_=replacement(tmp_path)
    http=N(post=AsyncMock(return_value={'status':'processing','file_registry_id':44}),
           get=AsyncMock(side_effect=[{'status':'completed'}, {'status':'completed','plugin_params':{'moodle_provenance':{'import_id':'someone-else','source_hash':'other'}}}]),
           delete=AsyncMock())
    result=asyncio.run(deliver(prepared,http,rt,7))
    assert result['status']=='replacement_ready' and 'identity could not be verified' in result['note']
    http.delete.assert_not_awaited()


@pytest.mark.parametrize('failure', ['offline','proxy'])
def test_only_creator_pre_ingestion_offline_refusal_is_definite(tmp_path,failure):
    from lamb.aac.liteshell.http_client import APIResponseError
    prepared,rt,old,_=replacement(tmp_path)
    error=APIResponseError(503,'KB server is not available' if failure=='offline' else 'proxy error')
    http=N(post=AsyncMock(side_effect=error))
    if failure=='offline':
        result=asyncio.run(deliver(prepared,http,rt,7))
        assert result['status']=='failed' and load_receipt(rt,old['import_id'])['status']=='completed'
    else:
        with pytest.raises(APIResponseError):asyncio.run(deliver(prepared,http,rt,7))
        assert load_receipt(rt,old['import_id'])['status']=='outcome_unknown'


@respx.mock
@pytest.mark.parametrize('kind',['page','book'])
def test_student_role_in_enrolled_course_cannot_import_class_content(source,kind):
    rt,_,_=source
    from lamb.moodle.scope import CourseIdentityService
    with patch.object(CourseIdentityService,'own_course_profile',return_value={'id':7,'roles':[{'shortname':'student'}]}):
        with pytest.raises(PermissionError,match='instructor'):
            rt.execute(kind+'.list',{'course_id':10})
