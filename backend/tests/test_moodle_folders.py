import asyncio
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, unquote
import pytest
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from tests.test_moodle_scoped_reads import responses
from lamb.aac.liteshell.shell import LiteShell, prepare_command
from lamb.moodle.folders import MAX_BATCH_BYTES, clean_path
from lamb.moodle.imports import store_for_runtime


@pytest.fixture
def folder(stores, tmp_path):
    with respx.mock:
        rt = runtime(stores); rt.cache_root = tmp_path
        _, read = responses()
        state = {'files': {'/same.md': b'ROOT_EVIDENCE', '/unit/same.md': b'NESTED_EVIDENCE',
                           '/unit/deep/lesson.html': b'<h1>DEEP_EVIDENCE</h1><img src="no">', '/unit/audio.mp3': b'audio'},
                 'hidden': False}
        def respond(request):
            fn = parse_qs(request.content.decode())['wsfunction'][0]
            if fn == 'core_course_get_contents':
                return Response(200, json=[{'id': 1, 'name': 'Section', 'modules': [{
                    'id': 22, 'instance': 32, 'contextid': 202, 'name': 'Readings', 'modname': 'folder',
                    'uservisible': not state['hidden'], 'contents': [
                        {'type': 'file', 'filename': path.rsplit('/', 1)[1], 'filepath': path.rsplit('/', 1)[0] + '/',
                         'fileurl': 'https://moodle.test/pluginfile.php/202/mod_folder/content/1' + path + '?forcedownload=1',
                         'filesize': len(content), 'timemodified': 1} for path, content in state['files'].items()]}]}])
            return read(request)
        respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
        download = respx.post(re.compile(r'https://moodle.test/webservice/pluginfile.php/202/mod_folder/content/1/.*')).mock(
            side_effect=lambda r: Response(200, content=state['files'][unquote(r.url.path.split('/content/1')[1])]))
        yield rt, state, download


def listed(rt):
    return rt.execute('folder.list', {'course_id': 10})[0]['source_ref']


def reviewed(rt, ref, suffix=''):
    command = f'moodle import folder {ref} {suffix} --to kb 12'
    key, _, params, _ = prepare_command(command)
    return command, rt.prepare_import(key.removeprefix('moodle.'), params)


@respx.mock
def test_recursive_inventory_paths_exclusions_and_no_body_download(folder):
    rt, state, download = folder
    ref = listed(rt)
    inv = rt.execute('folder.inspect', {'source_ref': ref, 'path': '/', 'exclude': ()})
    assert inv['file_count'] == 3 and inv['ready']
    assert [f['path'] for f in inv['files']] == ['/same.md', '/unit/deep/lesson.html', '/unit/same.md']
    assert inv['skipped'][0]['reason'] == 'unsupported_format'
    assert not download.called and 'NESTED_EVIDENCE' not in json.dumps(inv) + json.dumps(rt.context)
    subset = rt.execute('folder.inspect', {'source_ref': ref, 'path': '/unit/', 'exclude': ('/unit/deep/',)})
    assert [f['path'] for f in subset['files']] == ['/unit/same.md']
    with pytest.raises(ValueError, match='not present'):
        rt.execute('folder.inspect', {'source_ref': ref, 'path': '/', 'exclude': ('/does-not-exist/',)})


@respx.mock
def test_one_review_imports_all_files_with_distinct_names_and_idempotent_finish(folder):
    rt, _, _ = folder
    command, review = reviewed(rt, listed(rt))
    assert review['file_count'] == 3 and 'ROOT_EVIDENCE' not in json.dumps(review)
    from lamb.moodle.import_review import render_review
    assert 'Archivos para importar: 3' in render_review(review, 'es')
    uploads = []
    async def upload(path, **kwargs):
        uploads.append(kwargs)
        return {'status': 'success', 'file_registry_id': len(uploads)}
    http = SimpleNamespace(post=AsyncMock(side_effect=upload), get=AsyncMock(return_value={'status': 'completed'}))
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt); shell._http_client = http
    async def run():
        assert not (await shell.execute(command)).success
        http.post.assert_not_awaited()
        imported = await shell.execute(command, confirmed=True, review=review)
        assert imported.success, imported.error
        assert imported.data['counts'] == {'completed': 3}
        assert all(f['result']['status'] == 'completed' and 'document_count' not in f['result']
                   for f in imported.data['files'])
        assert len(uploads) == 3
        assert len({u['files']['file'][0] for u in uploads}) == 3
        assert {json.loads(u['data']['moodle_provenance'])['source_path'] for u in uploads} == {
            '/same.md', '/unit/same.md', '/unit/deep/lesson.html'}
        status = await shell.execute('moodle folder status ' + imported.data['batch_id'])
        assert status.data['status'] == 'completed' and len(uploads) == 3
        result = await shell.execute('moodle folder finish ' + imported.data['batch_id'])
        assert result.success, result.error
        assert len(uploads) == 3
        repeated = await shell.execute(command, confirmed=True, review=review)
        assert repeated.data['batch_id'] == imported.data['batch_id'] and len(uploads) == 3
    asyncio.run(run())


@pytest.mark.parametrize('change', ['bytes', 'add', 'remove', 'hidden', 'session', 'course'])
@respx.mock
def test_changed_or_foreign_folder_review_never_starts_delivery(folder, change):
    rt, state, _ = folder
    command, review = reviewed(rt, listed(rt))
    if change == 'bytes': state['files']['/same.md'] = b'OTHER_EVIDENCE'
    if change == 'add': state['files']['/added.md'] = b'New'
    if change == 'remove': del state['files']['/same.md']
    if change == 'hidden': state['hidden'] = True
    if change == 'session': rt.context['document_scope'] = 'different-session'
    if change == 'course': rt.context['course_id'] = 99
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt)
    shell._http_client = SimpleNamespace(post=AsyncMock())
    result = asyncio.run(shell.execute(command, confirmed=True, review=review))
    assert not result.success
    shell._http_client.post.assert_not_awaited()


@respx.mock
def test_partial_batch_persists_unknown_outcome_and_does_not_reupload(folder):
    rt, _, _ = folder
    command, review = reviewed(rt, listed(rt))
    count = 0
    async def upload(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2: raise OSError('Connection lost after upload')
        return {'status': 'success', 'file_registry_id': count}
    http = SimpleNamespace(post=AsyncMock(side_effect=upload), get=AsyncMock(return_value={'status': 'completed'}))
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt); shell._http_client = http
    async def run():
        result = await shell.execute(command, confirmed=True, review=review)
        assert result.success, result.error
        assert result.data['status'] == 'partial'
        assert result.data['counts'] == {'completed': 2, 'outcome_unknown': 1}
        # Recreate runtime from the persisted document context, as after a restart.
        from lamb.moodle.runtime import MoodleRuntime
        restored = MoodleRuntime(rt.store, cipher=rt._cipher); restored.cache_root = rt.cache_root
        restored.context = json.loads(json.dumps(rt.context))
        shell.moodle = restored
        status = await shell.execute('moodle folder status ' + result.data['batch_id'])
        assert status.success, status.error
        before = count
        retry = await shell.execute(result.data['next_command'], confirmed=True)
        assert retry.success, retry.error
        assert count == before and retry.data['status'] == 'partial'
    asyncio.run(run())


@respx.mock
def test_folder_bounds_precede_download(folder):
    rt, state, download = folder
    state['files'] = {f'/{i}.md': b'X' for i in range(21)}
    ref = listed(rt)
    with pytest.raises(ValueError, match='1-20'): reviewed(rt, ref)
    assert not download.called
    state['files'] = {f'/{i}.md': b'X' for i in range(101)}
    with pytest.raises(ValueError, match='100'): reviewed(rt, ref)
    assert not download.called


@pytest.mark.parametrize('path', ['../x', '/a/../b', '/a\\b', '/a\nb'])
def test_folder_path_validation(path):
    with pytest.raises(ValueError): clean_path(path)


def test_folder_contract_rejects_single_file_and_requires_destination():
    for command in ('moodle import folder ref --single-file', 'moodle import folder ref', 'moodle import folder ref --to kb 0'):
        with pytest.raises(ValueError): prepare_command(command)


@respx.mock
def test_folder_download_preserves_encoded_names_and_strips_only_presentation_hint():
    from lamb.moodle.documents import download_file
    endpoint = 'https://moodle.test/webservice/pluginfile.php/202/mod_folder/content/1/Unit%201/notes%23one.md'
    route = respx.post(endpoint).mock(return_value=Response(200, content=b'Text'))
    item = {'filename':'notes#one.md','url':endpoint+'?forcedownload=1'}
    assert download_file('https://moodle.test','secret',item,single_file=False).content == b'Text'
    assert not route.calls.last.request.url.query
    assert parse_qs(route.calls.last.request.content.decode()) == {'token':['secret']}
    for query in ('token=secret', 'forcedownload=1&token=secret', 'forcedownload=2', 'forcedownload=1&forcedownload=0'):
        with pytest.raises(PermissionError):
            download_file('https://moodle.test','secret',dict(item,url=endpoint+'?'+query),single_file=False)


@pytest.mark.parametrize('completed', [True, False])
def test_aac_does_not_request_another_approval_for_a_completed_batch(completed):
    from tests.test_aac_legacy import agent, tool
    from lamb.aac.liteshell.shell import ShellResult
    a, _, shell = agent([])
    shell.execute.return_value = ShellResult(True, data={'batch_id':'batch', 'status':'completed' if completed else 'partial'})
    result = asyncio.run(a._execute_tool(tool('moodle folder finish batch')))
    shell.execute.assert_awaited_once_with('moodle folder status batch')
    assert bool(a.pending_action) is not completed
    if completed: assert result['action_executed'] is False and result['data']['status'] == 'completed'
