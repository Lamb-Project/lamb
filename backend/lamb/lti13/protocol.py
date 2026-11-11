"""OIDC login and strict LTIResourceLinkRequest verification.

Unverified JWT contents never select a platform key or change activity state.
The persisted login transaction determines the registration and expected nonce.
"""
import json
import os
import secrets
import threading
import time
from collections import OrderedDict
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

import jwt
from fastapi.responses import HTMLResponse

from . import AGS, CLAIM
from . import network
from .store import Store, digest

_JWKS = OrderedDict()
_LOCK = threading.Lock()
INSTRUCTOR_ROLES = {
    'http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor',
    'http://purl.imsglobal.org/vocab/lis/v2/membership#ContentDeveloper',
    'http://purl.imsglobal.org/vocab/lis/v2/membership#Administrator',
    'http://purl.imsglobal.org/vocab/lis/v2/membership/Instructor#TeachingAssistant',
}
LEARNER_ROLE = 'http://purl.imsglobal.org/vocab/lis/v2/membership#Learner'


def text(value, label, limit=1024, required=True):
    if value is None and not required:
        return ''
    if not isinstance(value, str) or len(value) > limit or (required and not value) or '\x00' in value:
        raise ValueError('Invalid or missing ' + label)
    return value


def target_url():
    from lamb.modules.base import module_public_base
    return network.checked_url(module_public_base() + '/lamb/v1/lti/launch')


def script_page(script, message='Opening your activity…', form_redirect_origin=''):
    # All inserted values are JSON encoded with HTML metacharacters escaped.
    nonce = secrets.token_urlsafe(18)
    return HTMLResponse(
        '<!doctype html><html><head><meta charset="utf-8"><title>LAMB LTI</title></head>'
        '<body><p id="status">' + message + '</p><noscript>Enable JavaScript to open this activity.</noscript>'
        '<script nonce="' + nonce + '">' + script + '</script></body></html>',
        headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                 'Content-Security-Policy': "default-src 'none'; script-src 'nonce-" + nonce + "'; form-action 'self' " + form_redirect_origin + "; base-uri 'none'"})


def js(value):
    return json.dumps(value).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def begin_login(params, store=None):
    store = store or Store()
    issuer = text(params.get('iss'), 'issuer')
    hint = text(params.get('login_hint'), 'login_hint', 4096)
    target = text(params.get('target_link_uri'), 'target_link_uri', 4096)
    if target != target_url():
        raise ValueError('Unexpected LTI launch target')
    client_id = params.get('client_id')
    registrations = [r for r in store.registrations(issuer)
                     if r['enabled'] and (client_id is None or r['client_id'] == client_id)]
    if len(registrations) != 1:
        raise ValueError('Unknown or ambiguous platform/client; supply the registered client_id')
    reg = registrations[0]
    deployment_hint = text(params.get('lti_deployment_id'), 'deployment ID', required=False)
    if deployment_hint and deployment_hint not in reg['deployment_ids']:
        raise ValueError('Unknown LTI deployment')
    message_hint = text(params.get('lti_message_hint'), 'lti_message_hint', 8192, required=False)
    state, nonce, proof = store.new_transaction(reg, target, deployment_hint)
    auth = {'scope': 'openid', 'response_type': 'id_token', 'response_mode': 'form_post',
            'prompt': 'none', 'client_id': reg['client_id'], 'redirect_uri': target,
            'login_hint': hint, 'state': state, 'nonce': nonce}
    if message_hint:
        auth['lti_message_hint'] = message_hint
    parts = urlsplit(reg['authorization_url'])
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in auth]
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query + list(auth.items())), ''))
    # sessionStorage is per origin and tab and works without third-party cookies.
    # A storage denial fails closed and lets the LMS user relaunch in a new window.
    return script_page('try { const key=' + js('lamb-lti13:' + state) + ';'
                       'sessionStorage.setItem(key,' + js(proof) + '); location.replace(' + js(url) + ');'
                       '} catch(e) { document.getElementById("status").textContent='
                       '"Browser storage is unavailable. Open this activity in a new window from your LMS."; }')


def browser_response(id_token, state):
    text(id_token, 'id_token', 65536)
    text(state, 'state', 128)
    # Browsers apply form-action to the final 303 destination too. A repeat chat
    # launch can go directly to the separately hosted, operator-configured OWI.
    import config
    owi = os.getenv('OWI_PUBLIC_BASE_URL') or os.getenv('OWI_BASE_URL') or config.OWI_PUBLIC_BASE_URL
    try:
        redirect_origin = network.origin(owi)
    except ValueError:
        redirect_origin = ''
    # No authentication or resource mutation occurs here. The browser must prove
    # it initiated this exact transaction before the server verifies the ID token.
    return script_page('try { const key=' + js('lamb-lti13:' + state) + ';'
        'const proof=sessionStorage.getItem(key); if(!proof) throw new Error("Missing transaction");'
        'const f=document.createElement("form"); f.method="POST"; f.action=' + js(target_url()) + ';'
        'const fields=' + js({'id_token': id_token, 'state': state}) + '; fields.browser_proof=proof;'
        'for(const [name,value] of Object.entries(fields)){ const i=document.createElement("input");'
        'i.type="hidden"; i.name=name; i.value=value; f.appendChild(i); }'
        'document.body.appendChild(f); sessionStorage.removeItem(key); f.submit();'
        '} catch(e) { document.getElementById("status").textContent='
        '"Login transaction missing. Open the activity again from your LMS in this window."; }',
        form_redirect_origin=redirect_origin)


def platform_key(reg, kid):
    cache_key = (reg['id'], reg['revision'], reg['jwks_url'])
    now = time.monotonic()
    with _LOCK:
        cached = _JWKS.get(cache_key)
    keys = cached[1] if cached and now - cached[0] < 300 else None
    if keys is None or not any(k.get('kid') == kid for k in keys):
        body = network.request('GET', reg['jwks_url'])
        keys = body.get('keys') if isinstance(body, dict) else None
        if not isinstance(keys, list) or not 1 <= len(keys) <= 100 or not all(isinstance(k, dict) for k in keys):
            raise ValueError('Invalid platform JWKS')
        with _LOCK:
            _JWKS[cache_key] = (now, keys)
            while len(_JWKS) > 128:
                _JWKS.popitem(last=False)
    matching = [k for k in keys if k.get('kid') == kid and k.get('kty') == 'RSA'
                and k.get('alg', 'RS256') == 'RS256' and k.get('use', 'sig') == 'sig'
                and ('key_ops' not in k or (isinstance(k['key_ops'], list) and 'verify' in k['key_ops']))]
    if len(matching) != 1:
        raise ValueError('Unknown or ambiguous platform signing key')
    try:
        key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(matching[0]))
        if key.key_size < 2048:
            raise ValueError('Platform RSA key is too small')
        return key
    except (TypeError, KeyError, jwt.PyJWTError) as exc:
        raise ValueError('Invalid platform signing key') from exc


def validate_launch(form, store=None):
    store = store or Store()
    transaction = store.transaction(form.get('state'), form.get('browser_proof'))
    reg = store.registration(transaction['registration_id'])
    if reg['revision'] != transaction['revision']:
        raise ValueError('LTI registration changed; relaunch from the LMS')
    encoded = text(form.get('id_token'), 'id_token', 65536)
    try:
        header = jwt.get_unverified_header(encoded)
        if header.get('alg') != 'RS256' or header.get('crit'):
            raise ValueError('Unsupported signing algorithm or critical header')
        kid = text(header.get('kid'), 'signing key ID', 256)
        claims = jwt.decode(encoded, platform_key(reg, kid), algorithms=['RS256'],
                            audience=reg['client_id'], issuer=reg['issuer'], leeway=30,
                            options={'require': ['iss', 'aud', 'sub', 'iat', 'exp', 'nonce']})
    except (jwt.PyJWTError, TypeError, OverflowError) as exc:
        raise ValueError('Invalid LTI ID token') from exc
    audience = claims['aud']
    if not isinstance(audience, (str, list)) or (isinstance(audience, list) and
            (not audience or not all(isinstance(v, str) for v in audience))):
        raise ValueError('Invalid audience')
    azp = claims.get('azp')
    if ((isinstance(audience, list) and len(audience) > 1 and azp != reg['client_id'])
            or (azp is not None and azp != reg['client_id'])):
        raise ValueError('Wrong authorized party')
    now = time.time()
    if (type(claims['iat']) not in (int, float) or type(claims['exp']) not in (int, float)
            or not now - 630 <= claims['iat'] <= now + 30 or claims['exp'] <= claims['iat']):
        raise ValueError('Invalid or stale ID token timestamps')
    nonce = text(claims['nonce'], 'nonce', 256)
    if not secrets.compare_digest(digest(nonce), transaction['nonce_hash']):
        raise ValueError('LTI nonce mismatch')
    if claims.get(CLAIM + 'message_type') != 'LtiResourceLinkRequest' or claims.get(CLAIM + 'version') != '1.3.0':
        raise ValueError('Unsupported LTI message type or version')
    if claims.get(CLAIM + 'target_link_uri') != transaction['target'] or transaction['target'] != target_url():
        raise ValueError('LTI launch target mismatch')
    deployment = text(claims.get(CLAIM + 'deployment_id'), 'deployment ID')
    store.registration(reg['id'], deployment)
    if transaction['deployment_hint'] and deployment != transaction['deployment_hint']:
        raise ValueError('LTI deployment mismatch')
    subject = text(claims.get('sub'), 'subject', 255)
    resource = claims.get(CLAIM + 'resource_link')
    if not isinstance(resource, dict):
        raise ValueError('Missing resource link')
    resource_id = text(resource.get('id'), 'resource link ID')
    context = claims.get(CLAIM + 'context', {})
    if not isinstance(context, dict):
        raise ValueError('Invalid LTI context')
    context_id = text(context.get('id'), 'context ID', required=False)
    context_title = text(context.get('title'), 'context title', required=False)
    roles = claims.get(CLAIM + 'roles')
    if not isinstance(roles, list) or not roles or not all(isinstance(r, str) and len(r) <= 512 for r in roles):
        raise ValueError('Missing or invalid LTI roles')
    instructor = bool(INSTRUCTOR_ROLES.intersection(roles))
    if not instructor and LEARNER_ROLE not in roles:
        raise ValueError('This LTI role cannot access learning activities')
    email = text(claims.get('email'), 'email', 320, required=False)
    name = text(claims.get('name'), 'name', required=False) or 'LMS user'
    endpoint = claims.get(AGS + 'claim/endpoint', {})
    if not isinstance(endpoint, dict):
        raise ValueError('Invalid grade service claim')
    scopes = endpoint.get('scope', [])
    if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
        raise ValueError('Invalid grade service scopes')
    endpoint = {k: network.service_url(endpoint[k], reg) for k in ('lineitem', 'lineitems') if k in endpoint} | {'scope': scopes}
    # Everything above is read-only. Replay consumption is the first durable write.
    store.consume(transaction)
    user_key = store.object_id(reg['id'], deployment, 'user', subject)
    resource_key = store.object_id(reg['id'], deployment, 'resource', resource_id)
    context_key = store.object_id(reg['id'], deployment, 'context', context_id) if context_id else ''
    return {'resource_link_id': resource_key, 'lms_user_id': user_key, 'username': user_key,
            'lms_email': email, 'display_name': name, 'roles': ','.join(roles),
            'is_instructor': instructor, 'context_id': context_key, 'context_title': context_title,
            'lti_version': '1.3.0', 'registration_id': reg['id'], 'deployment_id': deployment,
            'grade_endpoint': endpoint}
