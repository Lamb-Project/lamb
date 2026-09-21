import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import respx
from lamb.aac.liteshell.shell import LiteShell, prepare_command
from lamb.moodle.ingestion import configuration
from tests.test_moodle_import import source, review
from tests.test_moodle_store import stores
from tests.test_moodle_folders import folder, listed, reviewed


def test_typed_chunk_options_all_imports_and_invalid_single_file_settings():
    for kind in ('file', 'page', 'book', 'folder', 'refresh'):
        prefix = f'moodle import {kind} ref' + (' --to kb 12' if kind != 'refresh' else '')
        _, _, params, _ = prepare_command(prefix + ' --chunk-size 2000 --chunk-overlap 0 --splitter-type TokenTextSplitter')
        cfg = configuration(params)
        assert cfg['chunk_size'] == 2000 and cfg['chunk_overlap'] == 0 and cfg['units'] == 'tokens'
        for suffix in ('--chunk-size 0', '--chunk-size nope', '--chunk-overlap -1', '--splitter-type evil'):
            with pytest.raises(ValueError): prepare_command(prefix + ' ' + suffix)
    for params in ({'chunk_size': 10}, {'chunk_size': 10, 'chunk_overlap': 10}):
        with pytest.raises(ValueError): configuration(params)
    with pytest.raises(ValueError): prepare_command('moodle import file ref --single-file --chunk-size 2000')
    assert configuration({'chunk_size': 3000}, previous={'chunk_size': 2000, 'chunk_overlap': 200, 'splitter_type': 'TokenTextSplitter'})['chunk_overlap'] == 200


@respx.mock
def test_page_review_delivery_and_refresh_preserve_overrides(source):
    rt, state, _ = source
    ref = rt.execute('page.list', {'course_id': 10})[0]['source_ref']
    command = f'moodle import page {ref} --to kb 12 --chunk-size 2000 --chunk-overlap 200'
    approval = review(rt, command)
    assert approval['ingestion']['chunk_size'] == 2000
    assert approval['ingestion']['units'] == 'characters'
    http = SimpleNamespace(post=AsyncMock(return_value={'status': 'success', 'file_registry_id': 44}),
                           get=AsyncMock(return_value={'status': 'completed'}), delete=AsyncMock())
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt); shell._http_client = http
    async def run():
        assert not (await shell.execute(command.replace('2000', '3000'), confirmed=True, review=approval)).success
        http.post.assert_not_awaited()
        done = await shell.execute(command, confirmed=True, review=approval)
        assert done.success, done.error
        sent = http.post.call_args.kwargs['data']
        assert sent['chunk_size'] == '2000' and sent['chunk_overlap'] == '200'
        assert sent['splitter_type'] == 'RecursiveCharacterTextSplitter'
        assert done.data['review']['ingestion'] == approval['ingestion']
        refresh = 'moodle import refresh ' + done.data['import_id']
        assert review(rt, refresh)['ingestion'] == approval['ingestion']
        changed = review(rt, refresh + ' --chunk-size 3000')['ingestion']
        assert changed['chunk_size'] == 3000 and changed['chunk_overlap'] == 200
        with pytest.raises(ValueError): review(rt, refresh + ' --chunk-size 100')
        assert http.post.await_count == 1
    asyncio.run(run())


@respx.mock
def test_folder_every_child_job_and_receipt_share_approved_settings(folder):
    rt, _, _ = folder
    command, approval = reviewed(rt, listed(rt), '--chunk-size 2048 --chunk-overlap 128 --splitter-type TokenTextSplitter')
    assert all(row['ingestion']['units'] == 'tokens' for row in approval['files'])
    uploads = []
    async def upload(path, **kwargs):
        uploads.append(kwargs['data'])
        return {'status': 'success', 'file_registry_id': len(uploads)}
    http = SimpleNamespace(post=AsyncMock(side_effect=upload), get=AsyncMock(return_value={'status': 'completed'}))
    shell = LiteShell('', '', 'fixture', 1, user_id=7, moodle=rt); shell._http_client = http
    async def run():
        refused = await shell.execute(command.replace('2048', '2000'), confirmed=True, review=approval)
        assert not refused.success and not uploads
        done = await shell.execute(command, confirmed=True, review=approval)
        assert done.success, done.error
        assert done.data['counts'] == {'completed': 3}
        assert len(uploads) == 3
        assert all(row['chunk_size'] == '2048' and row['chunk_overlap'] == '128' and row['splitter_type'] == 'TokenTextSplitter' for row in uploads)
        await shell.execute('moodle folder finish ' + done.data['batch_id'])
        assert len(uploads) == 3
    asyncio.run(run())
