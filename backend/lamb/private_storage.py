"""Shared private-file lifecycle primitives. No authored resources are managed here."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile


def private_directory(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unsafe private storage path')
    public = (Path(__file__).resolve().parents[1] / 'static').resolve()
    resolved = path.resolve()
    if str(resolved).casefold() == str(public).casefold() or str(resolved).casefold().startswith(str(public).casefold() + '/'):
        raise ValueError('Private storage must be outside static')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def data_root():
    """Require a stable configured root; never silently put source data in cwd."""
    value = os.environ.get('LAMB_DB_PATH', '')
    if not value or not Path(value).is_absolute():
        raise ValueError('Set LAMB_DB_PATH to an absolute private persistent directory')
    return private_directory(value)


@contextmanager
def file_lock(folder, *, blocking=True):
    folder = private_directory(folder)
    fd = os.open(folder / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            raise ValueError('Private storage is busy; retry after the current operation finishes') from None
        yield


def atomic_json(path, value):
    """Caller holds the store lock. Replace only after a complete durable write."""
    path = Path(path)
    private_directory(path.parent)
    if path.is_symlink():
        raise ValueError('Unsafe private storage file')
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8', errors='backslashreplace'))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sync_directory(folder):
    fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_json(path, limit):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Private storage file exceeds its limit')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Invalid private storage record')
    return value
