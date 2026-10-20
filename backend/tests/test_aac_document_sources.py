"""Source adapters use verified identities, including the stored submission attachment."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch, Mock
from urllib.parse import parse_qs
import pytest
import respx
from httpx import Response
from lamb.aac import document_sources as src
from tests.test_moodle_store import stores
from tests.test_moodle_runtime import runtime


@pytest.fixture
def moodle(stores):
    rt = runtime(stores)
    auth = SimpleNamespace(user={'id': 7, 'email': 'fixture@test'}, organization={'id': 1})
    with patch('lamb.moodle.runtime.MoodleRuntime', return_value=rt), patch('lamb.moodle.router.database', return_value=stores[0]), patch('lamb.moodle.secrets.TokenCipher', return_value=rt._cipher):
        yield auth, rt


def submission():
    return {'lastattempt': {'submission': {'id': 123, 'attemptnumber': 0, 'timemodified': 50, 'plugins': [
        {'type': 'file', 'fileareas': [{'files': [{'filename': 'work.txt', 'fileurl': 'https://moodle.test/webservice/pluginfile.php/30/assignsubmission_file/submission_files/123/work.txt', 'filesize': 6}]}]},
        {'type': 'onlinetext', 'editorfields': [{'name': 'onlinetext', 'text': '<p>Online answer</p>'}]}
    ]}}}


def test_submission_files_online_text_and_revoked_scope(moodle):
    auth, rt = moodle
    with patch('lamb.moodle.scoped_reads.execute_scoped_read', return_value=submission()) as scoped, respx.mock:
        route = respx.post('https://moodle.test/webservice/pluginfile.php/30/assignsubmission_file/submission_files/123/work.txt').mock(return_value=Response(200, content=b'answer'))
        rows = asyncio.run(src.list_sources(auth, 'submission', 99, 10, 8))
        assert len(rows) == 2
        scoped.assert_called_with(scoped.call_args.args[0], 'assign.status', {'assign_id': 99, 'user_id': 8}, owner_moodle_id=70, context={'course_id': 10})
        result = asyncio.run(src.resolve(auth, rows[0], download=True))
        assert result.content == b'answer'
        assert parse_qs(route.calls[0].request.content.decode())['token'] == ['fixture']
        assert asyncio.run(src.resolve(auth, rows[1], download=True)).content == b'<p>Online answer</p>'
        scoped.side_effect = PermissionError('not a teacher')
        with pytest.raises(PermissionError): asyncio.run(src.resolve(auth, rows[0]))
        assert len(route.calls) == 1


def test_changed_attempt_and_connection_withhold_old_reference(moodle):
    auth, rt = moodle
    data = submission()
    with patch('lamb.moodle.scoped_reads.execute_scoped_read', return_value=data):
        source = asyncio.run(src.list_sources(auth, 'submission', 99, 10, 8))[0]
        data['lastattempt']['submission']['timemodified'] += 1
        with pytest.raises(PermissionError, match='changed'): asyncio.run(src.resolve(auth, source))
        rt.store.disconnect()
        with pytest.raises(PermissionError): asyncio.run(src.resolve(auth, source))


def test_assistant_explicit_share_required_even_for_admin(tmp_path):
    auth = SimpleNamespace(user={'id': 4, 'email': 'owner@test'}, organization={'id': 2}, is_system_admin=True)
    path = tmp_path/'source.txt'; path.write_text('exact source')
    item = {'id': 5, 'name': 'assistant', 'owner': 'other@test', 'organization_id': 2, 'metadata': '{"file_path":"8/source.txt"}'}
    with patch.object(src, 'LambDatabaseManager') as factory, patch('lamb.uploaded_files.document_for_owner', return_value=path):
        db = factory.return_value; db.get_assistant_by_id_with_publication.return_value = item
        db.is_assistant_shared_with_user.return_value = False
        with pytest.raises(PermissionError): src.assistant_source(auth, 5)
        db.is_assistant_shared_with_user.return_value = True
        rows = asyncio.run(src.list_sources(auth, 'assistant', 5))
        assert asyncio.run(src.resolve(auth, rows[0], download=True)).content == b'exact source'
        db.is_assistant_shared_with_user.return_value = False
        with pytest.raises(PermissionError): asyncio.run(src.resolve(auth, rows[0]))


def test_kb_original_read_uses_configured_origin_and_rechecks_file():
    auth = SimpleNamespace(user={'id': 4}, organization={'id': 2})
    files = [{'id': '12', 'filename': 'Original.pdf', 'file_url': 'https://public-kb.test/static/4/3/converted.md'}]
    config = {'url': 'https://internal-kb.test', 'token': 'test-token'}
    with patch.object(src, 'kb_files', return_value=(files, config)), respx.mock:
        route = respx.get('https://internal-kb.test/static/4/3/converted.md').mock(return_value=Response(200, content=b'# Extracted text'))
        source = asyncio.run(src.list_sources(auth, 'kb', 3))[0]
        download = asyncio.run(src.resolve(auth, source, download=True))
        assert download.content == b'# Extracted text' and download.filename == 'converted.md'
        assert route.call_count == 1
        files.clear()
        with pytest.raises(PermissionError): asyncio.run(src.resolve(auth, source))


def test_kb_private_non_static_url_rejected():
    source = {'kind': 'kb', 'id': 3, 'file_id': '12', 'filename': 'a.txt'}
    for url in ['https://kb.test/secrets', 'https://kb.test/static/../secret', 'https://kb.test/static/a?token=secret']:
        with patch.object(src, 'kb_files', return_value=([{'id': '12', 'file_url': url}], {'url': 'https://kb.test', 'token': 'x'})):
            with pytest.raises(PermissionError): asyncio.run(src.resolve(None, source, download=True))


def test_upload_path_and_foreign_owner_denied(tmp_path):
    auth = SimpleNamespace(user={'id': 4}, organization={'id': 2})
    with patch('lamb.aac.files.ROOT', tmp_path):
        (tmp_path/'4').mkdir(); (tmp_path/'4/a.txt').write_text('owned')
        rows = asyncio.run(src.list_sources(auth, 'upload'))
        assert len(rows) == 1
        for reference in ['5/secret.txt', '../secret.txt', '/etc/passwd']:
            with pytest.raises(ValueError): asyncio.run(src.resolve(auth, {'kind': 'upload', 'reference': reference}, download=True))
