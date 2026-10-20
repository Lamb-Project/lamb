"""Owned upload references for AAC. Model-supplied paths never select arbitrary files."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'static' / 'public'
MAX_BYTES = 10 * 1024 * 1024

def owned_file(reference: str, user_id: int) -> Path:
    if not isinstance(reference, str) or not reference or '\\' in reference:
        raise ValueError('Invalid uploaded-file reference')
    relative = Path(reference)
    if relative.is_absolute() or '..' in relative.parts or len(relative.parts) != 2 or relative.parts[0] != str(user_id):
        raise ValueError('File reference must belong to the authenticated user')
    path = ROOT / relative
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.resolve().parent != (ROOT / str(user_id)).resolve():
        raise ValueError('Uploaded file not found or not owned')
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('File exceeds 10 MiB limit')
    return path
