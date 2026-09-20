"""Owner-scoped import receipts, originals and review handles outside /static."""
import base64
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
from .storage import ensure_private, private_root

MAX_OWNER_BYTES = 256 * 1024 * 1024


def identity(value):
    try:
        if str(uuid.UUID(str(value))) != str(value): raise ValueError()
    except (ValueError, AttributeError):
        raise PermissionError('Unknown Moodle document handle') from None
    return str(value)


class ImportStore:
    def __init__(self, organization_id, owner_id, root=None):
        self.root = ensure_private(Path(root or private_root()) / 'imports' / str(int(organization_id)) / str(int(owner_id)))

    @contextmanager
    def lock(self):
        fd = os.open(self.root / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as handle:
            try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('Another document operation is in progress; retry when it finishes') from None
            yield

    def path(self, category, key):
        path = ensure_private(self.root / category) / (identity(key) + '.json')
        if path.is_symlink(): raise PermissionError('Unsafe Moodle document storage')
        return path

    def get(self, category, key):
        path = self.path(category, key)
        if not path.is_file(): raise PermissionError('Unknown Moodle document handle')
        return json.loads(path.read_text())

    def put(self, category, key, data):
        path = self.path(category, key)
        payload = json.dumps(data, ensure_ascii=False).encode()
        used = sum(p.stat().st_size for p in self.root.rglob('*.json') if p != path and not p.is_symlink())
        if used + len(payload) > MAX_OWNER_BYTES:
            raise ValueError('Private Moodle import storage is full; ask an administrator to archive old imports')
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(payload); out.flush(); os.fsync(out.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def list(self, category):
        folder = ensure_private(self.root / category)
        for path in sorted(folder.glob('*.json')):
            if not path.is_symlink(): yield self.get(category, path.stem)

    def review(self, data):
        key = str(uuid.uuid4())
        data['review']['review_id'] = key
        data['review']['expires_at'] = int(time.time()) + 3600
        with self.lock(): self.put('reviews', key, data)
        return data['review']

    def consume(self, review, scope, binding):
        data = self.get('reviews', review.get('review_id'))
        if data['review'] != review or data['scope'] != scope or data['binding'] != binding:
            raise PermissionError('Import approval belongs to another session, source, destination or connection')
        if review['expires_at'] < time.time(): raise PermissionError('Import review expired; review again')
        return data

    @staticmethod
    def encode(content): return base64.b64encode(content).decode('ascii')

    @staticmethod
    def decode(content): return base64.b64decode(content, validate=True)
