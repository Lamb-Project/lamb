import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from tests.test_moodle_folders import folder, listed
from tests.test_moodle_store import stores
from lamb.aac.liteshell.shell import LiteShell, prepare_command
from lamb.moodle.import_review import render_review


def prepare(rt):
    command = f'moodle import folder {listed(rt)} --new-kb "Teacher readings" --description "For teachers" --chunk-size 2000 --chunk-overlap 100'
    key, _, params, _ = prepare_command(command)
    return command, rt.prepare_import(key.removeprefix('moodle.'), params)


def test_one_review_creates_one_kb_imports_and_resumes_without_duplicates(folder):
    rt, _, _ = folder
    command, review = prepare(rt)
    assert 'Teacher readings' in render_review(review, 'ca', advanced=False)
    assert '2000 caràcters' in render_review(review, 'ca', advanced=False)
    assert 'markitdown_ingest' not in render_review(review, 'ca', advanced=False)
    uploads, creates = [], []
    async def post(path, **kwargs):
        if path == '/creator/knowledgebases':
            creates.append(kwargs); return {'kb_id': '48', 'name': 'Teacher readings'}
        assert '/kb/48/plugin-ingest-file' in path
        uploads.append(kwargs)
        assert kwargs['data']['chunk_size'] == '2000'
        return {'status': 'success', 'file_registry_id': len(uploads)}
    http = SimpleNamespace(post=AsyncMock(side_effect=post), get=AsyncMock(return_value={'status': 'completed'}))
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt); shell._http_client = http
    async def run():
        assert not (await shell.execute(command)).success
        http.post.assert_not_awaited()
        result = await shell.execute(command, confirmed=True, review=review)
        assert result.success, result.error
        assert result.data['status'] == 'completed' and result.data['destination']['kb_id'] == 48
        assert result.data['kb_creation']['status'] == 'completed'
        assert len(creates) == 1 and len(uploads) == 3
        again = await shell.execute(command, confirmed=True, review=review)
        resumed = await shell.execute('moodle folder finish ' + result.data['batch_id'], confirmed=True)
        assert again.success and resumed.success
        assert len(creates) == 1 and len(uploads) == 3
    asyncio.run(run())


@pytest.mark.parametrize('failure', ['timeout', 'cancel', 'offline', 'bad-response'])
def test_uncertain_or_failed_creation_never_creates_twice_or_uploads(folder, failure):
    rt, _, _ = folder
    command, review = prepare(rt)
    async def post(path, **kwargs):
        assert path == '/creator/knowledgebases'
        if failure == 'timeout': raise TimeoutError('Reply lost')
        if failure == 'cancel': raise asyncio.CancelledError()
        if failure == 'offline': return {'kb_server_available': False}
        return {'unexpected': True}
    http = SimpleNamespace(post=AsyncMock(side_effect=post))
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt); shell._http_client = http
    async def run():
        try:
            await shell.execute(command, confirmed=True, review=review)
        except asyncio.CancelledError:
            assert failure == 'cancel'
        result = await shell.execute(command, confirmed=True, review=review)
        assert result.success and result.data['status'] == 'partial'
        assert result.data['counts'] == {'not_started': 3}
        assert result.data['kb_creation']['status'] == ('failed' if failure == 'offline' else 'outcome_unknown')
        await shell.execute('moodle folder finish ' + result.data['batch_id'], confirmed=True)
        assert http.post.await_count == 1
    asyncio.run(run())


def test_changed_source_does_not_even_create_the_new_kb(folder):
    rt, state, _ = folder
    command, review = prepare(rt)
    state['files']['/new.md'] = b'NEW'
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt)
    shell._http_client = SimpleNamespace(post=AsyncMock())
    result = asyncio.run(shell.execute(command, confirmed=True, review=review))
    assert not result.success
    shell._http_client.post.assert_not_awaited()


def test_partial_import_keeps_created_kb_and_never_recreates_it(folder):
    rt, _, _ = folder
    command, review = prepare(rt)
    calls = []
    async def post(path, **kwargs):
        calls.append(path)
        if path == '/creator/knowledgebases': return {'kb_id': 48}
        if len(calls) == 3: raise TimeoutError('Upload reply lost')
        return {'status': 'success', 'file_registry_id': len(calls)}
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt)
    shell._http_client = SimpleNamespace(post=AsyncMock(side_effect=post), get=AsyncMock(return_value={'status':'completed'}))
    async def run():
        result = await shell.execute(command, confirmed=True, review=review)
        assert result.success and result.data['status'] == 'partial'
        assert result.data['kb_creation']['kb_id'] == 48
        assert result.data['counts'] == {'completed': 2, 'outcome_unknown': 1}
        await shell.execute('moodle folder finish ' + result.data['batch_id'], confirmed=True)
        assert calls.count('/creator/knowledgebases') == 1 and len(calls) == 4
    asyncio.run(run())


def test_parallel_confirmations_cannot_create_two_kbs(folder):
    rt, _, _ = folder
    command, review = prepare(rt)
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        async def post(path, **kwargs):
            if path == '/creator/knowledgebases':
                entered.set(); await release.wait(); return {'kb_id': 48}
            return {'status': 'success', 'file_registry_id': 1}
        http = SimpleNamespace(post=AsyncMock(side_effect=post), get=AsyncMock(return_value={'status':'completed'}))
        first, second = [LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt) for _ in range(2)]
        first._http_client = second._http_client = http
        task = asyncio.create_task(first.execute(command, confirmed=True, review=review))
        await asyncio.wait_for(entered.wait(), 2)
        try:
            refused = await second.execute(command, confirmed=True, review=review)
            assert not refused.success and 'in progress' in refused.error
        finally:
            release.set()
        assert (await task).success
        assert sum(c.args[0] == '/creator/knowledgebases' for c in http.post.call_args_list) == 1
    asyncio.run(run())


@pytest.mark.parametrize('suffix', ['--new-kb ""', '--new-kb " "', '--new-kb X --to kb 12', '--new-kb X 12', '--description X --to kb 12'])
def test_ambiguous_or_empty_destination_rejected(suffix):
    with pytest.raises(ValueError):
        prepare_command('moodle import folder ref ' + suffix)
