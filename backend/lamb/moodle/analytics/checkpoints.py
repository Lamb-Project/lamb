"""Owner/connection-bound completion checkpoints, not public chart evidence.

The executor must revalidate live course/module scope and source inventories
before resuming. Storage ownership alone does not establish Moodle permission.
"""
from copy import deepcopy
import json
import math
import time
import uuid

from lamb.private_storage import atomic_json, file_lock, read_json
from ..results import TTL_SECONDS

MAX_CHECKPOINT_BYTES = 1024 * 1024
MAX_CHECKPOINTS = 4


class CompletionCheckpoints:
    def __init__(self, results):
        self.folder = results.folder.parent / 'completion-runs'
        self.binding = deepcopy(results.binding)

    def _path(self, identity):
        return self.folder / (str(uuid.UUID(identity)) + '.json')

    def _read(self, identity):
        try:
            value = read_json(self._path(identity), MAX_CHECKPOINT_BYTES)
            expiry = value['expires_at']
            if (type(value['schema_version']) is not int or value['schema_version'] != 1 or value['id'] != str(uuid.UUID(identity)) or
                    value['binding'] != self.binding or type(expiry) not in (int, float) or
                    not math.isfinite(expiry) or expiry <= time.time() or
                    type(value['revision']) is not int or value['revision'] < 0 or
                    not isinstance(value['state'], dict)):
                raise ValueError()
            return value
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            raise PermissionError('Completion checkpoint is unavailable or expired') from None

    def read(self, identity):
        with file_lock(self.folder, blocking=False):
            return self._read(identity)

    def _write(self, value):
        if len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8', errors='backslashreplace')) > MAX_CHECKPOINT_BYTES:
            raise ValueError('Completion checkpoint exceeds its storage limit')
        try:
            atomic_json(self._path(value['id']), value)
        except OSError:
            raise ValueError('Completion checkpoint could not be saved; recover the stored revision') from None

    def create(self, state):
        if not isinstance(state, dict):
            raise ValueError('Invalid completion checkpoint state')
        with file_lock(self.folder, blocking=False):
            entries = list(self.folder.glob('*.json'))
            if any(path.is_symlink() or not path.is_file() for path in entries):
                raise ValueError('Unsafe completion checkpoint storage')
            # Do not evict a recovery handle to admit another task. The owner
            # lifecycle sweep removes expired derived checkpoints separately.
            if len(entries) >= MAX_CHECKPOINTS:
                raise ValueError('Completion checkpoint quota reached; clean expired runs before starting another')
            value = {'schema_version':1, 'id':str(uuid.uuid4()), 'binding':self.binding,
                'expires_at':time.time()+TTL_SECONDS, 'revision':0, 'state':deepcopy(state)}
            self._write(value)
            return deepcopy(value)

    def replace(self, identity, state, *, expected_revision):
        if not isinstance(state, dict) or type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('Invalid completion checkpoint update')
        with file_lock(self.folder, blocking=False):
            value = self._read(identity)
            if value['revision'] != expected_revision:
                raise ValueError('Completion checkpoint advanced; reload before resuming')
            value.update(state=deepcopy(state), revision=value['revision']+1)
            self._write(value)
            return deepcopy(value)
