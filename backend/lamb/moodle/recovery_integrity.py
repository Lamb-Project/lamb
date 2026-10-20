"""Validate retention metadata before allowing deletion of recovery evidence."""
import math
from lamb.private_storage import read_json


def validate_retention(run):
    if not isinstance(run, dict) or not {'expires_at','last_result','working','next_results'} <= run.keys():
        raise ValueError('Incomplete recovery retention metadata')
    expires = run['expires_at']
    if type(expires) not in (int, float) or not math.isfinite(expires) or expires <= 0:
        raise ValueError('Invalid recovery expiry')
    refs = run['next_results']
    if not isinstance(refs, dict):
        raise ValueError('Invalid recovery references')
    if any(value is not None and (not isinstance(value, str) or not value)
           for value in (run['last_result'], run['working'])):
        raise ValueError('Invalid recovery handle')
    if any(not isinstance(value, str) or not value for value in (*refs.keys(), *refs.values())):
        raise ValueError('Invalid recovery mapping')
    return run


def retention_record(path, limit):
    # Unsafe paths / filesystem errors propagate. Only malformed contents are
    # marked unknown. Callers preserve both the original file and all evidence.
    try:
        return validate_retention(read_json(path, limit))
    except (ValueError, KeyError, TypeError, OverflowError):
        return None
