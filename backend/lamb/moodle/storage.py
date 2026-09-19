"""Private persistent Moodle data. Never put derived course data under /static."""
import os
import shutil
from pathlib import Path


def private_root():
    root = Path(os.environ.get('LAMB_DB_PATH', '.')).resolve() / 'moodle'
    public = (Path(__file__).resolve().parents[2] / 'static').resolve()
    if root == public or public in root.parents:
        from .policy import MoodleConfigurationError
        raise MoodleConfigurationError('LAMB_DB_PATH must be outside the static file directory')
    return root


def ensure_private(root):
    root = Path(root)
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Unsafe Moodle storage path')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    return root


def migrate_legacy_cache(legacy=None, target=None):
    """Archive the rebuildable legacy cache outside static; do not trust it as fresh.

    Run before serving requests. Copy/verify before removing the old location, so
    an interrupted cross-volume migration can be retried. The original bytes are
    retained in a private archive for rollback, never republished under static.
    """
    legacy = Path(legacy) if legacy is not None else Path(__file__).resolve().parents[2] / 'static/public/.moodle'
    if not legacy.exists():
        return
    root = ensure_private(target if target is not None else private_root())
    import fcntl
    fd = os.open(root / '.migration.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not legacy.exists():
            return
        paths = [legacy, *legacy.rglob('*')]
        if any(p.is_symlink() for p in paths):
            raise ValueError('Legacy Moodle cache contains a symlink; migration requires administrator review')
        archive = root / 'legacy-cache-archive'
        ensure_private(archive)
        for source in paths[1:]:
            dest = archive / source.relative_to(legacy)
            if source.is_dir():
                ensure_private(dest)
            elif source.is_file():
                ensure_private(dest.parent)
                if dest.is_symlink():
                    raise ValueError('Unsafe Moodle archive path')
                if dest.exists() and dest.read_bytes() != source.read_bytes():
                    raise ValueError('Legacy Moodle archive conflict; original retained')
                if not dest.exists():
                    with dest.open('xb') as out:
                        out.write(source.read_bytes())
                        out.flush()
                        os.fsync(out.fileno())
                    dest.chmod(0o600)
                if dest.read_bytes() != source.read_bytes():
                    raise ValueError('Moodle archive verification failed; original retained')
        for folder in [p for p in archive.rglob('*') if p.is_dir()] + [archive, root]:
            directory_fd = os.open(folder, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        shutil.rmtree(legacy)
