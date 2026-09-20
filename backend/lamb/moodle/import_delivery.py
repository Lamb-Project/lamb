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
from lamb.document_provenance import single_provenance
from .documents import CONVERT_TYPES
from .imports import PreparedImport, public_receipt, same_import_account
from .import_store import ImportStore
from .document_sources import digest, public_source
from .storage import ensure_private, private_root


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


def failed_attempt(receipt, store):
    """Keep failure evidence and restore the last completed revision, if any."""
    receipt['status'] = 'failed'
    result = public_receipt(receipt)
    previous_id = receipt.get('previous_version')
    if previous_id:
        previous = store.get('versions', previous_id)
        store.put('versions', str(uuid.uuid4()), receipt)
        store.put('receipts', receipt['import_id'], previous)
        result['previous_revision_retained'] = previous['revision']
    else:
        store.put('receipts', receipt['import_id'], receipt)
    review_id = receipt.get('review', {}).get('review_id')
    if review_id:
        ticket = store.get('reviews', review_id)
        ticket['failed_result'] = result
        store.put('reviews', review_id, ticket)
    return result


def definite_refusal(error):
    import httpx
    while error is not None:
        if getattr(error, 'status_code', None) in {400, 401, 403, 404, 405, 413, 415, 422}:
            return True
        if getattr(error, 'status_code', None) == 503 and getattr(error, 'detail', None) == 'KB server is not available':
            return True  # Creator's explicit pre-ingestion availability refusal.
        if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)):
            return True  # Request was not sent. Read/write timeouts stay unknown.
        error = error.__cause__
    return False


async def finish(receipt, store, http, runtime):
    binding = runtime.result_binding()
    if not same_import_account(receipt['binding'], binding):
        raise PermissionError('Import belongs to a different Moodle site or account')
    if receipt['status'] == 'completed': return public_receipt(receipt)
    if receipt['status'] == 'failed': return public_receipt(receipt)
    if receipt['status'] not in {'processing', 'replacement_ready'}:
        return dict(public_receipt(receipt), note='Import outcome needs inspection before retrying. No second upload was started.')
    kid = receipt['destination']['kb_id']
    job_id = receipt['result']['file_registry_id']
    for _ in range(15):
        job = await http.get(f'/creator/knowledgebases/kb/{kid}/ingestion-jobs/{job_id}')
        if job['status'] == 'completed': break
        if job['status'] in {'failed', 'cancelled', 'deleted'}:
            receipt['result']['job_status'] = job['status']
            return failed_attempt(receipt, store)
        await asyncio.sleep(2)
    else:
        return dict(public_receipt(receipt), next_command='moodle import finish ' + receipt['import_id'],
                    note='Ingestion is still running. Previous content remains in place. Finish after the job completes.')
    if runtime.result_binding() != binding:
        raise PermissionError('Moodle connection changed. Ingestion may have completed; previous content was not removed.')
    old = receipt.get('replaced_file_id')
    if old:
        receipt['status'] = 'replacement_ready'
        store.put('receipts', receipt['import_id'], receipt)
        # A SQLite row id alone is not permanent source identity. A removed file
        # may have been replaced by an unrelated file under the same id.
        from lamb.aac.liteshell.http_client import APIResponseError
        try:
            old_job = await http.get(f'/creator/knowledgebases/kb/{kid}/ingestion-jobs/{old}')
        except APIResponseError as error:
            if error.status_code != 404: raise
            old_job = None  # Already absent; no deletion is necessary.
        if old_job is not None and old_job.get('status') != 'deleted':
            provenance = old_job.get('plugin_params', {}).get('moodle_provenance', {})
            if isinstance(provenance, str):
                try: provenance = json.loads(provenance)
                except ValueError: provenance = {}
            previous = store.get('versions', receipt['previous_version']) if receipt.get('previous_version') else None
            if (not previous or not isinstance(provenance, dict) or provenance.get('import_id') != receipt['import_id']
                    or provenance.get('source_hash') != previous['review']['source_hash']):
                return dict(public_receipt(receipt), note='New content was ingested, but the previous file identity could not be verified. No file was deleted; inspect the KB before finishing.')
            if runtime.result_binding() != binding:
                raise PermissionError('Moodle connection changed before replacement cleanup')
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
        if ticket.get('failed_result'): return ticket['failed_result']
        if ticket.get('import_id'):
            return await finish(store.get('receipts', ticket['import_id']), store, http, runtime)
        if runtime.result_binding() != data['binding']:
            raise PermissionError('Moodle connection changed before import')
        previous = data.get('previous')
        previous_version = None
        import_id = previous['import_id'] if previous else str(uuid.uuid4())
        if previous:
            current = store.get('receipts', import_id)
            if current['revision'] != previous['revision'] or current['status'] != 'completed':
                raise PermissionError('Another replacement changed this import; review again')
            previous_version = str(uuid.uuid4())
            store.put('versions', previous_version, current)
        receipt = {k: v for k, v in data.items() if k != 'previous'}
        receipt.update(import_id=import_id, revision=(previous['revision'] + 1 if previous else 1),
            status='outcome_unknown', imported_at=datetime.now(timezone.utc).isoformat(), result={})
        if previous_version: receipt['previous_version'] = previous_version
        if previous and not data['destination']['single_file']:
            receipt['replaced_file_id'] = previous['result']['file_registry_id']
        # Record the operation before issuing a potentially irreversible write.
        store.put('receipts', import_id, receipt)
        ticket['import_id'] = import_id
        store.put('reviews', review_id, ticket)
        if runtime.result_binding() != data['binding']:
            receipt['result'] = {'message': 'Connection changed before any import was sent.'}
            failed_attempt(receipt, store)
            raise PermissionError('Moodle connection changed before import')
        try:
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
        except Exception as error:
            if definite_refusal(error):
                receipt['result'] = {'message': 'Destination refused the import before ingestion. Review again to retry.'}
                return failed_attempt(receipt, store)
            raise
        store.put('receipts', import_id, receipt)
        return await finish(receipt, store, http, runtime)
