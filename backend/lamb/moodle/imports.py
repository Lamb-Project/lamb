"""Deterministic import review and freshness checks shared by AAC and CLI."""
from dataclasses import dataclass
from .document_sources import digest, public_source, resolve_source, materialize
from .documents import Download, session_scope
from .html_document import LOSS_NOTICE
from .import_store import ImportStore

# A warning threshold, not a claim about a provider's context window. This name
# anticipates the reference-document setting; 0.7 never truncates a document.
REFERENCE_DOCUMENT_MAX_TOKENS = 24000


@dataclass
class PreparedImport:
    download: Download
    data: dict
    store: ImportStore


@dataclass
class ResumeImport:
    receipt: dict
    store: ImportStore


def store_for_runtime(runtime):
    return ImportStore(runtime.store.organization_id, runtime.store.owner_id, runtime.cache_root)


def import_identity(binding):
    # Owner/org are enforced by the private store. Durable receipts survive a
    # credential rotation or policy edit, but never a different site/account.
    return {k: binding.get(k) for k in ('base_url', 'moodle_user_id')}


def same_import_account(binding, current):
    return import_identity(binding) == import_identity(current)


def load_receipt(runtime, import_id):
    receipt = store_for_runtime(runtime).get('receipts', import_id)
    if not same_import_account(receipt['binding'], runtime.result_binding()):
        raise PermissionError('Import belongs to a different Moodle site or account')
    return receipt


def resolve(runtime, client, record, kind, params):
    if kind == 'refresh':
        receipt = load_receipt(runtime, params['import_id'])
        if receipt['status'] != 'completed':
            raise ValueError('The previous import is not complete. Check its recorded destination/job before starting a replacement.')
        current, raw = resolve_source(client, record['base_url'], record['moodle_user_id'], runtime.context,
                                      receipt['source']['kind'], saved=receipt['source'])
        return current, raw, receipt['destination'], receipt
    current, raw = resolve_source(client, record['base_url'], record['moodle_user_id'], runtime.context,
                                 kind, ref=params['source_ref'])
    destination = {'single_file': params['single_file'], 'kb_id': params['kb_id']}
    return current, raw, destination, None


def prepared(runtime, client, record, token, key, params):
    source, raw, destination, previous = resolve(runtime, client, record, key.split('.')[1], params)
    return prepared_source(runtime, record, token, key, params, source, raw, destination, previous)


def prepared_source(runtime, record, token, key, params, source, raw, destination, previous=None):
    from .ingestion import configuration
    ingestion = configuration(params, single_file=destination['single_file'],
        previous=(previous or {}).get('review', {}).get('ingestion'))
    download, originals, losses = materialize(source, raw, record['base_url'], token, destination['single_file'])
    source_hash = digest({name: digest(body) for name, body in sorted(originals.items())})
    conversion_hash = digest(download.content)
    text = download.content.decode('utf-8') if destination['single_file'] else None
    # Explicit heuristic, independent of the AAC's own window.
    tokens = (len(text.encode('utf-8')) + 2) // 3 if text is not None else None
    review = {'source': public_source(source), 'destination': destination,
        'filename': download.filename, 'bytes': len(download.content),
        'source_hash': source_hash, 'converted_hash': conversion_hash,
        'conversion_losses': losses, 'conversion_notice': LOSS_NOTICE,
        'hidden_chapters_skipped': source.get('hidden_chapters_skipped', 0),
        'replacement_of': previous['import_id'] if previous else None}
    if ingestion is not None:
        from pathlib import PurePosixPath
        from .documents import CONVERT_TYPES
        review['ingestion'] = dict(ingestion, plugin_name='markitdown_ingest'
            if PurePosixPath(download.filename).suffix.lower() in CONVERT_TYPES else 'simple_ingest')
    if text is not None:
        review.update(characters=len(text), estimated_tokens=tokens,
            token_estimate_method='UTF-8 bytes / 3, rounded up; estimate, not the assistant model tokenizer',
            reference_document_max_tokens=REFERENCE_DOCUMENT_MAX_TOKENS,
            size_warning=('Large reference: use a knowledge base instead. Approving explicitly keeps the full document as single-file grounding; ensure the assistant model has enough context for this plus the conversation.'
                          if tokens > REFERENCE_DOCUMENT_MAX_TOKENS else
                          'The assistant model needs room for this document plus instructions and conversation.'))
    return {'review': review, 'scope': session_scope(runtime.context), 'binding': runtime.result_binding(),
        'key': key, 'params': params, 'source': source, 'destination': destination,
        'filename': download.filename, 'content_type': download.content_type,
        'content': ImportStore.encode(download.content),
        'originals': {name: ImportStore.encode(body) for name, body in originals.items()},
        'previous': {k: previous[k] for k in ('import_id', 'revision', 'result', 'destination')} if previous else None}


def prepare(runtime, client, record, token, key, params):
    if key == 'import.folder':
        from .folders import prepare_folder
        return prepare_folder(runtime, client, record, token, params)
    data = prepared(runtime, client, record, token, key, params)
    return store_for_runtime(runtime).review(data)


def confirm(runtime, client, record, token, key, params, review):
    if key == 'import.folder':
        from .folders import confirm_folder
        return confirm_folder(runtime, client, record, token, params, review)
    if not review: raise PermissionError('Review the document, conversion and size before confirming an import')
    store = store_for_runtime(runtime)
    approved = store.consume(review, session_scope(runtime.context), runtime.result_binding())
    if approved['key'] != key or approved['params'] != params:
        raise PermissionError('Import command changed after review')
    fresh = prepared(runtime, client, record, token, key, params)
    expected = {k: v for k, v in review.items() if k not in {'review_id', 'expires_at'}}
    if 'ingestion' not in expected:
        # Pre-option pending approvals used the fixed 1000/100 defaults.
        fresh['review'].pop('ingestion', None)
    if fresh['review'] != expected or fresh['binding'] != approved['binding']:
        raise PermissionError('Moodle source or destination changed after review; nothing imported. Review it again.')
    download = Download(fresh['filename'], store.decode(fresh['content']), fresh['content_type'])
    fresh['review'] = review
    return PreparedImport(download, fresh, store)


def check(runtime, client, record, token, params):
    receipt = load_receipt(runtime, params['import_id'])
    if receipt['source']['kind'] == 'page' and not params.get('verify_content'):
        # The Page API embeds the body in its response. For a cheap check use
        # the exported course-module timestamp instead, without calling it.
        from .document_sources import modules
        from .scope import MoodleScope
        old = receipt['source']
        MoodleScope(client, record['moodle_user_id']).require_teacher(old['course_id'])
        module = next((m for m in modules(client, old['course_id'])
                       if m.get('modname') == 'page' and int(m.get('instance', 0)) == old['item_id']
                       and int(m['id']) == old['module_id']), None)
        if not module or module.get('uservisible') is False or module.get('visible') == 0:
            raise PermissionError('Moodle page is no longer accessible')
        entry = next((e for e in module.get('contents', []) if e.get('filename') == 'index.html'), {})
        modified = entry.get('timemodified')
        source = {**public_source(old), 'timemodified': modified, 'title': module.get('name', old['title'])}
        source.pop('source_hash', None)
        source.pop('size_bytes', None)  # No current body read means no new size measurement.
        changed = (modified != old['timemodified'] or source['title'] != old['title']) if modified is not None else None
        return {'import_id': receipt['import_id'], 'status': receipt['status'], 'source': source,
                'metadata_changed': changed, 'content_hash_checked': False, 'content_changed': None,
                'note': 'Compared exported page timestamp/title only; no Page body read. Equal metadata does not prove unchanged bytes. Use --verify-content to compare.'}
    source, raw = resolve_source(client, record['base_url'], record['moodle_user_id'], runtime.context,
                                receipt['source']['kind'], saved=receipt['source'])
    result = {'import_id': receipt['import_id'], 'status': receipt['status'], 'source': public_source(source),
        'metadata_changed': source['metadata_hash'] != receipt['source']['metadata_hash'],
        'content_hash_checked': False, 'content_changed': None}
    if params.get('verify_content'):
        _, originals, _ = materialize(source, raw, record['base_url'], token, receipt['destination']['single_file'])
        result.update(content_hash_checked=True,
                      content_changed=digest({n: digest(b) for n, b in sorted(originals.items())}) != receipt['review']['source_hash'])
    result['note'] = 'Metadata equality alone does not prove unchanged bytes. Use --verify-content to download and compare.'
    return result


def public_receipt(receipt):
    result = {k: receipt.get(k) for k in ('import_id', 'status', 'imported_at', 'revision', 'review', 'destination', 'result')}
    if receipt.get('status') == 'completed' and receipt.get('destination', {}).get('kb_id'):
        # The original upload response said processing/zero documents. It is
        # historical transport data, not the current completed ingestion state.
        result['result'] = dict(receipt.get('result', {}), status='completed', job_status='completed', message='Ingestion completed')
        result['result'].pop('document_count', None)
    return result
