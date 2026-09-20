"""Optional citation lookup for single-file RAG. Standard library only."""
import hashlib
import json
import os
from pathlib import Path


def private_root():
    root = Path(os.getenv('LAMB_DB_PATH', '.')).resolve() / 'moodle'
    public = (Path(__file__).resolve().parents[1] / 'static').resolve()
    if str(root).casefold().startswith(str(public).casefold() + '/') or root == public:
        raise ValueError('Provenance storage must be private')
    return root


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    return hashlib.sha256(value).hexdigest()


def single_provenance(reference, content=None):
    try:
        path = private_root() / 'import-citations' / (digest(reference) + '.json')
        if not path.exists() or any(p.is_symlink() for p in (path, *path.parents)): return {}
        data = json.loads(path.read_text())
        if data['reference'] != reference or (content is not None and data['converted_hash'] != digest(content.encode())):
            return {}
        return data['source'] if isinstance(data['source'], dict) else {}
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        # Provenance is supplementary; a damaged sidecar must not break the
        # owner's otherwise valid single-file assistant.
        return {}

