"""Deterministic, bounded Moodle Folder inventory and approved batch imports."""
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath
import time
from .document_sources import digest, modules
from .documents import KB_TYPES, MAX_BYTES, session_scope, Download
from .scope import MoodleScope
from .imports import PreparedImport, prepared_source, store_for_runtime, public_receipt
from .import_store import ImportStore

MAX_FILES = 20
MAX_ENTRIES = 100
MAX_BATCH_BYTES = 20 * 1024 * 1024


def clean_path(path, directory=False):
    if not isinstance(path, str) or not path.startswith('/') or '\\' in path or any(c in path for c in '\r\n\x00'):
        raise ValueError('Use an absolute Moodle folder path, for example /readings/')
    if any(part in {'.', '..'} for part in path.split('/')):
        raise ValueError('Moodle folder paths cannot contain traversal components')
    normalized = '/' + '/'.join(part for part in path.split('/') if part)
    return normalized.rstrip('/') + '/' if directory else normalized


def folder_modules(client, course, owner):
    MoodleScope(client, owner).require_teacher(course)
    return [m for m in modules(client, course) if m.get('modname') == 'folder'
            and m.get('uservisible') is not False and m.get('visible') != 0]


def folder_source(module, course, base_url):
    return {'kind': 'folder', 'course_id': int(course), 'module_id': int(module['id']),
            'item_id': int(module['instance']), 'title': str(module.get('name', 'Folder'))[:1000],
            'source_url': base_url.rstrip('/') + '/mod/folder/view.php?id=' + str(module['id'])}


def listing(client, record, context, course):
    result = []
    for module in folder_modules(client, course, record['moodle_user_id']):
        source = folder_source(module, course, record['base_url'])
        ref = 'mfld_' + digest([session_scope(context), course, module['id']])[:24]
        context.setdefault('folders', {})[ref] = source
        result.append(dict(source, source_ref=ref,
                           file_count=sum(e.get('type') == 'file' for e in module.get('contents', []))))
    context['course_id'] = int(course)
    return result


def folder_files(client, base_url, owner, proof):
    module = next((m for m in folder_modules(client, proof['course_id'], owner)
                   if int(m['id']) == proof['module_id'] and int(m['instance']) == proof['item_id']), None)
    if not module: raise PermissionError('Moodle Folder is no longer accessible in this instructor course')
    source = folder_source(module, proof['course_id'], base_url)
    result, paths = [], set()
    for entry in module.get('contents', []):
        if entry.get('type') != 'file': continue
        name = entry.get('filename', '')
        if not name or PurePosixPath(name).name != name or '\\' in name:
            raise ValueError('Invalid Moodle Folder filename')
        path = clean_path(entry.get('filepath', '/'), True) + name
        path = clean_path(path)
        if path in paths: raise ValueError('Moodle returned duplicate folder paths; import withheld')
        paths.add(path)
        file = {'filename': name, 'url': entry.get('fileurl', ''),
                'filesize': max(0, int(entry.get('filesize', 0))), 'timemodified': entry.get('timemodified', 0)}
        current = {**source, 'kind': 'folder_file', 'title': path, 'source_path': path,
                   'file': file, 'timemodified': file['timemodified'], 'size_bytes': file['filesize'],
                   'external': bool(entry.get('isexternalfile', False))}
        current['metadata_hash'] = digest(current)
        result.append(current)
    return source, sorted(result, key=lambda row: row['source_path'])


def inventory(runtime, client, record, params, saved=None):
    proof = saved or runtime.context.get('folders', {}).get(params['source_ref'])
    if not proof or (not saved and proof['course_id'] != runtime.context.get('course_id')):
        raise PermissionError('List this Moodle Folder in this conversation and selected instructor course first')
    source, files = folder_files(client, record['base_url'], record['moodle_user_id'], proof)
    path = clean_path(params.get('path', '/'), True)
    excluded = {clean_path(p, p.endswith('/')) for p in params.get('exclude', [])}
    files = [f for f in files if f['source_path'].startswith(path)]
    if len(files) > MAX_ENTRIES: raise ValueError('Folder inventory exceeds 100 files; select a smaller --path')
    if not files: raise ValueError('No files found beneath this Moodle folder path')
    if any(not any(f['source_path'] == p or (p.endswith('/') and f['source_path'].startswith(p)) for f in files)
           for p in excluded):
        raise ValueError('An excluded path was not present in this folder selection; inspect again')
    included, skipped = [], []
    for file in files:
        p = file['source_path']
        reason = ('excluded_by_user' if any(p == x or (x.endswith('/') and p.startswith(x)) for x in excluded) else
                  'external_repository_file' if file['external'] else
                  'unsupported_format' if PurePosixPath(p).suffix.lower() not in KB_TYPES else
                  'over_10_MiB' if file['size_bytes'] > MAX_BYTES else None)
        if reason: skipped.append({'path': p, 'bytes': file['size_bytes'], 'reason': reason})
        else: included.append(file)
    result = {'source': source, 'path': path, 'files': [{'path': f['source_path'], 'bytes': f['size_bytes']} for f in included],
              'skipped': skipped, 'file_count': len(included), 'source_bytes': sum(f['size_bytes'] for f in included),
              'limits': {'files_per_batch': MAX_FILES, 'bytes_per_batch': MAX_BATCH_BYTES}}
    result['ready'] = bool(included) and len(included) <= MAX_FILES and result['source_bytes'] <= MAX_BATCH_BYTES
    return result, included


def build(runtime, client, record, token, params, saved=None):
    inv, sources = inventory(runtime, client, record, params, saved)
    if not inv['ready']:
        raise ValueError('Choose 1-20 supported files totalling at most 20 MiB; narrow --path or use --exclude')
    destination = {'single_file': False, 'kb_id': params['kb_id']}
    if params.get('new_kb'):
        destination.update(new_kb=params['new_kb'], description=params.get('description', ''))
    children, size = [], 0
    for source in sources:
        child = prepared_source(runtime, record, token, 'import.folder-file', params, source, None, destination)
        size += sum(len(ImportStore.decode(v)) for v in child['originals'].values())
        if size > MAX_BATCH_BYTES: raise ValueError('Downloaded folder exceeds 20 MiB; nothing imported')
        children.append(child)
    review = {**inv, 'kind': 'folder', 'destination': destination,
              'bytes': sum(c['review']['bytes'] for c in children),
              'files': [dict(c['review'], path=c['source']['source_path']) for c in children],
              'conversion_notice': children[0]['review']['conversion_notice'],
              'note': 'One approval covers these exact files. Unsupported and excluded files are not imported. No silent synchronization.'}
    return review, children


def prepare_folder(runtime, client, record, token, params):
    review, children = build(runtime, client, record, token, params)
    storage = store_for_runtime(runtime)
    child_ids = [storage.review(c)['review_id'] for c in children]
    return storage.review({'review': review, 'scope': session_scope(runtime.context), 'binding': runtime.result_binding(),
                           'key': 'import.folder', 'params': dict(params, exclude=list(params['exclude'])),
                           'children': child_ids})


@dataclass
class PreparedFolder:
    ticket: dict
    children: list
    store: ImportStore


def confirm_folder(runtime, client, record, token, params, review, resume=False):
    if not review: raise PermissionError('Inspect and approve the exact folder inventory first')
    storage = store_for_runtime(runtime)
    ticket = storage.get('reviews', review.get('review_id'))
    if (ticket['scope'] != session_scope(runtime.context) or ticket['binding'] != runtime.result_binding()
            or ticket['key'] != 'import.folder' or ticket['review'] != review):
        raise PermissionError('Folder approval belongs to another owner, session or connection')
    if ticket['params'] != dict(params, exclude=list(params['exclude'])):
        raise PermissionError('Folder selection changed after review')
    if not ticket.get('approved') and review['expires_at'] < time.time():
        raise PermissionError('Folder review expired; inspect it again')
    fresh, children = build(runtime, client, record, token, params, saved=review['source'] if resume else None)
    for old, current in zip(review.get('files', []), fresh.get('files', [])):
        if 'ingestion' not in old:
            current.pop('ingestion', None)
    if fresh != {k:v for k,v in review.items() if k not in {'review_id','expires_at'}}:
        raise PermissionError('Folder contents changed after review; no further files imported. Review again.')
    for child, key in zip(children, ticket['children']):
        child['review'] = storage.get('reviews', key)['review']
    return PreparedFolder(ticket, children, storage)


def load_batch(runtime, batch_id):
    ticket = store_for_runtime(runtime).get('reviews', batch_id)
    if ticket.get('key') != 'import.folder' or not ticket.get('approved'):
        raise PermissionError('Unknown approved folder batch')
    if ticket['binding'] != runtime.result_binding() or ticket['scope'] != session_scope(runtime.context):
        raise PermissionError('Folder batch belongs to another session or connection')
    return ticket


def status(runtime, ticket):
    storage = store_for_runtime(runtime)
    files = []
    for identity in ticket['children']:
        child = storage.get('reviews', identity)
        receipt = storage.get('receipts', child['import_id']) if child.get('import_id') else None
        row = {'path': child['source']['source_path'], 'status': receipt['status'] if receipt else 'not_started',
               'import_id': child.get('import_id'), 'result': public_receipt(receipt)['result'] if receipt else None}
        if row['status'] != 'completed' and ticket.get('errors', {}).get(identity): row['error'] = ticket['errors'][identity]
        files.append(row)
    counts = dict(Counter(f['status'] for f in files))
    done = counts.get('completed', 0) == len(files)
    creation = ticket.get('kb_creation')
    destination = ticket['review']['destination']
    if creation and creation.get('kb_id'):
        destination = {'single_file': False, 'kb_id': creation['kb_id'], 'name': destination['new_kb']}
    return {'batch_id': ticket['review']['review_id'], 'status': 'completed' if done else 'partial',
            'source': ticket['review']['source'], 'destination': destination,
            **({'kb_creation': creation} if creation else {}),
            'files': files, 'counts': counts, 'skipped': ticket['review']['skipped'],
            'next_command': None if done else 'moodle folder finish ' + ticket['review']['review_id']}


async def deliver_folder(prepared, http, runtime, owner):
    from .import_delivery import deliver
    storage, ticket = prepared.store, prepared.ticket
    identity = ticket['review']['review_id']
    with storage.lock():
        ticket = storage.get('reviews', identity)
        if runtime.result_binding() != ticket['binding']:
            raise PermissionError('Moodle connection changed before folder delivery')
        ticket['approved'] = True
        storage.put('reviews', identity, ticket)
    if ticket['review']['destination'].get('new_kb'):
        from .folder_destination import create_destination
        if not await create_destination(storage, identity, http, runtime):
            return status(runtime, storage.get('reviews', identity))
        ticket = storage.get('reviews', identity)
    started = time.monotonic()
    for child in prepared.children:
        if time.monotonic() - started > 60: break
        if runtime.result_binding() != ticket['binding']: raise PermissionError('Moodle connection changed; inspect batch status')
        if ticket.get('kb_creation'):
            # The approved virtual destination stays in the immutable review.
            # Receipts bind its actual created id for uploads and future refreshes.
            child = dict(child, destination={'single_file': False, 'kb_id': ticket['kb_creation']['kb_id']})
        download = Download(child['filename'], storage.decode(child['content']), child['content_type'])
        try:
            await deliver(PreparedImport(download, child, storage), http, runtime, owner)
        except Exception:
            # Receipts distinguish an unstarted file from an uncertain upload.
            # Do not claim that an HTTP error means the remote write failed.
            with storage.lock():
                ticket = storage.get('reviews', identity)
                ticket.setdefault('errors', {})[child['review']['review_id']] = 'Delivery interrupted or failed; inspect this file receipt/job before retrying.'
                storage.put('reviews', identity, ticket)
    return status(runtime, storage.get('reviews', identity))
