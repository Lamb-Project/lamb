"""Bearer-token authentication tests.

Covers FastAPI HTTPBearer edge cases, token comparison behaviour, endpoint
coverage, and the public /health endpoint contract.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Original 4 tests — preserved exactly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_authorization_header(client: AsyncClient) -> None:
    """Missing Authorization header must be rejected."""
    r = await client.get("/collections")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_wrong_token_rejected(client: AsyncClient) -> None:
    r = await client.get(
        "/collections", headers={"Authorization": "Bearer nope"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_malformed_bearer(client: AsyncClient) -> None:
    r = await client.get(
        "/collections", headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_correct_token_accepted(client: AsyncClient) -> None:
    r = await client.get(
        "/collections", headers={"Authorization": "Bearer test-token"}
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_byte_off_token_rejected(client: AsyncClient) -> None:
    """Token with one character different (m vs n at end) must be rejected.

    Exercises the hmac.compare_digest timing-safe comparison path and
    confirms no partial-match leak: even a single byte off returns 401.
    """
    r = await client.get(
        "/collections", headers={"Authorization": "Bearer test-tokem"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_empty_bearer_token_rejected(client: AsyncClient) -> None:
    """'Authorization: Bearer ' (scheme present, credentials absent) → 401/403.

    FastAPI's HTTPBearer rejects the request when credentials are the empty
    string (truthy check on credentials fails → auto_error raises 403).
    """
    r = await client.get(
        "/collections", headers={"Authorization": "Bearer "}
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_bearer_with_leading_trailing_whitespace(client: AsyncClient) -> None:
    """'Bearer  test-token  ' (double space, trailing spaces) is accepted.

    FastAPI's ``get_authorization_scheme_param`` splits on the first space and
    strips surrounding whitespace from the credentials part, so the token
    resolves to 'test-token' and authentication succeeds.
    """
    r = await client.get(
        "/collections",
        headers={"Authorization": "Bearer  test-token  "},
    )
    # The token resolves to the correct value after whitespace stripping.
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_lowercase_bearer_scheme_accepted(client: AsyncClient) -> None:
    """'bearer test-token' (lowercase scheme) must be accepted per RFC 6750.

    HTTPBearer does ``scheme.lower() == "bearer"`` so the scheme comparison
    is case-insensitive.  The token itself is still checked verbatim.
    """
    r = await client.get(
        "/collections",
        headers={"Authorization": "bearer test-token"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_basic_scheme_rejected(client: AsyncClient) -> None:
    """An unrelated Authorization scheme (Basic) is rejected with 401/403.

    HTTPBearer checks ``scheme.lower() != "bearer"`` and raises immediately,
    before any token comparison takes place.
    """
    r = await client.get(
        "/collections", headers={"Authorization": "Basic dGVzdA=="}
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_bearer_with_extra_junk_after_token_rejected(client: AsyncClient) -> None:
    """'Bearer test-token foo' (extra junk after token) is rejected.

    FastAPI's scheme-param splitter takes everything after the first space
    as credentials, so credentials become 'test-token foo', which fails the
    hmac.compare_digest check → 401.
    """
    r = await client.get(
        "/collections",
        headers={"Authorization": "Bearer test-token foo"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Table-driven: every protected endpoint requires auth
# ---------------------------------------------------------------------------

# Each entry: (method, path, body)
# body=None means no JSON payload; we use a minimal payload only to avoid
# 422 errors that would mask the auth check (we want 401/403, not 422).
_PROTECTED_ENDPOINTS = [
    # Collections
    ("GET", "/collections", None),
    (
        "POST",
        "/collections",
        {
            "organization_id": "org-x",
            "name": "test",
            "chunking_strategy": "simple",
            "embedding": {"vendor": "fake", "model": "fake-model"},
            "vector_db_backend": "chromadb",
        },
    ),
    ("GET", "/collections/nonexistent-id", None),
    ("PUT", "/collections/nonexistent-id", {"name": "new-name"}),
    ("DELETE", "/collections/nonexistent-id", None),
    (
        "POST",
        "/collections/nonexistent-id/add-content",
        {
            "documents": [
                {
                    "source_item_id": "s1",
                    "text": "hello",
                    "metadata": {},
                }
            ]
        },
    ),
    ("DELETE", "/collections/nonexistent-id/content/source-123", None),
    (
        "POST",
        "/collections/nonexistent-id/query",
        {"query_text": "hello", "top_k": 3},
    ),
    # Jobs
    ("GET", "/jobs/nonexistent-id", None),
    # System (auth-protected)
    ("GET", "/backends", None),
    ("GET", "/chunking-strategies", None),
    ("GET", "/embedding-vendors", None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", _PROTECTED_ENDPOINTS)
async def test_no_auth_header_returns_401_or_403(
    client: AsyncClient, method: str, path: str, body: dict | None
) -> None:
    """Every protected endpoint rejects a request with no Authorization header."""
    r = await client.request(method, path, json=body)
    assert r.status_code in (401, 403), (
        f"{method} {path} → {r.status_code}: expected 401 or 403 without auth"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", _PROTECTED_ENDPOINTS)
async def test_wrong_token_returns_401(
    client: AsyncClient, method: str, path: str, body: dict | None
) -> None:
    """Every protected endpoint rejects an incorrect bearer token with 401."""
    r = await client.request(
        method,
        path,
        json=body,
        headers={"Authorization": "Bearer definitely-wrong-token"},
    )
    assert r.status_code == 401, (
        f"{method} {path} → {r.status_code}: expected 401 with wrong token"
    )


# ---------------------------------------------------------------------------
# Public /health endpoint contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_public_with_no_auth(client: AsyncClient) -> None:
    """/health returns 200 with no Authorization header at all."""
    r = await client.get("/health")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_health_public_with_invalid_token(client: AsyncClient) -> None:
    """/health returns 200 even when an invalid bearer token is supplied.

    /health has no auth dependency so a bad token should not cause a 401.
    This cross-checks that the endpoint is truly public and does not
    accidentally reject requests that carry a wrong token.
    """
    r = await client.get(
        "/health", headers={"Authorization": "Bearer wrong-token"}
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_health_public_with_basic_scheme(client: AsyncClient) -> None:
    """/health returns 200 even when Authorization uses the Basic scheme.

    Confirms /health carries no HTTPBearer dependency that would reject
    non-Bearer tokens.
    """
    r = await client.get(
        "/health", headers={"Authorization": "Basic dGVzdA=="}
    )
    assert r.status_code == 200
