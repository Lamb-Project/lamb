import asyncio
import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs
import pytest
import respx
from httpx import Response
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores
from tests.test_moodle_scoped_reads import responses
from lamb.aac.liteshell.shell import LiteShell, prepare_command
from lamb.moodle.documents import download_file, validate_archive
from lamb.moodle.html_document import convert_html
from lamb.moodle.imports import store_for_runtime


def test_import_destinations_and_confirmation_policy():
    from lamb.aac.authorization import ActionAuthorizer
    for kind in ('file', 'page', 'book'):
        for suffix, expected in [('--single-file', None), ('--to kb 12', 12)]:
            key, _, p, _ = prepare_command('moodle import ' + kind + ' ref ' + suffix)
            assert p['kb_id'] == expected
            assert ActionAuthorizer().check(key) == 'ask'
        for suffix in ('', '--to kb', '--to kb 1 --single-file', '--single-file 12'):
            with pytest.raises(ValueError): prepare_command('moodle import ' + kind + ' ref ' + suffix)


@pytest.fixture
def source(stores, tmp_path):
    rt = runtime(stores); rt.cache_root = tmp_path
    _, read = responses()
    state = {'content': b'Evidence', 'mtime': 1, 'present': True}
    def respond(request):
        p = parse_qs(request.content.decode()); fn = p['wsfunction'][0]
        if fn == 'core_course_get_contents':
            return Response(200, json=[{'id': 1, 'name': 'Section', 'modules': [
                {'id': 21, 'instance': 31, 'modname': 'resource', 'contextid': 201},
                {'id': 22, 'instance': 32, 'modname': 'page', 'contextid': 202}]}])
        if fn == 'core_files_get_files':
            return Response(200, json={'files': [{'filename': 'lesson.txt',
                'url': 'https://moodle.test/pluginfile.php/201/mod_resource/content/0/lesson.txt',
                'filesize': len(state['content']), 'timemodified': state['mtime'], 'isdir': False}] if state['present'] else []})
        if fn == 'mod_page_get_pages_by_courses':
            return Response(200, json={'pages': [{'id': 32, 'course': 10, 'name': 'Guide',
                'timemodified': state['mtime'], 'content': state['content'].decode()}]})
        return read(request)
    respx.post('https://moodle.test/webservice/rest/server.php').mock(side_effect=respond)
    fetched = respx.post('https://moodle.test/webservice/pluginfile.php/201/mod_resource/content/0/lesson.txt').mock(
        side_effect=lambda request: Response(200, content=state['content'], headers={'content-type': 'text/plain'}))
    return rt, state, fetched


def review(rt, command):
    key, _, params, _ = prepare_command(command)
    return rt.prepare_import(key.removeprefix('moodle.'), params)


@respx.mock
def test_import_review_scope_revalidation_upload_and_no_duplicate(source, monkeypatch, tmp_path):
    rt, state, fetched = source
    monkeypatch.setattr('lamb.moodle.import_delivery.private_root', lambda: tmp_path)
    http = SimpleNamespace(post=AsyncMock(return_value={'path': '7/owned.txt'}))
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt); shell._http_client = http
    async def run():
        await shell.execute('moodle course get 10')
        listed = await shell.execute('moodle file list 201 --component mod_resource --filearea content')
        assert listed.success, listed.error
        command = f"moodle import file {listed.data[0]['file_id']} --single-file"
        assert not (await shell.execute(command, confirmed=True)).success
        approval = review(rt, command)
        assert approval['characters'] == 8 and approval['estimated_tokens'] > 0
        rt.context['document_scope'] += '-other'
        assert not (await shell.execute(command, confirmed=True, review=approval)).success
        rt.context['document_scope'] = rt.context['document_scope'].removesuffix('-other')
        result = await shell.execute(command, confirmed=True, review=approval)
        assert result.success, result.error
        assert result.data['result']['path'] == '7/owned.txt'
        http.post.assert_awaited_once_with('/creator/aac/files', files={'file': ('lesson.txt', b'Evidence', 'text/plain')})
        repeated = await shell.execute(command, confirmed=True, review=approval)
        assert repeated.success and repeated.data['import_id'] == result.data['import_id']
        assert http.post.await_count == 1
        state['content'] = b'Changed!'
        rejected = await shell.execute(command, confirmed=True, review=approval)
        assert not rejected.success and 'changed' in rejected.error
    asyncio.run(run())
    assert fetched.calls and all(not call.request.url.query for call in fetched.calls)
    assert parse_qs(fetched.calls[0].request.content.decode())['token'] == ['fixture']


@respx.mock
def test_page_bodies_never_returned_and_large_review(source):
    rt, state, _ = source
    state['content'] = b'<h1>Untrusted</h1><p>INJECTION_DO_NOT_EXPOSE</p>'
    rows = rt.execute('page.list', {'course_id': 10})
    assert 'INJECTION_DO_NOT_EXPOSE' not in json.dumps(rows)
    assert 'INJECTION_DO_NOT_EXPOSE' not in json.dumps(rt.context)
    command = f"moodle import page {rows[0]['source_ref']} --single-file"
    approval = review(rt, command)
    assert 'INJECTION_DO_NOT_EXPOSE' not in json.dumps(approval)
    state['content'] = b'<p>' + b'large ' * 20000 + b'</p>'
    assert 'Large reference' in review(rt, command)['size_warning']
    # The legacy activity listing is metadata-only too.
    rows = rt.execute('content.list', {'course_id': 10, 'module_type': 'page'})
    assert 'large large' not in json.dumps(rows)


@respx.mock
def test_changed_source_and_foreign_session_fail_before_delivery(source):
    rt, state, _ = source
    rows = rt.execute('page.list', {'course_id': 10})
    command = f"moodle import page {rows[0]['source_ref']} --to kb 12"
    approval = review(rt, command)
    state['content'] = b'changed with same timestamp'
    key, _, params, _ = prepare_command(command)
    with pytest.raises(PermissionError, match='changed'):
        rt.execute('import.page', params, confirmed=True, review=approval)
    rt.context = {'generation': rt.snapshot()['generation'], 'course_id': 10}
    with pytest.raises(PermissionError): review(rt, command)
    with pytest.raises(PermissionError): rt.execute('page.list', {'course_id': 999})


@respx.mock
def test_download_rejects_urls_redirects_oversize_and_unsupported_formats():
    item = {'filename': 'lesson.txt', 'url': 'https://other.test/pluginfile.php/1/file', 'filesize': 1}
    with pytest.raises(PermissionError): download_file('https://moodle.test', 'secret-token', item, single_file=True)
    assert not respx.calls
    item['url'] = 'https://moodle.test/pluginfile.php/1/file'
    route = respx.post('https://moodle.test/webservice/pluginfile.php/1/file').mock(return_value=Response(302, headers={'location': 'https://other.test'}))
    with pytest.raises(ValueError) as exc: download_file('https://moodle.test', 'secret-token', item, single_file=True)
    assert 'secret-token' not in str(exc.value)
    for ext in ('zip', 'xml', 'wav', 'mp3'):
        item['filename'] = 'lesson.' + ext
        with pytest.raises(ValueError): download_file('https://moodle.test', 'secret-token', item, single_file=False)
    item.update(filename='lesson.txt', filesize=11 * 1024 * 1024)
    with pytest.raises(ValueError): download_file('https://moodle.test', 'secret-token', item, single_file=True)
    assert len(route.calls) == 1


def test_archive_expansion_is_bounded():
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('huge.xml', b' ' * (51 * 1024 * 1024))
    with pytest.raises(ValueError, match='Expanded'): validate_archive(archive.getvalue(), '.docx')


def test_html_conversion_and_losses():
    html = '<h1>Title</h1><ul><li>One</li><li>Two</li></ul><a href="/guide?id=2&token=SECRET">Guide</a><table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table><img src="https://evil.test"><script>BAD</script><iframe>BAD</iframe><table><tr><td colspan="2">Wide</td></tr></table>'
    text, losses = convert_html(html, 'https://moodle.test/mod/page/view.php?id=1')
    assert '# Title' in text and '- One' in text and '- Two' in text
    assert '[Guide](https://moodle.test/guide?id=2)' in text
    assert '| A | B |\n| --- | --- |\n| 1 | 2 |' in text
    assert 'SECRET' not in text and 'BAD' not in text and 'evil.test' not in text
    assert losses == {'images': 1, 'media': 1, 'complex_tables': 1, 'active_content': 1}


def test_book_hidden_chapters_are_not_downloaded():
    from lamb.moodle.document_sources import book_chapters
    module = {'contents': [{'type': 'content', 'filename': 'structure', 'content': json.dumps([
        {'title': 'First', 'href': '1/index.html', 'hidden': 0},
        {'title': 'Hidden', 'href': '2/index.html', 'hidden': 1, 'subitems': [{'title': 'Child', 'href': '3/index.html'}]},
        {'title': 'Last', 'href': '4/index.html', 'hidden': 0}])},
        *[{'filename': 'index.html', 'filepath': f'/{n}/', 'fileurl': f'https://moodle.test/pluginfile.php/{n}'} for n in (1, 4)]]}
    chapters, hidden = book_chapters(module)
    assert [x['chapter_id'] for x in chapters] == [1, 4] and hidden == 2


def test_replacement_waits_for_new_job_and_retries_do_not_upload(tmp_path):
    from lamb.moodle.import_delivery import finish
    from lamb.moodle.import_store import ImportStore
    store = ImportStore(1, 7, tmp_path)
    import uuid
    key = str(uuid.uuid4())
    receipt = {'import_id': key, 'status': 'processing', 'binding': {'generation': 1},
               'destination': {'kb_id': 12}, 'result': {'file_registry_id': 44}, 'replaced_file_id': 43}
    runtime = SimpleNamespace(result_binding=lambda: {'generation': 1})
    http = SimpleNamespace(get=AsyncMock(return_value={'status': 'failed'}), delete=AsyncMock(), post=AsyncMock())
    async def run():
        failed = await finish(receipt, store, http, runtime)
        assert failed['status'] == 'failed'
        http.delete.assert_not_awaited()
        receipt['status'] = 'processing'
        http.get.return_value = {'status': 'completed'}
        done = await finish(receipt, store, http, runtime)
        assert done['status'] == 'completed'
        http.delete.assert_awaited_once_with('/creator/knowledgebases/kb/12/files/43')
        await finish(receipt, store, http, runtime)
        assert http.delete.await_count == 1
        http.post.assert_not_awaited()
    asyncio.run(run())


@respx.mock
def test_document_http_sessions_are_owner_scoped_and_confirm_handles_are_required(source, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from lamb.moodle.router import router, store_for
    from lamb.auth_context import get_auth_context
    from lamb.moodle.runtime import MoodleRuntime
    rt, state, _ = source
    app = FastAPI(); app.include_router(router)
    auth = SimpleNamespace(user={'id': 7, 'email': 'fixture@test'}, organization={'id': 1})
    app.dependency_overrides[get_auth_context] = lambda: auth
    app.dependency_overrides[store_for] = lambda: rt.store
    monkeypatch.setattr('lamb.moodle.runtime.TokenCipher', lambda: rt._cipher)
    # Match the endpoint's default storage with this fixture runtime.
    monkeypatch.setattr('lamb.moodle.import_store.private_root', lambda: rt.cache_root)
    c = TestClient(app)
    first = c.post('/moodle/documents/sessions').json()['session']
    second = c.post('/moodle/documents/sessions').json()['session']
    listed = c.post('/moodle/documents/commands', json={'session': first, 'command': 'moodle page list 10'})
    assert listed.status_code == 200, listed.text
    ref = listed.json()[0]['source_ref']
    command = f'moodle import page {ref} --single-file'
    review_response = c.post('/moodle/documents/commands', json={'session': first, 'command': command})
    assert review_response.status_code == 200, review_response.text
    review_id = review_response.json()['review']['review_id']
    denied = c.post('/moodle/documents/commands', json={'session': second, 'command': command, 'confirm': review_id})
    assert denied.status_code == 400 and 'another session' in denied.text
    denied = c.post('/moodle/documents/commands', json={'session': '../foreign', 'command': 'moodle page list 10'})
    assert denied.status_code == 403
    denied = c.post('/moodle/documents/commands', json={'session': first, 'command': 'moodle forum post 1'})
    assert denied.status_code == 400
    app.dependency_overrides.clear()
    assert c.post('/moodle/documents/sessions').status_code in {401, 403}


def test_aac_approval_forwards_persisted_import_review():
    from tests.test_aac_legacy import agent, message
    from lamb.aac.liteshell.shell import ShellResult
    a, _, shell = agent([message('Imported')])
    review = {'review_id': 'opaque', 'characters': 42}
    command = 'moodle import page md_fixture --single-file'
    a.pending_action = {'action_key': 'moodle.import.page', 'command': command, 'moodle_review': review}
    shell.execute.return_value = ShellResult(True, data={'status': 'completed'})
    asyncio.run(a._resolve_pending_action('yes'))
    shell.execute.assert_awaited_once_with(command, confirmed=True, review=review)


def test_import_review_is_localized_and_does_not_dump_internal_hashes():
    from lamb.moodle.import_review import render_review
    review = {'source': {'title': 'Guide', 'source_url': 'https://moodle.test/mod/page/view.php?id=1', 'course_id': 1, 'module_id': 2},
              'destination': {'single_file': True}, 'characters': 200000, 'estimated_tokens': 70000,
              'reference_document_max_tokens': 24000, 'source_hash': 'INTERNAL_HASH', 'bytes': 200000}
    text = render_review(review, 'es')
    assert 'DOCUMENTO GRANDE' in text and '70000 tokens estimados' in text and 'Fuente: Guide' in text
    assert 'INTERNAL_HASH' not in text


def test_single_file_citation_is_hash_bound_and_optional(tmp_path, monkeypatch):
    from lamb.moodle.import_delivery import save_single_provenance, single_provenance
    from lamb.moodle.document_sources import digest
    monkeypatch.setattr('lamb.moodle.import_delivery.private_root', lambda: tmp_path)
    receipt = {'review': {'converted_hash': digest(b'Evidence')},
               'source': {'title': 'Guide', 'source_url': 'https://moodle.test/mod/page/view.php?id=2'}}
    save_single_provenance('7/owned.md', receipt)
    assert single_provenance('7/owned.md', 'Evidence')['title'] == 'Guide'
    assert single_provenance('8/owned.md', 'Evidence') == {}
    assert single_provenance('7/owned.md', 'Changed') == {}
    path = next((tmp_path/'import-citations').glob('*.json'))
    path.write_text('broken')
    assert single_provenance('7/owned.md', 'Evidence') == {}


@respx.mock
def test_cheap_page_check_avoids_body_endpoint(source):
    rt, state, _ = source
    rows = rt.execute('page.list', {'course_id': 10})
    command = f"moodle import page {rows[0]['source_ref']} --single-file"
    approval = review(rt, command)
    storage = store_for_runtime(rt)
    data = storage.get('reviews', approval['review_id'])
    import uuid
    identity = str(uuid.uuid4())
    data.update(import_id=identity, status='completed')
    storage.put('receipts', identity, data)
    respx.calls.clear()
    checked = rt.execute('import.check', {'import_id': identity, 'verify_content': False})
    assert checked['content_hash_checked'] is False
    # This minimal fixture lacks an exported timestamp: report unknown, not unchanged.
    assert checked['metadata_changed'] is None
    assert all(parse_qs(c.request.content.decode()).get('wsfunction') != ['mod_page_get_pages_by_courses'] for c in respx.calls)


@pytest.mark.parametrize('html', ['<img src="image.png">', '<script>Only code</script>', '<iframe>Only embed</iframe>'])
def test_media_only_document_cannot_masquerade_as_text(html):
    with pytest.raises(ValueError, match='no importable text'):
        convert_html(html, 'https://moodle.test')
