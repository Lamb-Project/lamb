"""Workspace persistence, exact paging, revision conflicts and session/source isolation."""
import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lamb.auth_context import get_auth_context
from lamb.aac.workspace import Workspace, text_page
from lamb.aac import workspace_router as api
from lamb.moodle.documents import Download


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('LAMB_DB_PATH', str(tmp_path))
    sid = str(uuid4())
    auth = SimpleNamespace(user={'id': 4, 'email': 'teacher@example.test'}, organization={'id': 2})
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[get_auth_context] = lambda: auth
    session = {'id': sid, 'organization_id': 2}
    with patch.object(api, 'AACSessionManager') as manager:
        manager.return_value.get_session.side_effect = lambda identity, email: session if identity == sid and email == auth.user['email'] else None
        with TestClient(app) as client:
            yield client, sid, auth, Workspace(2, 4, sid), manager


def test_exact_unicode_paging():
    text = (' α\n📚 café\t' * 1900) + 'END'
    offset = 0; parts = []
    while True:
        page = text_page(text, offset); parts.append(page['text'])
        if page['next_offset'] is None: break
        offset = page['next_offset']
    assert ''.join(parts) == text
    assert text_page(text, find='END')['text'] == 'END'
    assert text_page(text, find='absent')['match_found'] is False
    with pytest.raises(ValueError): text_page(text, -1)


def test_notebook_resume_and_revision_conflict(setup):
    c, sid, auth, store, _ = setup
    url = f'/sessions/{sid}/notebook'
    first = c.post(url, json={'name': 'batch', 'content': 'one: 7/10', 'revision': 0})
    assert first.status_code == 200 and first.json()['revision'] == 1
    assert c.post(url, json={'name': 'batch', 'content': 'lost update', 'revision': 0}).status_code == 400
    assert Workspace(2, 4, sid).read()['notes']['batch']['content'] == 'one: 7/10'
    assert c.post(url, json={'name': 'batch', 'content': 'one: 7/10\ntwo: 8/10', 'revision': 1}).status_code == 200
    result = c.get(url + '/read', params={'name': 'batch'}).json()
    assert result['revision'] == 2 and result['text'].endswith('two: 8/10')
    assert result['kind'] == 'working_draft' and result['is_source_evidence'] is False


def test_workspace_identity_and_session_api_isolation(setup):
    c, sid, auth, store, manager = setup
    store.note('private', 'private contents', 0, [])
    assert not Workspace(2, 5, sid).read()['notes']
    assert not Workspace(3, 4, sid).read()['notes']
    assert not Workspace(2, 4, str(uuid4())).read()['notes']
    assert c.get(f'/sessions/{uuid4()}/notebook').status_code == 404
    manager.return_value.get_session.side_effect = None
    manager.return_value.get_session.return_value = {'organization_id': 9}
    assert c.get(f'/sessions/{sid}/notebook').status_code == 404
    c.app.dependency_overrides.clear()
    assert c.get(f'/sessions/{sid}/notebook').status_code in (401, 403)


def test_document_open_read_and_revoked_note_access(setup):
    c, sid, auth, store, _ = setup
    prefix = f'/sessions/{sid}'
    source = {'kind': 'upload', 'title': 'lesson.txt', 'filename': 'lesson.txt', 'reference': '4/lesson.txt'}
    text = 'The fact is 42.\n' * 600
    async def resolve(auth, src, download=False):
        return Download('lesson.txt', text.encode(), 'text/plain') if download else None
    with patch.object(api.document_sources, 'list_sources', return_value=[source]), patch.object(api.document_sources, 'resolve', side_effect=resolve):
        ref = c.post(prefix + '/documents/sources', json={'kind': 'upload'}).json()['items'][0]['source_ref']
        response = c.post(prefix + '/documents/open', json={'source_ref': ref})
        assert response.status_code == 200, response.text
        rid = response.json()['read_id']
        assert 'text' not in response.json()
        result = c.get(prefix + '/documents/' + rid).json()
        assert result['text'] == text[:6000] and result['untrusted_source']
        assert c.get(prefix + '/documents/' + rid, params={'offset': result['next_offset']}).json()['text'] == text[6000:]
        saved = c.post(prefix + '/notebook', json={'name': 'assessment', 'content': '7/10', 'revision': 0})
        assert saved.status_code == 200 and rid in saved.json()['references']
    with patch.object(api.document_sources, 'resolve', side_effect=PermissionError('Source revoked')):
        assert c.get(prefix + '/documents/' + rid).status_code == 403
        assert c.get(prefix + '/notebook/read', params={'name': 'assessment'}).status_code == 403
        assert c.get(prefix + '/notebook').status_code == 403


def test_open_revalidates_after_extraction(setup):
    c, sid, auth, store, _ = setup
    ref = store.sources([{'kind': 'upload', 'title': 'test', 'reference': '4/test'}])[0]['source_ref']
    with patch.object(api.document_sources, 'resolve', side_effect=[Download('t.txt', b'text', 'text/plain'), PermissionError('revoked')]):
        assert c.post(f'/sessions/{sid}/documents/open', json={'source_ref': ref}).status_code == 403
    assert not store.read()['documents']


def test_no_arbitrary_paths_and_note_limits(setup):
    c, sid, auth, store, _ = setup
    assert c.post(f'/sessions/{sid}/documents/open', json={'source_ref': '/etc/passwd'}).status_code == 422
    assert c.post(f'/sessions/{sid}/documents/sources', json={'kind': 'upload', 'url': 'http://attacker/'}).status_code == 422
    with pytest.raises(ValueError): store.note('large', 'x' * 65537, 0, [])
    with pytest.raises(ValueError): store.note('missing', 'text', 0, ['unknown'])
    with pytest.raises(ValueError): store.document('unknown', ' ', {})


def test_synthetic_ten_document_notebook_assembly(setup):
    c, sid, auth, store, _ = setup
    ids = []
    for number in range(10):
        ref = store.sources([{'kind': 'upload', 'title': f'{number}.txt', 'reference': f'4/{number}.txt'}])[0]['source_ref']
        ids.append(store.document(ref, f'Answer {number}', {})['read_id'])
    with patch.object(api.document_sources, 'resolve', return_value=None):
        for number in range(10):
            response = c.post(f'/sessions/{sid}/notebook', json={'name': 'batch', 'content': '\n'.join(f'{i}: provisional {i}/10' for i in range(number + 1)), 'revision': number, 'references': ids})
            assert response.status_code == 200
        restored = c.get(f'/sessions/{sid}/notebook/read', params={'name': 'batch'}).json()
    assert restored['revision'] == 10 and len(restored['text'].splitlines()) == 10
    assert restored['references'] == sorted(ids)


def test_text_and_html_extraction():
    raw = ' whitespace\n\n café 📚\t'
    assert api.extract(Download('t.txt', raw.encode(), 'text/plain'))[0] == raw
    text, losses = api.extract(Download('t.html', b'<h1>Topic</h1><script>bad()</script><p>Evidence</p>', 'text/html'))
    assert 'Evidence' in text and 'bad()' not in text


def test_shell_commands_are_session_bound_and_do_not_enter_generic_cache(setup):
    from lamb.aac.liteshell.shell import LiteShell
    from lamb.aac.authorization import ActionAuthorizer
    c, sid, auth, store, _ = setup
    class Client:
        async def post(self, url, json):
            response = c.post(url.removeprefix('/creator/aac'), json=json)
            response.raise_for_status(); return response.json()
        async def get(self, url, params=None):
            response = c.get(url.removeprefix('/creator/aac'), params=params)
            response.raise_for_status(); return response.json()
    shell = LiteShell('', '', auth.user['email'], 2, user_id=4, session_id=sid)
    shell._http_client = Client()
    result = asyncio.run(shell.execute('lamb notebook write "batch" --content "draft output" --revision 0'))
    assert result.success, result.error
    assert ActionAuthorizer().check('notebook.write') == 'auto'
    payload = asyncio.run(shell.execute('lamb notebook read "batch"')).to_dict()
    assert payload['data']['text'] == 'draft output'
    with patch('lamb.aac.result_store.ResultStore', side_effect=AssertionError('must not use generic cache')):
        assert shell.model_result('lamb notebook read "batch"', payload) == payload
    denied = asyncio.run(shell.execute('lamb notebook read "batch" --session foreign'))
    assert not denied.success


def test_concurrent_notebook_updates_do_not_lose_writes(setup):
    from concurrent.futures import ThreadPoolExecutor
    _, sid, _, store, _ = setup
    store.note('race', 'original', 0, [])
    def write(value):
        try: return Workspace(2, 4, sid).note('race', value, 1, [])['revision']
        except ValueError: return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ['first', 'second']))
    assert sorted(map(str, results)) == ['2', 'conflict']
    assert store.read()['notes']['race']['revision'] == 2


def test_private_file_symlink_rejected(setup, tmp_path):
    _, _, _, store, _ = setup
    store.read()
    target = tmp_path/'secret.json'; target.write_text('{"private":"secret"}')
    (store.path/'workspace.json').symlink_to(target)
    with pytest.raises(OSError): store.read()
