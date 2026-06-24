"""Auth behavior across every router.

The Library Manager has no user-level ACL: a single bearer token (the
``LAMB_API_TOKEN``) protects every endpoint via ``Depends(verify_token)``.
This module asserts the three outcomes that token check produces on a
representative endpoint of each router, plus the one unprotected endpoint
(``GET /health``).

Source: ``backend/dependencies.py`` (``verify_token`` →
``HTTPBearer`` raises 401 "Not authenticated" when the header is absent, and
``verify_token`` raises 401 "Invalid service token." when the token is
wrong) and every router declaring ``dependencies=[Depends(verify_token)]``.
"""

from __future__ import annotations

import pytest
from _helpers import AUTH_HEADERS
from httpx import AsyncClient

_WRONG_HEADERS = {"Authorization": "Bearer wrong-token"}

# One representative protected GET per router. ``library`` is created by the
# fixture so the path resolves before auth would even matter (auth runs first
# regardless). Paths that need no existing resource use a literal id.
_PROTECTED_ENDPOINTS = [
    pytest.param("/libraries/{lib}", id="libraries"),
    pytest.param("/libraries/{lib}/tree", id="folders"),
    pytest.param("/libraries/{lib}/items", id="content"),
    pytest.param("/libraries/{lib}/export", id="importing-and-content-export"),
    pytest.param("/capabilities", id="capabilities"),
    pytest.param("/plugins", id="system-plugins"),
]


@pytest.mark.parametrize("path", _PROTECTED_ENDPOINTS)
async def test_missing_header_returns_401(
    client: AsyncClient, library: dict, path: str
) -> None:
    """No Authorization header on a protected endpoint yields 401 (HTTPBearer)."""
    resp = await client.get(path.format(lib=library["id"]))
    assert resp.status_code == 401, resp.text


@pytest.mark.parametrize("path", _PROTECTED_ENDPOINTS)
async def test_wrong_token_returns_401(
    client: AsyncClient, library: dict, path: str
) -> None:
    """A bearer token that does not match returns 401 (verify_token)."""
    resp = await client.get(path.format(lib=library["id"]), headers=_WRONG_HEADERS)
    assert resp.status_code == 401, resp.text


@pytest.mark.parametrize("path", _PROTECTED_ENDPOINTS)
async def test_correct_token_returns_200(
    client: AsyncClient, library: dict, path: str
) -> None:
    """The correct bearer token passes auth and reaches the handler (200)."""
    resp = await client.get(path.format(lib=library["id"]), headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text


async def test_health_needs_no_auth(client: AsyncClient) -> None:
    """``GET /health`` is the one endpoint reachable without any header."""
    resp = await client.get("/health")
    assert resp.status_code == 200, resp.text


async def test_protected_write_endpoint_missing_header_401(client: AsyncClient) -> None:
    """A protected POST (create library) also rejects a missing header with 401."""
    resp = await client.post("/libraries", json={"id": "x", "organization_id": "o", "name": "n"})
    assert resp.status_code == 401, resp.text


async def test_protected_write_endpoint_wrong_token_401(client: AsyncClient) -> None:
    """A protected POST with a wrong token returns 401, before body validation."""
    resp = await client.post(
        "/libraries",
        headers=_WRONG_HEADERS,
        json={"id": "x", "organization_id": "o", "name": "n"},
    )
    assert resp.status_code == 401, resp.text
