"""Nonblocking session turn locks shared by workers using the same SQLite directory.

The OS releases locks on worker exit. Keep lock files in place: unlinking one
while a worker holds it would let another worker lock a different inode.
"""
import fcntl
import hashlib
import os
import threading
from pathlib import Path
import config
from fastapi import HTTPException

LOCK_ROOT = Path(config.LAMB_DB_PATH) / '.aac-turn-locks'

_guard = threading.Lock()
_active = set()

def _busy():
    return HTTPException(status_code=409, detail='A turn is already running for this AAC session. Wait for it to finish before retrying.')

class TurnLock:
    def __init__(self, session_id):
        LOCK_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = hashlib.sha256(session_id.encode()).hexdigest()
        # Some mounted filesystems treat flock as process-scoped. Reserve the
        # session locally as well as across workers; neither guard alone suffices.
        self.key = (os.getpid(), str(LOCK_ROOT.resolve()), name)
        self.file = None
        self.closed = False
        with _guard:
            if self.key in _active:
                raise _busy()
            _active.add(self.key)
        try:
            self.file = (LOCK_ROOT / name).open('ab')
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as error:
            if self.file is not None:
                self.file.close()
            with _guard:
                _active.discard(self.key)
            if isinstance(error, BlockingIOError):
                raise _busy() from error
            raise

    def close(self):
        with _guard:
            if self.closed:
                return
            self.closed = True
            try:
                try:
                    fcntl.flock(self.file, fcntl.LOCK_UN)
                finally:
                    self.file.close()
            finally:
                _active.discard(self.key)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
