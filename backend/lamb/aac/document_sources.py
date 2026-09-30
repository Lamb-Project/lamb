"""Resolve document identities through current LAMB/Moodle permissions, never caller URLs."""
import asyncio
import json
import threading
from pathlib import Path
from urllib.parse import urlsplit, unquote
import httpx
from lamb.database_manager import LambDatabaseManager
from lamb.moodle.documents import Download, MAX_BYTES, validate_archive


def positive(value):
    result = int(value)
    if result < 1:
        raise ValueError('A positive resource ID is required')
    return result


def assistant_source(auth, identity):
    db = LambDatabaseManager()
    identity = positive(identity)
    item = db.get_assistant_by_id_with_publication(identity)
    if not item or item.get('organization_id') != auth.organization['id'] or not (
        item.get('owner') == auth.user['email'] or db.is_assistant_shared_with_user(identity, auth.user['id'])
    ):
        raise PermissionError('Assistant source requires ownership or explicit sharing')
    metadata = item.get('metadata') or '{}'
    metadata = json.loads(metadata) if isinstance(metadata, str) else metadata
    reference = metadata.get('file_path')
    if not reference:
        raise ValueError('Assistant has no single-file source')
    from lamb.uploaded_files import document_for_owner
    path = document_for_owner(reference, item['owner'])
    return path, {'kind': 'assistant', 'id': identity, 'title': item['name'], 'filename': path.name,
                  'reference': reference, 'citation': {'assistant_id': identity}}


async def kb_files(auth, identity):
    from creator_interface.kb_server_manager import KBServerManager
    identity = positive(identity)
    db = LambDatabaseManager()
    access, level = db.user_can_access_kb(str(identity), auth.user['id'])
    if not access or level not in {'owner', 'shared'}:
        raise PermissionError('Knowledge base is not accessible')
    manager = KBServerManager()
    details = await manager.get_knowledge_base_details(str(identity), auth.user, access_type=level)
    if not isinstance(details, dict) or details.get('status') == 'error':
        raise ValueError('Knowledge base is unavailable')
    return details.get('files', []), manager._get_kb_config_for_user(auth.user)


async def list_sources(auth, kind, identity=None, course=None, user=None):
    if kind in {'submission', 'moodle'}:
        return await moodle_call(auth, kind, positive(identity), positive(course),
                                       positive(user) if user else None, False, None)
    if kind == 'assistant':
        _, source = assistant_source(auth, identity)
        return [source]
    if kind == 'kb':
        files, _ = await kb_files(auth, identity)
        return [{'kind': 'kb', 'id': positive(identity), 'file_id': str(f['id']),
                 'title': f.get('filename') or f.get('name') or str(f['id']),
                 'filename': f.get('filename') or f.get('name'), 'citation': {'kb_id': positive(identity), 'file_id': str(f['id'])}}
                for f in files if f.get('status') != 'deleted']
    if kind == 'upload':
        from lamb.aac.files import ROOT, owned_file
        folder = ROOT / str(auth.user['id'])
        result = []
        for p in sorted(folder.iterdir()) if folder.is_dir() else []:
            if p.is_file() and not p.is_symlink():
                reference = f"{auth.user['id']}/{p.name}"
                owned_file(reference, auth.user['id'])
                result.append({'kind': 'upload', 'reference': reference, 'title': p.name, 'filename': p.name,
                               'citation': {'upload': reference}})
        return result
    raise ValueError('Document kinds: submission, moodle, kb, assistant, upload')


async def moodle_call(*args):
    cancel = threading.Event()
    try:
        return await asyncio.to_thread(moodle_sources, *args, cancel=cancel)
    except asyncio.CancelledError:
        cancel.set()
        raise


def moodle_sources(auth, kind, identity, course, user, download, selected, *, cancel=None):
    from lamb.moodle.runtime import MoodleRuntime
    from lamb.moodle.store import ConnectionStore
    from lamb.moodle.router import database
    from lamb.moodle.secrets import TokenCipher
    from lamb.moodle.client import MoodleHTTPClient
    from lamb.moodle.scoped_reads import execute_scoped_read
    from lamb.moodle.course_batch import course_sources
    from lamb.moodle.documents import download_file
    from lamb.moodle.document_sources import materialize
    runtime = MoodleRuntime(ConnectionStore(database(), auth.organization['id'], auth.user['id']))
    binding = runtime.result_binding()
    record = runtime.snapshot()['record']
    if selected and selected['binding'] != binding:
        raise PermissionError('Moodle account or connection changed; list the source again')
    token = TokenCipher().decrypt(record['token_encrypted'], organization_id=auth.organization['id'],
                                  owner_id=auth.user['id'], base_url=record['base_url'])
    from lamb.moodle.forum_activity import GuardedClient
    def revalidate():
        if runtime.result_binding() != binding:
            raise PermissionError('Moodle connection changed during document read')
    with MoodleHTTPClient(record['base_url'], token, functions=record.get('functions'), readonly=True) as raw_client:
        client = GuardedClient(raw_client, revalidate=revalidate, cancel=cancel)
        client.checkpoint()
        if kind == 'submission':
            if not user:
                raise ValueError('Submission reading requires --user USER_ID')
            data = execute_scoped_read(client, 'assign.status', {'assign_id': identity, 'user_id': user},
                    owner_moodle_id=record['moodle_user_id'], context={'course_id': course})
            submission = data.get('lastattempt', {}).get('submission') or {}
            files = [f for plugin in submission.get('plugins', []) for area in plugin.get('fileareas', [])
                     for f in area.get('files', []) if f.get('fileurl')]
            rows = [({'kind': kind, 'id': identity, 'course': course, 'user': user, 'binding': binding,
                       'title': f['filename'], 'filename': f['filename'], 'url': f['fileurl'],
                       'submission_id': submission.get('id'), 'attempt': submission.get('attemptnumber'),
                       'modified': submission.get('timemodified'),
                       'citation': {'course_id': course, 'assignment_id': identity, 'user_id': user,
                                    'submission_id': submission.get('id'), 'filename': f['filename']}}, f)
                    for f in files]
            # Online-text submission plugins are documents too.
            for plugin in submission.get('plugins', []):
                for field in plugin.get('editorfields', []):
                    if field.get('text'):
                        name = field.get('name', 'submission') + '.html'
                        source = {'kind': kind, 'id': identity, 'course': course, 'user': user, 'binding': binding,
                                  'title': name, 'filename': name, 'editor': field.get('name'),
                                  'submission_id': submission.get('id'), 'modified': submission.get('timemodified'),
                                  'citation': {'course_id': course, 'assignment_id': identity, 'user_id': user}}
                        rows.append((source, field))
        else:
            _, found, skipped = course_sources(client, record['base_url'], record['moodle_user_id'], course, [identity])
            rows = [({'kind': kind, 'id': identity, 'course': course, 'user': None, 'binding': binding,
                      'title': s.get('title') or s.get('source_path') or str(identity),
                      'filename': s.get('file', {}).get('filename'), 'document_source': s,
                      'citation': {'course_id': course, 'module_id': identity}}, s) for s in found]
            if not rows:
                raise ValueError('Module has no readable document: ' + str([v.get('reason') for v in skipped]))
        if runtime.result_binding() != binding:
            raise PermissionError('Moodle connection changed during source read')
        if selected is None:
            return [row[0] for row in rows]
        pair = next((r for r in rows if r[0] == selected), None)
        if pair is None:
            raise PermissionError('Document changed or is no longer accessible; list it again')
        if not download:
            return None
        source, raw = pair
        client.checkpoint()
        if kind == 'submission':
            if 'editor' in source:
                result = Download(source['filename'], raw['text'].encode(), 'text/html')
            else:
                result = download_file(record['base_url'], token, {**raw, 'url': raw['fileurl']}, single_file=False)
        else:
            from lamb.moodle.document_sources import resolve_source
            actual, html = resolve_source(client, record['base_url'], record['moodle_user_id'],
                                         {'course_id': course}, raw['kind'], saved=raw)
            result, _, _ = materialize(actual, html, record['base_url'], token, single_file=False)
        if runtime.result_binding() != binding:
            raise PermissionError('Moodle connection changed; document withheld')
        client.checkpoint()
        return result


async def resolve(auth, source, *, download=False):
    kind = source['kind']
    if kind in {'submission', 'moodle'}:
        return await moodle_call(auth, kind, source['id'], source['course'],
                                       source.get('user'), download, source)
    if kind == 'assistant':
        path, current = assistant_source(auth, source['id'])
        if current != source:
            raise PermissionError('Assistant source changed; list it again')
    elif kind == 'upload':
        from lamb.aac.files import owned_file
        path = owned_file(source['reference'], auth.user['id'])
    elif kind == 'kb':
        files, config = await kb_files(auth, source['id'])
        item = next((f for f in files if str(f['id']) == source['file_id'] and f.get('status') != 'deleted'), None)
        if item is None:
            raise PermissionError('KB document is no longer accessible')
        if not download:
            return
        base = urlsplit(config['url']); url = urlsplit(item.get('url') or item.get('file_url') or '')
        path_text = unquote(url.path)
        if url.query or url.fragment or '/static/' not in path_text or '\\' in path_text or any(v in {'.', '..'} for v in path_text.split('/')):
            raise PermissionError('KB source URL is outside the configured KB static document store')
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            async with client.stream('GET', config['url'].rstrip('/') + '/static/' + url.path.split('/static/', 1)[1], headers={'Authorization': 'Bearer ' + config['token']}) as response:
                if response.status_code != 200:
                    raise ValueError('KB original document is unavailable')
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise ValueError('Document exceeds 10 MiB')
        filename = Path(path_text).name  # URL extension identifies the stored original/converted representation
        validate_archive(bytes(body), Path(filename).suffix.lower())
        return Download(filename, bytes(body), 'application/octet-stream')
    else:
        raise ValueError('Unknown document source')
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Document exceeds 10 MiB')
    if download:
        return Download(path.name, path.read_bytes(), 'application/octet-stream')
