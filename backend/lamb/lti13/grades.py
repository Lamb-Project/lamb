"""AGS score return for validated launches, with scoped client-assertion tokens."""
import math
import secrets
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from . import SCORE_SCOPE
from . import network
from .keys import KeyRing
from .store import Store

_TOKENS = OrderedDict()
_LOCK = threading.Lock()


def access_token(registration, scopes, store=None):
    store = store or Store()
    reg = store.registration(registration['id'])
    if reg['revision'] != registration['revision']:
        raise ValueError('LTI registration changed; retry grade return')
    key = (reg['id'], reg['revision'], tuple(sorted(scopes)))
    with _LOCK:
        cached = _TOKENS.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    now = int(time.time())
    assertion = KeyRing().sign({'iss': reg['client_id'], 'sub': reg['client_id'],
                               'aud': reg['token_url'], 'iat': now, 'exp': now + 60,
                               'jti': secrets.token_urlsafe(32)})
    response = network.request('POST', reg['token_url'], data={
        'grant_type': 'client_credentials', 'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
        'client_assertion': assertion, 'scope': ' '.join(sorted(scopes))})
    if not isinstance(response, dict):
        raise ValueError('Invalid OAuth token response')
    token = response.get('access_token')
    token_type = response.get('token_type')
    if (not isinstance(token, str) or not token or len(token) > 32768
            or not isinstance(token_type, str) or token_type.lower() != 'bearer'):
        raise ValueError('Invalid OAuth token response')
    granted = response.get('scope', ' '.join(scopes))
    if not isinstance(granted, str) or not set(scopes).issubset(granted.split()):
        raise ValueError('Platform did not grant the required grade scope')
    expiry = response.get('expires_in', 0)
    if type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= 0:
        raise ValueError('Invalid OAuth token expiry')
    with _LOCK:
        _TOKENS[key] = (time.monotonic() + max(0, min(expiry, 3600) - 30), token)
        while len(_TOKENS) > 128:
            _TOKENS.popitem(last=False)
    return token


def send_score(resource_id, student_email, score, comment='', store=None):
    store = store or Store()
    try:
        reg, subject, endpoint = store.grade_target(resource_id, student_email)
        if SCORE_SCOPE not in endpoint.get('scope', []):
            raise ValueError('The LMS did not grant AGS score permission; enable grades and relaunch')
        if not endpoint.get('lineitem'):
            raise ValueError('The LMS supplied no grade column; configure grades and relaunch')
        lineitem = network.service_url(endpoint['lineitem'], reg)
        parts = urlsplit(lineitem)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/') + '/scores', parts.query, ''))
        value = float(score)
        if not math.isfinite(value) or not 0 <= value <= 10:
            raise ValueError('File evaluation grades must be between 0 and 10')
        token = access_token(reg, {SCORE_SCOPE}, store)
        network.request('POST', url,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/vnd.ims.lis.v1.score+json'},
            payload={'userId': subject, 'scoreGiven': value, 'scoreMaximum': 10,
                     'comment': comment, 'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                     'activityProgress': 'Completed', 'gradingProgress': 'FullyGraded'})
        return {'success': True, 'status_code': 200}
    except (ValueError, TypeError) as exc:
        return {'success': False, 'status_code': None, 'error_message': str(exc)}
