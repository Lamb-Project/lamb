"""One approved batch import of documents chosen across a course (#524).

The agent chooses course modules (from the course inventory); this module turns them into the
exact set of importable documents deterministically: a Resource contributes its files, a Folder
its files, a Page or Book its converted text. Everything else is reported as skipped with a
reason. Review, approval, delivery, status and resume reuse the folder batch machinery.
"""
import time
from .document_sources import activity_sources, digest, modules
from .documents import KB_TYPES, MAX_BYTES, session_scope
from .folders import PreparedFolder, folder_files, folder_source
from .import_store import ImportStore
from .imports import prepared_source, store_for_runtime
from .scope import MoodleScope

MAX_ITEMS = 30
MAX_BATCH_BYTES = 30 * 1024 * 1024
DOCUMENT_MODULES = ('resource', 'folder', 'page', 'book')


def resource_files(module, course, base_url):
    """Files of a Moodle Resource module, as sources like folder files."""
    result = []
    for entry in module.get('contents', []):
        if entry.get('type') != 'file' or not entry.get('filename'):
            continue
        file = {'filename': entry['filename'], 'url': entry.get('fileurl', ''),
                'filesize': max(0, int(entry.get('filesize', 0))), 'timemodified': entry.get('timemodified', 0)}
        source = {'kind': 'course_file', 'course_id': int(course), 'module_id': int(module['id']),
                  'item_id': int(module.get('instance', 0)), 'title': str(module.get('name', ''))[:1000],
                  'source_url': base_url.rstrip('/') + '/mod/resource/view.php?id=' + str(module['id']),
                  'source_path': f"{module.get('name', '')}/{entry['filename']}"[:1000], 'file': file,
                  'timemodified': file['timemodified'], 'size_bytes': file['filesize'],
                  'external': bool(entry.get('isexternalfile', False))}
        source['metadata_hash'] = digest(source)
        result.append(source)
    return result


def course_sources(client, base_url, owner, course, module_ids):
    """Deterministic document sources for the chosen modules, in the order chosen, and skips."""
    course = MoodleScope(client, owner).require_teacher(course)
    by_id = {int(m['id']): m for m in modules(client, course)}
    sources, skipped, seen = [], [], set()
    for module_id in module_ids:
        if module_id in seen:
            continue
        seen.add(module_id)
        module = by_id.get(int(module_id))
        name = (module or {}).get('name', '')
        if module is None:
            skipped.append({'module_id': module_id, 'reason': 'not_in_course'}); continue
        if module.get('uservisible') is False or module.get('visible') == 0:
            skipped.append({'module_id': module_id, 'name': name, 'reason': 'hidden'}); continue
        kind = module.get('modname')
        if kind not in DOCUMENT_MODULES:
            skipped.append({'module_id': module_id, 'name': name, 'type': kind, 'reason': 'not_a_document'}); continue
        if kind == 'resource':
            files = resource_files(module, course, base_url)
        elif kind == 'folder':
            # Folder paths stay as the folder code resolves them later (refresh, resume).
            files = folder_files(client, base_url, owner, folder_source(module, course, base_url))[1]
        else:
            found = activity_sources(client, kind, course, owner, base_url, selected=int(module['instance']))
            if not found:
                skipped.append({'module_id': module_id, 'name': name, 'reason': 'not_importable'}); continue
            proof = dict(found[0][0], source_path=name[:1000])
            sources.append(proof); continue
        if not files:
            skipped.append({'module_id': module_id, 'name': name, 'reason': 'no_files'})
        for f in files:
            suffix = '.' + f['file']['filename'].rsplit('.', 1)[-1].lower() if '.' in f['file']['filename'] else ''
            reason = ('external_repository_file' if f.get('external') else
                      'unsupported_format' if suffix not in KB_TYPES else
                      'over_10_MiB' if f['size_bytes'] > MAX_BYTES else None)
            if reason:
                skipped.append({'module_id': module_id, 'path': f['source_path'], 'bytes': f['size_bytes'], 'reason': reason})
            else:
                sources.append(f)
    return course, sources, skipped


def build(runtime, client, record, token, params, saved=None):
    course = (saved or {}).get('course_id', params['course_id'])
    module_ids = list((saved or {}).get('modules', params['module']))
    course, sources, skipped = course_sources(client, record['base_url'], record['moodle_user_id'], course, module_ids)
    if not sources:
        raise ValueError('None of the chosen modules has an importable document; see the skipped reasons')
    if len(sources) > MAX_ITEMS:
        raise ValueError(f'Choose at most {MAX_ITEMS} documents per batch; split the selection')
    destination = {'single_file': False, 'kb_id': params['kb_id']}
    if params.get('new_kb'):
        destination.update(new_kb=params['new_kb'], description=params.get('description', ''))
    children, size = [], 0
    for source in sources:
        child = prepared_source(runtime, record, token, 'import.course-item', params, source, None, destination)
        size += sum(len(ImportStore.decode(v)) for v in child['originals'].values())
        if size > MAX_BATCH_BYTES:
            raise ValueError('The chosen documents exceed 30 MiB together; split the selection. Nothing imported.')
        children.append(child)
    review = {'kind': 'course', 'source': {'kind': 'course', 'course_id': course, 'modules': module_ids},
              'destination': destination, 'file_count': len(children),
              'bytes': sum(c['review']['bytes'] for c in children),
              'files': [dict(c['review'], path=c['source']['source_path']) for c in children],
              'skipped': skipped, 'limits': {'documents_per_batch': MAX_ITEMS, 'bytes_per_batch': MAX_BATCH_BYTES},
              'conversion_notice': children[0]['review']['conversion_notice'],
              'note': 'One approval covers these exact documents. Skipped modules are not imported. No silent synchronization.'}
    return review, children


def batch_params(params):
    return dict(params, module=list(params['module']))


def prepare_course(runtime, client, record, token, params):
    review, children = build(runtime, client, record, token, params)
    storage = store_for_runtime(runtime)
    child_ids = [storage.review(c)['review_id'] for c in children]
    return storage.review({'review': review, 'scope': session_scope(runtime.context), 'binding': runtime.result_binding(),
                           'key': 'import.course', 'params': batch_params(params), 'children': child_ids})


def confirm_course(runtime, client, record, token, params, review, resume=False):
    if not review:
        raise PermissionError('Review the exact document selection first')
    storage = store_for_runtime(runtime)
    ticket = storage.get('reviews', review.get('review_id'))
    if (ticket['scope'] != session_scope(runtime.context) or ticket['binding'] != runtime.result_binding()
            or ticket['key'] != 'import.course' or ticket['review'] != review):
        raise PermissionError('Batch approval belongs to another owner, session or connection')
    if ticket['params'] != batch_params(params):
        raise PermissionError('Document selection changed after review')
    if not ticket.get('approved') and review['expires_at'] < time.time():
        raise PermissionError('Batch review expired; prepare it again')
    fresh, children = build(runtime, client, record, token, params, saved=review['source'] if resume else None)
    for old, current in zip(review.get('files', []), fresh.get('files', [])):
        if 'ingestion' not in old:
            current.pop('ingestion', None)
    if fresh != {k: v for k, v in review.items() if k not in {'review_id', 'expires_at'}}:
        raise PermissionError('Course documents changed after review; nothing further imported. Prepare the batch again.')
    for child, key in zip(children, ticket['children']):
        child['review'] = storage.get('reviews', key)['review']
    return PreparedFolder(ticket, children, storage)
