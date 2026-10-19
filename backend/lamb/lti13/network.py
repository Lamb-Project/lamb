"""Bounded HTTPS requests to explicitly registered platform endpoints only."""
import json
import os
import ssl
from urllib.parse import urlsplit

import httpx

MAX_RESPONSE = 1024 * 1024


def checked_url(value):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 33 for c in value):
        raise ValueError('Invalid platform URL')
    parts = urlsplit(value)
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.fragment or '\\' in value):
        raise ValueError('Platform endpoints must be absolute HTTPS URLs without credentials or fragments')
    # Accessing port rejects malformed/out-of-range values.
    _ = parts.port
    return value


def origin(value):
    parts = urlsplit(checked_url(value))
    host = parts.hostname.lower()
    if ':' in host:
        host = '[' + host + ']'
    return 'https://' + host + (':' + str(parts.port) if parts.port and parts.port != 443 else '')


def service_url(value, registration):
    checked_url(value)
    if origin(value) not in registration['service_origins']:
        raise ValueError('Grade service URL is outside the registered platform origins')
    return value


def request(method, url, *, headers=None, data=None, payload=None):
    checked_url(url)
    ca = os.getenv('LTI13_CA_BUNDLE')
    tls = ssl.create_default_context(cafile=ca) if ca else True
    try:
        with httpx.Client(timeout=10, verify=tls, follow_redirects=False, trust_env=False) as client:
            with client.stream(method, url, headers=headers, data=data, json=payload) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    # Never include response bodies (potential credentials) or Authorization headers.
                    raise ValueError(f'Platform service returned HTTP {response.status_code}')
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE:
                        raise ValueError('Platform response exceeds size limit')
                    chunks.append(chunk)
                body = b''.join(chunks)
                return json.loads(body) if body.strip() else {}
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise ValueError('Platform service unavailable or returned invalid JSON') from exc
