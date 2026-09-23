"""Synthetic private stores only. Cleanup must never touch teaching resources."""
import asyncio
import json
import os
from types import SimpleNamespace
import uuid

import pytest
from lamb.private_storage import atomic_json, data_root, file_lock
from lamb.storage_lifecycle import OwnerStorage, owners, sweep_batch
from lamb.aac.result_store import ResultStore as AACResults
from lamb.moodle.results import ResultStore as MoodleResults


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setenv('LAMB_DB_PATH', str(tmp_path))
    return OwnerStorage(1, 7)


def test_chart_inventory_reports_calendar_capacity_without_auto_expiry(storage):
    from lamb.moodle.charts import MAX_CHARTS,MAX_CALENDAR_BYTES
    charts=storage.inspect()['stores']['charts']
    assert charts['quota_bytes']==MAX_CHARTS*MAX_CALENDAR_BYTES
    assert '128 KiB per chart, 512 KiB per deadline calendar' in charts['policy']
    assert 'no automatic expiry' in charts['policy']


def ticket(store, **extra):
    data = {'review': {}, 'scope': 'session', 'binding': {'generation': 1},
            'content': 'PRIVATE_ENCODED_BYTES', 'originals': {'source': 'PRIVATE_ORIGINAL'}, **extra}
    review = store.review(data)
    return review['review_id']


def expired(store, key):
    row = store.get('reviews', key)
    row['review']['expires_at'] = 1
    with store.lock():
        store.put('reviews', key, row)


def test_unapproved_reviews_do_not_duplicate_bodies(storage):
    store = storage.imports()
    key = ticket(store)
    row = store.get('reviews', key)
    assert 'content' not in row and 'originals' not in row
    assert row['review']['review_id'] == key


def test_inactive_owner_expiry_and_durable_history(storage):
    store = storage.imports()
    key = ticket(store)
    expired(store, key)
    aac = AACResults(1, 7)
    identity = aac.save({'data': 'private'}, origin={})['result_id']
    envelope = aac.read(identity)
    envelope['expires_at'] = 1
    atomic_json(aac.folder / (identity + '.json'), envelope)
    chart = storage.moodle / 'charts/1/7' / (str(uuid.uuid4()) + '.json')
    atomic_json(chart, {'snapshot': 'saved history'})
    receipt_id = str(uuid.uuid4())
    with store.lock():
        store.put('receipts', receipt_id, {'status': 'outcome_unknown', 'content': 'durable'})
    assert sweep_batch(owners(storage.root), storage.root, limit=20)
    assert not store.path('reviews', key).exists()
    assert not (aac.folder / (identity + '.json')).exists()
    assert store.get('receipts', receipt_id)['content'] == 'durable'
    assert json.loads(chart.read_text())['snapshot'] == 'saved history'
    with pytest.raises(PermissionError, match='do not repeat a write'):
        aac.read(identity)


def test_active_approval_survives_and_expired_approval_is_explicitly_invalid(storage):
    store = storage.imports()
    key = ticket(store)
    storage.clean()
    assert store.get('reviews', key)
    expired(store, key)
    storage.clean()
    with pytest.raises(PermissionError, match='Unknown Moodle document handle'):
        store.get('reviews', key)


@pytest.mark.parametrize('marker', ['approved', 'import_id', 'failed_result'])
def test_attempted_reviews_and_batch_children_never_expire(storage, marker):
    store = storage.imports()
    child = ticket(store)
    parent = ticket(store, children=[child], **{marker: True})
    expired(store, child)
    expired(store, parent)
    storage.clean()
    assert store.get('reviews', parent) and store.get('reviews', child)
    with pytest.raises(ValueError, match='protected'):
        storage.discard_review(child)
    with pytest.raises(ValueError):
        storage.discard_review(parent)


def test_pre_receipt_crash_retains_review_even_without_ticket_marker(storage):
    store = storage.imports()
    key = ticket(store)
    expired(store, key)
    with store.lock():
        store.put('receipts', str(uuid.uuid4()), {'review': {'review_id': key}, 'status': 'outcome_unknown'})
    storage.clean()
    assert store.get('reviews', key)


def test_explicit_discard_reclaims_quota_without_deleting_documents(storage, monkeypatch):
    store = storage.imports()
    key = ticket(store)
    original = storage.root / 'teaching-resource.txt'
    original.write_text('keep')
    used = storage.inspect()['stores']['imports']['bytes']
    monkeypatch.setattr('lamb.moodle.import_store.MAX_OWNER_BYTES', used + 5)
    with pytest.raises(ValueError, match='full'):
        ticket(store)
    assert storage.discard_review(key)['discarded_reviews'] == 1
    assert ticket(store)
    assert original.read_text() == 'keep'


def test_folder_discard_removes_only_its_unused_children(storage):
    store = storage.imports()
    child = ticket(store)
    parent = ticket(store, children=[child])
    assert storage.discard_review(parent)['discarded_reviews'] == 2


def test_cleanup_compacts_legacy_reviews_without_changing_hash_or_handles(storage):
    store = storage.imports()
    key = ticket(store, approved=True)
    row = store.get('reviews', key)
    row.update(content='X' * 10000, originals={'raw': 'Y' * 10000})
    row['review']['source_hash'] = 'hash-kept'
    with store.lock():
        store.put('reviews', key, row)
    result = storage.clean()
    assert result['compacted_reviews'] == 1 and result['reclaimed_bytes'] > 19000
    assert store.get('reviews', key)['review'] == row['review']
    # Restart sees the same unchanged logical schema; no DB migration needed.
    assert OwnerStorage(1, 7).imports().get('reviews', key)['approved']


def test_cleanup_refuses_import_or_run_lock_overlap(storage):
    store = storage.imports()
    key = ticket(store)
    expired(store, key)
    with store.lock():
        with pytest.raises(ValueError, match='in progress'):
            storage.clean()
    assert store.get('reviews', key)
    with file_lock(storage.tasks / 'runs'):
        with pytest.raises(ValueError, match='busy'):
            storage.clean()


def test_every_live_run_readback_reference_is_protected(storage, monkeypatch):
    evidence = MoodleResults(1, 7, base_url='https://fixture', moodle_user_id=70, generation=1, root=storage.moodle)
    first, second = evidence.save({'n': 1}), evidence.save({'n': 2})
    run = {'id': str(uuid.uuid4()), 'expires_at': 10**12, 'binding': evidence.binding,
           'last_result': second, 'working': first, 'next_results': {first: second}}
    atomic_json(storage.tasks / 'runs' / (run['id'] + '.json'), run)
    monkeypatch.setattr('lamb.moodle.results.MAX_RESULTS', 2)
    with pytest.raises(ValueError, match='active recovery handles'):
        evidence.save({'n': 3})
    assert evidence.read(first) == {'n': 1} and evidence.read(second) == {'n': 2}
    storage.clean(now=10**11)
    assert len(list(evidence.folder.glob('*.json'))) == 2
    storage.clean(now=10**12 + 1)
    assert not list(evidence.folder.glob('*.json'))
    assert not list((storage.tasks / 'runs').glob('*.json'))


def test_foreign_owner_and_org_inspection_does_not_expose_bytes(storage):
    key = ticket(storage.imports())
    for org, owner in ((1, 8), (2, 7)):
        other = OwnerStorage(org, owner)
        assert other.inspect()['stores']['imports']['bytes'] == 0
        with pytest.raises(PermissionError):
            other.discard_review(key)
    assert 'PRIVATE_' not in json.dumps(storage.inspect())


@pytest.mark.parametrize('value', ['', '.', 'relative/directory'])
def test_storage_root_must_be_explicit_and_absolute(monkeypatch, value):
    monkeypatch.setenv('LAMB_DB_PATH', value)
    with pytest.raises(ValueError, match='absolute'):
        data_root()


def test_symlink_category_and_corrupt_references_fail_closed(storage, tmp_path):
    store = storage.imports()
    foreign = tmp_path / 'foreign'
    foreign.mkdir()
    (store.root / 'reviews').symlink_to(foreign)
    with pytest.raises(ValueError, match='Unsafe'):
        storage.inspect()
    assert list(foreign.iterdir()) == []


def test_orphan_pending_file_cleanup_requires_age_and_lock(storage):
    folder = storage.root / 'aac_results/1/7'
    with file_lock(folder):
        old = folder / '.pending-old'
        fresh = folder / '.pending-new'
        old.write_text('incomplete')
        fresh.write_text('incomplete')
        os.utime(old, (1, 1))
    storage.clean()
    assert not old.exists() and fresh.exists()


def test_routes_require_auth_and_only_system_admin_can_target_other_owners(storage):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from lamb.auth_context import get_auth_context
    from lamb.storage_router import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get('/private-storage').status_code in (401, 403)
    auth = SimpleNamespace(user={'id': 7}, organization={'id': 1}, is_system_admin=False, is_org_admin=True)
    app.dependency_overrides[get_auth_context] = lambda: auth
    assert client.get('/private-storage').status_code == 200
    assert client.post('/private-storage/cleanup').status_code == 200
    for query in ('owner_id=8', 'organization_id=2', 'owner_id=8&organization_id=2'):
        assert client.get('/private-storage?' + query).status_code == 403
        assert client.post('/private-storage/cleanup?' + query).status_code == 403
    auth.is_system_admin = True
    assert client.get('/private-storage?owner_id=8&organization_id=2').status_code == 200


def test_invalid_category_cannot_escape_store(storage):
    with pytest.raises(ValueError):
        storage.imports().get('../elsewhere', str(uuid.uuid4()))


@pytest.mark.parametrize('status', ['processing', 'outcome_unknown', 'replacement_ready'])
def test_uncertain_imports_cannot_purge_originals(storage, status):
    store = storage.imports()
    identity = str(uuid.uuid4())
    row = {'import_id': identity, 'status': status, 'originals': {'source': 'private'}}
    with store.lock():
        store.put('receipts', identity, row)
    with pytest.raises(ValueError, match='uncertain'):
        storage.purge_originals(identity)
    assert store.get('receipts', identity) == row


def test_explicit_original_purge_retains_receipt_revision_and_destination(storage):
    store = storage.imports()
    identity, version = str(uuid.uuid4()), str(uuid.uuid4())
    row = {'import_id': identity, 'status': 'completed', 'revision': 2,
           'review': {'source_hash': 'hash', 'converted_hash': 'hash2'},
           'result': {'path': 'untouched-document'}, 'destination': {'single_file': True},
           'content': 'X' * 10000, 'originals': {'source': 'Y' * 10000}}
    with store.lock():
        store.put('receipts', identity, row)
        store.put('versions', version, dict(row, revision=1))
    assert storage.purge_originals(identity)['reclaimed_bytes'] > 38000
    kept = store.get('receipts', identity)
    assert kept['result'] == row['result'] and kept['review'] == row['review']
    assert 'originals' not in kept and 'content' not in kept
    assert store.get('versions', version)['revision'] == 1
    assert storage.purge_originals(identity)['reclaimed_bytes'] == 0


@pytest.mark.parametrize('key,kind', [('assistant.get', 'assistant'), ('kb.query', 'kb')])
def test_full_result_current_resource_recheck_and_legacy_invalidation(key, kind):
    from lamb.aac.result_authority import authority, require_current_authority
    from unittest.mock import Mock
    checker = Mock(return_value='shared')
    auth = SimpleNamespace(can_access_assistant=checker, can_access_kb=checker)
    origin = {'command': key, 'authority': authority(key, ['42'], {'data': {}})}
    require_current_authority(auth, origin)
    checker.return_value = 'none'
    with pytest.raises(PermissionError, match='current resource permissions'):
        require_current_authority(auth, origin)
    with pytest.raises(PermissionError, match='never repeat a write'):
        require_current_authority(auth, {'command': key})


def test_unknown_command_cannot_claim_empty_resource_authority():
    from lamb.aac.result_authority import require_current_authority
    with pytest.raises(PermissionError):
        require_current_authority(None, {'command': 'unknown', 'authority': {'version': 1, 'resources': []}})


@pytest.mark.parametrize('decision', ['reject', 'edit'])
def test_aac_rejection_and_edit_release_unused_review(storage, decision):
    from tests.test_aac_legacy import agent
    store = storage.imports()
    key = ticket(store)
    review = store.get('reviews', key)['review']
    runtime = SimpleNamespace(store=SimpleNamespace(organization_id=1, owner_id=7), cache_root=storage.moodle,
        context={'document_scope': 'session'}, result_binding=lambda: {'generation': 1})
    a, _, shell = agent([])
    shell.moodle = runtime
    a.pending_action = {'command': 'moodle import page ref --single-file', 'moodle_review': review}
    a.approval_decision = decision
    asyncio.run(a._resolve_pending_action('No'))
    assert not a.pending_action
    with pytest.raises(PermissionError):
        store.get('reviews', key)
    shell.execute.assert_not_awaited()


def test_original_purge_route_requires_explicit_confirmation(storage):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from lamb.auth_context import get_auth_context
    from lamb.storage_router import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_auth_context] = lambda: SimpleNamespace(
        user={'id': 7}, organization={'id': 1}, is_system_admin=False)
    client = TestClient(app)
    identity = str(uuid.uuid4())
    url = f'/private-storage/imports/{identity}/purge-originals'
    assert client.post(url, json={}).status_code == 422
    assert client.post(url, json={'confirm': 'yes'}).status_code == 422
    assert client.post(url, json={'confirm': 'purge-private-originals'}).status_code == 404


def test_atomic_replace_failure_preserves_previous_record(storage, monkeypatch):
    path = storage.root / 'atomic.json'
    atomic_json(path, {'version': 1})
    def fail(*args):
        raise OSError('Synthetic interrupted replacement')
    monkeypatch.setattr('lamb.private_storage.os.replace', fail)
    with pytest.raises(OSError):
        atomic_json(path, {'version': 2})
    assert json.loads(path.read_text()) == {'version': 1}
    assert not list(path.parent.glob('.pending-*'))


def test_corrupt_run_reference_cannot_trigger_evidence_eviction(storage):
    evidence = MoodleResults(1, 7, base_url='https://fixture', moodle_user_id=70, generation=1, root=storage.moodle)
    first = evidence.save({'n': 1})
    atomic_json(storage.tasks / 'runs' / (str(uuid.uuid4()) + '.json'), {'bad_schema': True})
    with pytest.raises(ValueError, match='Cannot verify'):
        evidence.save({'n': 2})
    with pytest.raises(KeyError):
        storage.clean()
    assert evidence.read(first) == {'n': 1}


def test_cleanup_worker_does_not_block_event_loop_and_shutdown_waits_for_lock_release(storage, monkeypatch):
    import threading
    from lamb.storage_lifecycle import cleanup_loop
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    def batch(*args):
        entered.set()
        assert release.wait(2)
        finished.set()
        return True
    monkeypatch.setattr('lamb.storage_lifecycle.sweep_batch', batch)
    async def run():
        task = asyncio.create_task(cleanup_loop(storage.root))
        assert await asyncio.to_thread(entered.wait, 2)
        # The event loop runs this cancellation while the worker holds a lock.
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()
    asyncio.run(run())


def test_result_reader_rechecks_permissions_after_projection(storage, monkeypatch):
    from unittest.mock import Mock
    from lamb.aac.result_reader import read_result
    from lamb.aac.result_authority import authority
    checker = Mock(return_value='shared')
    auth = SimpleNamespace(user={'id': 7}, organization={'id': 1, 'config': {}},
                           can_access_kb=checker, is_system_admin=False, is_org_admin=False)
    store = AACResults(1, 7)
    identity = store.save({'data': 'KB content'}, origin={
        'command': 'kb.query', 'authority': authority('kb.query', ['42'], {})})['result_id']
    monkeypatch.setattr('lamb.aac.brief.role_axes', lambda _: {'layers': ['creator']})
    def revoke(*args):
        checker.return_value = 'none'
        return {'text': 'must be withheld'}
    monkeypatch.setattr('lamb.aac.result_reader.page', revoke)
    with pytest.raises(PermissionError, match='current resource permissions'):
        read_result(auth, identity)
    assert checker.call_count == 2
