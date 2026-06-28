"""E2E auth boundary: bad credentials always yield 401, never 500.

Hits the real socket with no header, the wrong token, and deliberately
malformed / non-Latin-1 / garbage tokens. The service must reject them
cleanly (401) and must never crash (500) on a token it cannot parse.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.slow


def test_missing_authorization_header(server) -> None:
    """No Authorization header → 401 on a protected route."""
    with httpx.Client(base_url=server.base_url, timeout=10.0) as c:
        resp = c.get("/plugins")
    assert resp.status_code == 401, resp.text


def test_wrong_bearer_token(server) -> None:
    """A syntactically valid but incorrect bearer token → 401."""
    with server.client(headers={"Authorization": "Bearer wrong-token"}) as c:
        resp = c.get("/plugins")
    assert resp.status_code == 401, resp.text


def test_non_latin1_token_is_401_not_500(server) -> None:
    """A non-Latin-1 token must be rejected (401), never crash the server (500)."""
    # httpx encodes headers as latin-1; pass raw bytes to smuggle non-ASCII
    # through so the server receives a token it cannot compare normally.
    headers = {"Authorization": "Bearer tökén-ñøn-latin".encode()}
    with httpx.Client(base_url=server.base_url, timeout=10.0) as c:
        resp = c.get("/plugins", headers=headers)
    assert resp.status_code == 401, resp.text


def test_garbage_authorization_value_is_401_not_500(server) -> None:
    """A malformed Authorization value (not a Bearer scheme) → 401, not 500."""
    with httpx.Client(base_url=server.base_url, timeout=10.0) as c:
        resp = c.get("/plugins", headers={"Authorization": "@@@garbage@@@"})
    assert resp.status_code == 401, resp.text
    assert resp.status_code != 500
