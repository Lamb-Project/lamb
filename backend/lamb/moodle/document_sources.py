"""Live instructor-scoped source resolution. Document bodies stay server-side."""
import hashlib
import json
from pathlib import PurePosixPath
from moodle_cli.services.course import CourseService
from moodle_cli.services.content import ContentService
from .scope import MoodleScope
from .documents import Download, download_file, session_scope, MAX_BYTES
from .html_document import convert_html, LOSS_NOTICE


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    return hashlib.sha256(value).hexdigest()


def modules(client, course):
    return [m for s in CourseService(client).get_contents(course) for m in s.modules]


def book_chapters(module):
    entries = module.get('contents', [])
    structure = next((e for e in entries if e.get('filename') == 'structure' and e.get('type') == 'content'), None)
    if not structure:
        raise ValueError('Moodle did not provide this book’s chapter structure')
    tree = json.loads(structure['content'])
    visible, hidden = [], 0
    def walk(nodes, parent_hidden=False):
        nonlocal hidden
        for node in nodes:
            is_hidden = parent_hidden or bool(int(node.get('hidden', 0)))
            if is_hidden:
                hidden += 1
            else:
                href = node['href'].strip('/')
                path = '/' + href.rsplit('/', 1)[0] + '/'
                file = next((f for f in entries if f.get('filepath') == path and f.get('filename') == 'index.html'), None)
                if not file: raise ValueError('Moodle chapter export is incomplete; nothing imported')
                visible.append({'title': node['title'], 'level': int(node.get('level', 0)),
                    'chapter_id': int(path.strip('/')), 'url': file['fileurl'], 'filename': 'index.html',
                    'filesize': file.get('filesize', 0), 'timemodified': file.get('timemodified', 0)})
            walk(node.get('subitems', []), is_hidden)
    walk(tree)
    if len(visible) > 100: raise ValueError('Book import is limited to 100 visible chapters')
    return visible, hidden


def activity_sources(client, kind, course, owner_moodle_id, base_url):
    course = MoodleScope(client, owner_moodle_id).require_teacher(course)
    available = {int(m['instance']): m for m in modules(client, course) if m.get('modname') == kind}
    records = ContentService(client).list_activities(kind, course)
    if isinstance(records, dict): records = records.get(kind + 's', [])
    result = []
    for item in records:
        module = available.get(int(item['id']))
        if not module or int(item.get('course', course)) != course: continue
        if module.get('uservisible') is False or module.get('visible') == 0: continue
        proof = {'kind': kind, 'course_id': course, 'module_id': int(module['id']), 'item_id': int(item['id']),
            'title': str(item['name'])[:1000], 'timemodified': item.get('timemodified', 0),
            'source_url': base_url.rstrip('/') + '/mod/' + kind + '/view.php?id=' + str(module['id'])}
        raw = item.get('content', '') if kind == 'page' else None
        if kind == 'page':
            encoded = raw.encode('utf-8')
            if len(encoded) > MAX_BYTES: raise ValueError('Moodle page exceeds the 10 MiB import limit')
            proof.update(size_bytes=len(encoded), source_hash=digest(encoded))
        else:
            chapters, hidden = book_chapters(module)
            proof.update(chapters=chapters, hidden_chapters_skipped=hidden,
                         size_bytes=sum(c['filesize'] for c in chapters),
                         size_is_estimate=True)
        proof['metadata_hash'] = digest(proof)
        result.append((proof, raw))
    return result


def public_source(proof):
    return {k: v for k, v in proof.items() if k not in {'chapters', 'listing', 'file', 'metadata_hash'}}


def list_activities(client, kind, course, owner_moodle_id, base_url, context):
    rows = activity_sources(client, kind, course, owner_moodle_id, base_url)
    context['course_id'] = int(course)
    output = []
    for proof, _ in rows:
        ref = 'md_' + digest([session_scope(context), kind, course, proof['item_id']])[:24]
        context.setdefault('documents', {})[ref] = proof
        output.append(dict(public_source(proof), source_ref=ref))
    return output


def resolve_source(client, base_url, owner_moodle_id, context, kind, ref=None, saved=None):
    proof = saved or (context.get('files', {}).get(ref) if kind == 'file' else context.get('documents', {}).get(ref))
    if not proof or (not saved and proof['course_id'] != context.get('course_id')):
        raise PermissionError('List this source in the selected instructor course and this conversation before importing')
    course = MoodleScope(client, owner_moodle_id).require_teacher(proof['course_id'])
    if kind == 'folder_file':
        from .folders import folder_files
        _, files = folder_files(client, base_url, owner_moodle_id, proof)
        found = next((f for f in files if f['source_path'] == proof['source_path']), None)
        if not found: raise PermissionError('Moodle folder file disappeared or is no longer accessible')
        return found, None
    if kind == 'file':
        from .scoped_reads import execute_scoped_read
        fresh_context = dict(context, course_id=course)
        files = execute_scoped_read(client, 'file.list', proof['listing'], owner_moodle_id=owner_moodle_id, context=fresh_context)
        item = next((f for f in files if f.get('url') == proof['file']['url'] and f.get('filename') == proof['file']['filename']), None)
        if not item: raise PermissionError('Moodle source disappeared or is no longer accessible')
        module = next((m for m in modules(client, course) if m.get('contextid') == proof['listing']['contextid']), None)
        if not module: raise PermissionError('Moodle source is outside the verified course')
        clean = {k: v for k, v in item.items() if k != 'file_id'}
        current = {'kind': 'file', 'course_id': course, 'listing': proof['listing'], 'file': item,
            'module_id': module['id'], 'item_id': module.get('instance'), 'title': item['filename'],
            'timemodified': item.get('timemodified', 0), 'size_bytes': item.get('filesize', 0),
            'source_url': base_url.rstrip('/') + '/mod/' + module['modname'] + '/view.php?id=' + str(module['id']),
            'metadata_hash': digest(clean)}
        return current, None
    candidates = activity_sources(client, kind, course, owner_moodle_id, base_url)
    found = next((row for row in candidates if row[0]['item_id'] == proof['item_id']), None)
    if not found: raise PermissionError('Moodle source disappeared or is no longer accessible')
    return found


def materialize(proof, raw, base_url, token, single_file):
    """Return a download, private originals and losses; never return these to AAC."""
    kind = proof['kind']
    originals, losses = {}, {}
    if kind in {'file', 'folder_file'}:
        download = download_file(base_url, token, proof['file'], single_file=single_file)
        originals[download.filename] = download.content
        if PurePosixPath(download.filename).suffix.lower() == '.html':
            text, losses = convert_html(download.content.decode('utf-8'), proof['source_url'])
            download = Download(PurePosixPath(download.filename).stem + '.md', text.encode(), 'text/markdown')
        if kind == 'folder_file':
            # Preserve stable, distinct destination names for duplicate basenames.
            path = PurePosixPath(download.filename)
            name = path.stem[:120] + '-' + digest([proof['module_id'], proof['source_path']])[:12] + path.suffix
            download = Download(name, download.content, download.content_type)
    elif kind == 'page':
        originals['original.html'] = raw.encode()
        text, losses = convert_html(raw, proof['source_url'])
        download = Download('page-' + str(proof['item_id']) + '.md', text.encode(), 'text/markdown')
    else:
        parts = ['# ' + proof['title']]
        for chapter in proof['chapters']:
            source = download_file(base_url, token, chapter, single_file=True)
            originals[str(chapter['chapter_id']) + '.html'] = source.content
            if sum(map(len, originals.values())) > MAX_BYTES:
                raise ValueError('Combined book exceeds the 10 MiB import limit')
            text, dropped = convert_html(source.content.decode('utf-8'), proof['source_url'])
            for key, n in dropped.items(): losses[key] = losses.get(key, 0) + n
            parts.append('#' * min(6, chapter['level'] + 2) + ' ' + chapter['title'] + '\n\n' + text)
        if not proof['chapters']: raise ValueError('Book has no visible chapters to import')
        download = Download('book-' + str(proof['item_id']) + '.md', '\n\n'.join(parts).encode(), 'text/markdown')
    if len(download.content) > MAX_BYTES: raise ValueError('Converted document exceeds the 10 MiB limit')
    return download, originals, losses
