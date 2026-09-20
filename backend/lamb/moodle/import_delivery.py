"""Deliver approved bytes through existing authenticated Creator APIs.

Receipts are written before side effects. Retrying a review never uploads twice.
An interrupted upload with no returned job id is explicitly outcome-unknown.
"""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import PurePosixPath
import tempfile
import uuid
from .documents import CONVERT_TYPES
from .imports import PreparedImport, public_receipt
from .import_store import ImportStore
from .document_sources import digest, public_source
from .storage import ensure_private, private_root


def single_provenance(reference, content=None):
    path = private_root() / 'import-citations' / (digest(reference) + '.json')
    if not path.exists() or path.is_symlink(): return {}
    try:
        data = json.loads(path.read_text())
        if data['reference'] != reference or (content is not None and data['converted_hash'] != digest(content.encode())):
            return {}
        return data['source'] if isinstance(data['source'], dict) else {}
    except (OSError, ValueError, KeyError, TypeError):
        # Provenance is supplementary; a damaged sidecar must not break the
        # owner's otherwise valid single-file assistant.
        return {}


def save_single_provenance(reference, receipt):
    root = ensure_private(private_root() / 'import-citations')
    target = root / (digest(reference) + '.json')
    payload = {'reference': reference, 'converted_hash': receipt['review']['converted_hash'], 'source': public_source(receipt['source'])}
    fd, temporary = tempfile.mkstemp(dir=root)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(payload, out); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


async def finish(receipt, store, http, runtime):
    if receipt['status'] == 'completed': return public_receipt(receipt)
    if receipt['status'] not in {'processing', 'replacement_ready', 'failed'}:
        return dict(public_receipt(receipt), note='Import outcome needs inspection before retrying. No second upload was started.')
    kid = receipt['destination']['kb_id']
    job_id = receipt['result']['file_registry_id']
    for _ in range(15):
        job = await http.get(f'/creator/knowledgebases/kb/{kid}/ingestion-jobs/{job_id}')
        if job['status'] == 'completed': break
        if job['status'] in {'failed', 'cancelled', 'deleted'}:
            receipt['status'] = 'failed'
            receipt['result']['job_status'] = job['status']
            store.put('receipts', receipt['import_id'], receipt)
            return public_receipt(receipt)
        await asyncio.sleep(2)
    else:
        return dict(public_receipt(receipt), next_command='moodle import finish ' + receipt['import_id'],
                    note='Ingestion is still running. Previous content remains in place. Finish after the job completes.')
    if runtime.result_binding() != receipt['binding']:
        raise PermissionError('Moodle connection changed. Ingestion may have completed; previous content was not removed.')
    old = receipt.get('replaced_file_id')
    if old:
        receipt['status'] = 'replacement_ready'
        store.put('receipts', receipt['import_id'], receipt)
        # This is part of the approved replacement, after new ingestion succeeds.
        await http.delete(f'/creator/knowledgebases/kb/{kid}/files/{old}')
    receipt['status'] = 'completed'
    receipt['result']['job_status'] = 'completed'
    store.put('receipts', receipt['import_id'], receipt)
    return public_receipt(receipt)


async def deliver(prepared, http, runtime, owner_id):
    store = prepared.store
    with store.lock():
        if not isinstance(prepared, PreparedImport):
            # Reload inside the owner lock, not the snapshot read before it.
            return await finish(store.get('receipts', prepared.receipt['import_id']), store, http, runtime)
        data = prepared.data
        review_id = data['review']['review_id']
        ticket = store.get('reviews', review_id)
        if ticket.get('import_id'):
            return await finish(store.get('receipts', ticket['import_id']), store, http, runtime)
        previous = data.get('previous')
        import_id = previous['import_id'] if previous else str(uuid.uuid4())
        if previous:
            current = store.get('receipts', import_id)
            if current['revision'] != previous['revision'] or current['status'] != 'completed':
                raise PermissionError('Another replacement changed this import; review again')
            store.put('versions', str(uuid.uuid4()), current)
        receipt = {k: v for k, v in data.items() if k != 'previous'}
        receipt.update(import_id=import_id, revision=(previous['revision'] + 1 if previous else 1),
            status='outcome_unknown', imported_at=datetime.now(timezone.utc).isoformat(), result={})
        if previous and not data['destination']['single_file']:
            receipt['replaced_file_id'] = previous['result']['file_registry_id']
        # Record the operation before issuing a potentially irreversible write.
        store.put('receipts', import_id, receipt)
        ticket['import_id'] = import_id
        store.put('reviews', review_id, ticket)
        if runtime.result_binding() != data['binding']:
            raise PermissionError('Moodle connection changed before import')
        download = prepared.download
        if data['destination']['single_file']:
            if previous:
                from lamb.uploaded_files import owned_document
                reference = previous['result']['path']
                target = owned_document(reference, owner_id)
                fd, temporary = tempfile.mkstemp(dir=target.parent, prefix='.moodle-')
                try:
                    with os.fdopen(fd, 'wb') as out:
                        out.write(download.content); out.flush(); os.fsync(out.fileno())
                    os.replace(temporary, target)
                finally:
                    if os.path.exists(temporary): os.unlink(temporary)
                result = dict(previous['result'])
            else:
                result = await http.post('/creator/aac/files', files={'file': (download.filename, download.content, download.content_type)})
            receipt.update(status='completed', result=result)
            save_single_provenance(result['path'], receipt)
        else:
            suffix = PurePosixPath(download.filename).suffix.lower()
            plugin = 'markitdown_ingest' if suffix in CONVERT_TYPES else 'simple_ingest'
            kid = data['destination']['kb_id']
            provenance = dict(public_source(data['source']), imported_at=receipt['imported_at'],
                              source_hash=data['review']['source_hash'], import_id=import_id)
            result = await http.post(f'/creator/knowledgebases/kb/{kid}/plugin-ingest-file',
                files={'file': (download.filename, download.content, download.content_type)},
                data={'plugin_name': plugin, 'citation': data['source']['source_url'],
                      'moodle_provenance': json.dumps(provenance), 'chunk_size': '1000', 'chunk_overlap': '100'})
            if result.get('status') == 'error' or not result.get('file_registry_id'):
                raise ValueError('KB did not return an ingestion job. Import outcome is unknown; inspect the KB before retrying.')
            receipt.update(status='processing', result=result)
        store.put('receipts', import_id, receipt)
        return await finish(receipt, store, http, runtime)
