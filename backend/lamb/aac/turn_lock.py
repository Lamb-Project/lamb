"""Nonblocking session turn locks shared by workers using the same SQLite directory.

The OS releases locks on worker exit. Keep lock files in place: unlinking one
while a worker holds it would let another worker lock a different inode.
"""
import fcntl
import hashlib
from pathlib import Path
import config
from fastapi import HTTPException

LOCK_ROOT = Path(config.LAMB_DB_PATH) / '.aac-turn-locks'

class TurnLock:
    def __init__(self, session_id):
        LOCK_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = hashlib.sha256(session_id.encode()).hexdigest()
        self.file = (LOCK_ROOT / name).open('ab')
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close()
            raise HTTPException(status_code=409, detail='A turn is already running for this AAC session. Wait for it to finish before retrying.')

    def close(self):
        if not self.file.closed:
            fcntl.flock(self.file, fcntl.LOCK_UN)
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
