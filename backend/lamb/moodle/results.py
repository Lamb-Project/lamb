"""Immutable, owner/account/generation-bound task evidence, outside static roots."""
import fcntl
import json
import os
import time
import uuid
from pathlib import Path

from .cache import positive_id
from .storage import ensure_private, private_root
from .forum_activity import preview

TTL_SECONDS = 24 * 60 * 60
MAX_RESULTS = 16
MAX_RESULT_BYTES = 4 * 1024 * 1024
MODEL_PAGE_BYTES = 6000


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode()


class ResultStore:
    def __init__(self, organization_id, owner_id, *, base_url, moodle_user_id, generation, root=None):
        root = Path(root) if root is not None else private_root()
        self.folder = root / positive_id(organization_id) / positive_id(owner_id) / 'results'
        self.binding = {'organization_id': int(organization_id), 'owner_id': int(owner_id),
            'base_url': base_url, 'moodle_user_id': int(moodle_user_id), 'generation': generation}

    def save(self, snapshot):
        ensure_private(self.folder)
        identity = str(uuid.uuid4())
        envelope = {'id': identity, 'binding': self.binding, 'expires_at': time.time() + TTL_SECONDS, 'snapshot': snapshot}
        payload = encoded(envelope)
        if len(payload) > MAX_RESULT_BYTES:
            raise ValueError('Moodle evidence storage limit exceeded; select fewer courses')
        fd = os.open(self.folder / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            # Bounded derived data retention; authored user documents are separate.
            files = sorted(self.folder.glob('*.json'), key=lambda p: p.stat().st_mtime)
            for path in files:
                if path.is_symlink():
                    raise ValueError('Unsafe Moodle evidence storage')
                if path.stat().st_mtime < time.time() - TTL_SECONDS or len(files) >= MAX_RESULTS:
                    path.unlink()
                else:
                    continue
                # Count remaining files without weakening the per-owner cap.
                files = [p for p in files if p != path]
            dest = self.folder / (identity + '.json')
            with os.fdopen(os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'wb') as out:
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())
        return identity

    def read(self, identity):
        try:
            identity = str(uuid.UUID(identity))
            ensure_private(self.folder)
            path = self.folder / (identity + '.json')
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
                data = source.read(MAX_RESULT_BYTES + 1)
            if len(data) > MAX_RESULT_BYTES:
                raise ValueError()
            envelope = json.loads(data)
            if envelope['binding'] != self.binding or envelope['expires_at'] <= time.time():
                raise ValueError()
            return envelope['snapshot']
        except (OSError, ValueError, KeyError, TypeError):
            raise PermissionError('Moodle evidence is unavailable or expired. Run the task again.') from None


def summary(identity, snapshot):
    result = {k: snapshot[k] for k in ('as_of', 'completed_at', 'window', 'coverage', 'budget', 'limitations')}
    result.update(result_id=identity, evidence_command=f'moodle evidence {identity}',
        view=f'/moodle?result={identity}', expires_in_seconds=TTL_SECONDS,
        course_preview=[{k: c[k] for k in ('id', 'name', 'status')} for c in snapshot['courses'][:10]],
        course_preview_complete=len(snapshot['courses']) <= 10,
        post_preview=[], post_preview_complete=False)
    for post in snapshot['posts'][:5]:
        text, shortened = preview(post['source'].get('message', ''), 200)
        subject, _ = preview(post['source'].get('subject', ''), 100)
        result['post_preview'].append({k: post[k] for k in ('id', 'course_id', 'forum_id', 'discussion_id', 'timecreated')} | {
            'subject': subject, 'text_excerpt': text, 'excerpt_shortened': shortened})
    # Stay within a byte cap even with multibyte names/content. This is a task
    # projection limit, not a claim of global model context accounting.
    while len(encoded(result)) > MODEL_PAGE_BYTES:
        if result['post_preview']:
            result['post_preview'].pop()
        elif result['course_preview']:
            result['course_preview'].pop()
            result['course_preview_complete'] = False
        else:
            raise ValueError('Moodle summary exceeds its fixed budget')
    result['post_preview_complete'] = len(result['post_preview']) == len(snapshot['posts']) and not any(
        p['excerpt_shortened'] for p in result['post_preview'])
    return result


def evidence_page(identity, snapshot, offset=0):
    """Explicit slices preserve all message HTML; never call an excerpt a thread."""
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError('Evidence offset must be a nonnegative integer')
    pieces = []
    for course in snapshot['courses']:
        pieces.append({'type': 'course', **{k: v for k, v in course.items() if k != 'forums'}})
        pieces.extend({'type': 'forum', 'course_id': course['id'], **f} for f in course['forums'])
    for post in snapshot['posts']:
        source = post['source']
        text = str(source.get('message', ''))
        subject, _ = preview(source.get('subject', ''), 100)
        for pos in range(0, max(1, len(text)), 600):
            pieces.append({'type': 'post_fragment', **{k: v for k, v in post.items() if k != 'source'},
                'subject': subject, 'html_fragment': text[pos:pos+600],
                'character_offset': pos, 'message_characters': len(text), 'last_fragment': pos+600 >= len(text)})
    if offset > len(pieces):
        raise ValueError('Evidence offset exceeds this result')
    response = {'result_id': identity, 'coverage': snapshot['coverage'], 'offset': offset,
        'items': [], 'next_offset': None, 'total_items': len(pieces), 'untrusted_source': True}
    for item in pieces[offset:]:
        candidate = {**response, 'items': [*response['items'], item], 'next_offset': offset + len(response['items']) + 1}
        if len(encoded(candidate)) > MODEL_PAGE_BYTES:
            break
        response['items'].append(item)
    next_offset = offset + len(response['items'])
    response['next_offset'] = next_offset if next_offset < len(pieces) else None
    return response
