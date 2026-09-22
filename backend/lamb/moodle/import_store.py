"""Owner-scoped import receipts, originals and review handles outside /static."""
import base64
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import time
import uuid
from .storage import ensure_private, private_root
from lamb.private_storage import atomic_json, read_json

MAX_OWNER_BYTES = 256 * 1024 * 1024
MAX_RECORDS = 4096
CATEGORIES = frozenset({'reviews', 'receipts', 'versions', 'sessions'})


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
        if category not in CATEGORIES:
            raise ValueError('Unknown import storage category')
        path = ensure_private(self.root / category) / (identity(key) + '.json')
        if path.is_symlink(): raise PermissionError('Unsafe Moodle document storage')
        return path

    def get(self, category, key):
        path = self.path(category, key)
        if not path.is_file(): raise PermissionError('Unknown Moodle document handle')
        return read_json(path, MAX_OWNER_BYTES)

    def put(self, category, key, data):
        path = self.path(category, key)
        payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8', errors='backslashreplace')
        files = [p for category in CATEGORIES for p in ensure_private(self.root / category).glob('*.json')]
        if any(p.is_symlink() for p in files): raise ValueError('Unsafe Moodle document storage')
        if not path.exists() and len(files) >= MAX_RECORDS:
            raise ValueError('Private import record limit reached; inspect private-storage usage and clean expired reviews')
        used = sum(p.stat().st_size for p in files if p != path)
        if used + len(payload) > MAX_OWNER_BYTES:
            raise ValueError('Private Moodle import storage is full; inspect private-storage usage and clean expired reviews')
        atomic_json(path, data)

    def list(self, category):
        if category not in CATEGORIES:
            raise ValueError('Unknown import storage category')
        folder = ensure_private(self.root / category)
        for path in sorted(folder.glob('*.json')):
            if not path.is_symlink(): yield self.get(category, path.stem)

    def review(self, data):
        key = str(uuid.uuid4())
        data['review']['review_id'] = key
        data['review']['expires_at'] = int(time.time()) + 3600
        # Approval binds hashes and metadata. Confirmation fetches and verifies
        # fresh bytes, so persisting an extra binary copy here is unnecessary.
        ticket = {k: v for k, v in data.items() if k not in {'content', 'originals'}}
        with self.lock(): self.put('reviews', key, ticket)
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
