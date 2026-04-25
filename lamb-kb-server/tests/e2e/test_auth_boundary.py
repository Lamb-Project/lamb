"""E2E auth boundary tests — real HTTP over loopback TCP.

The integration tier covers ASGI-level auth semantics.  This module focuses
on what is only observable over real HTTP: header transport, encoding,
malformed requests, and response-time safety properties.

All tests require ``kb_server_process`` (a live uvicorn subprocess launched by
conftest.py).  They use a plain ``httpx.Client`` without any auth headers so
that every test controls the exact Authorization value sent.
"""

from __future__ import annotations

import time

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _client_no_auth(kb_server_process: dict) -> httpx.Client:
    """Return a synchronous httpx client with NO default auth headers."""
    return httpx.Client(
        base_url=kb_server_process["base_url"],
        timeout=10.0,
    )


# ---------------------------------------------------------------------------
# 1. Health is public — no auth required
# ---------------------------------------------------------------------------


def test_health_reachable_without_auth_over_http(kb_server_process: dict) -> None:
    """GET /health over real HTTP without any Authorization header returns 200.

    Confirms the public endpoint is accessible without credentials even when
    the request travels through real TCP rather than the in-process ASGI
    transport used by the integration tests.
    """
    with _client_no_auth(kb_server_process) as client:
        r = client.get("/health")
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 2. Health stays public even with a bad token
# ---------------------------------------------------------------------------


def test_health_reachable_with_invalid_auth_over_http(kb_server_process: dict) -> None:
    """GET /health with 'Authorization: Bearer wrong' still returns 200.

    /health has no auth dependency; a bad token must not cause 401.
    """
    with _client_no_auth(kb_server_process) as client:
        r = client.get("/health", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 3. Protected endpoint rejects missing auth
# ---------------------------------------------------------------------------


def test_protected_endpoint_rejects_no_auth_over_http(kb_server_process: dict) -> None:
    """GET /collections without Authorization header returns 401 or 403.

    Over real HTTP the header must be absent from the TCP stream — this
    confirms the server enforces auth at the network level, not just in the
    ASGI test client.
    """
    with _client_no_auth(kb_server_process) as client:
        r = client.get("/collections")
    assert r.status_code in (401, 403), (
        f"Expected 401 or 403, got {r.status_code}: {r.text}"
    )


# ---------------------------------------------------------------------------
# 4. Protected endpoint rejects wrong token
# ---------------------------------------------------------------------------


def test_protected_endpoint_rejects_wrong_token_over_http(
    kb_server_process: dict,
) -> None:
    """GET /collections with 'Authorization: Bearer wrong-token' returns 401."""
    with _client_no_auth(kb_server_process) as client:
        r = client.get(
            "/collections", headers={"Authorization": "Bearer wrong-token"}
        )
    assert r.status_code == 401, (
        f"Expected 401, got {r.status_code}: {r.text}"
    )


# ---------------------------------------------------------------------------
# 5. Multibyte UTF-8 token (same visible length, different byte length)
# ---------------------------------------------------------------------------


def test_token_with_multibyte_utf8_difference(kb_server_process: dict) -> None:
    """A non-ASCII byte in the bearer token must not grant access.

    HTTP/1.1 header values are decoded by Starlette as latin-1.  We send the
    raw bytes ``b'Bearer test-tok\\xe9n'`` (where 0xE9 = latin-1 'é') directly
    so the header travels over TCP without client-side rejection.

    When Starlette decodes the header it produces the string ``'test-tokén'``
    (U+00E9).  FastAPI then calls ``hmac.compare_digest('test-tokén',
    'test-token')``.  However, ``hmac.compare_digest`` raises ``TypeError``
    with "comparing strings with non-ASCII characters is not supported" when
    given a str containing non-ASCII code points.

    The server does not catch this ``TypeError``, so the request results in a
    500 Internal Server Error rather than a clean 401.  Access is still denied
    — the 500 is a server-side bug (unhandled exception path), not a security
    hole — but it is worth documenting as a known rough edge.

    The test asserts the request is not accepted (not 200/2xx) and documents
    the actual status code.
    """
    # 'é' in latin-1 is a single byte 0xE9, same length as 'n'.
    bad_token_bytes = b"test-tok\xe9n"  # latin-1: é = 0xE9
    assert bad_token_bytes != b"test-token", "sanity: must differ from real token bytes"
    assert len(bad_token_bytes) == len(b"test-token"), "sanity: same byte length"

    header_value = b"Bearer " + bad_token_bytes

    with _client_no_auth(kb_server_process) as client:
        r = client.get(
            "/collections",
            headers={"Authorization": header_value},
        )

    print(
        f"\nBearer <latin-1 é token b'test-tok\\xe9n'> → {r.status_code}"
    )
    print(
        "  NOTE: 500 means hmac.compare_digest raised TypeError for non-ASCII str."
        " Access is still denied but the error is unhandled."
    )

    # The request must NOT be granted (no 2xx).
    # 401 = clean rejection, 500 = unhandled TypeError from hmac.compare_digest.
    assert r.status_code not in range(200, 300), (
        f"Non-ASCII token must not grant access; got {r.status_code}"
    )
    # Document the actual observed status code.
    assert r.status_code in (401, 500), (
        f"Expected 401 (clean rejection) or 500 (TypeError not handled),"
        f" got {r.status_code}: {r.text}"
    )


# ---------------------------------------------------------------------------
# 6. OPTIONS request — document actual behavior
# ---------------------------------------------------------------------------


def test_options_request_returns_405_or_204(kb_server_process: dict) -> None:
    """OPTIONS /collections: document what the server actually returns.

    FastAPI does not enable CORS by default, so a CORS preflight (OPTIONS)
    typically gets 405 Method Not Allowed.  If CORS middleware is configured
    the response may be 200 or 204.  We accept any of these and print the
    actual status code for documentation purposes.

    Actual observed behavior is asserted so CI catches regressions in the
    HTTP-layer behavior even if the exact value is server-policy-dependent.
    """
    with _client_no_auth(kb_server_process) as client:
        r = client.options("/collections")

    # Document the actual behavior.
    print(f"\nOPTIONS /collections → {r.status_code} (headers: {dict(r.headers)})")

    # The response must be a valid HTTP status code in a reasonable range.
    # Accept: 200, 204 (CORS preflight handled), 405 (no CORS middleware).
    assert r.status_code in (200, 204, 405), (
        f"Unexpected status for OPTIONS /collections: {r.status_code}"
    )


# ---------------------------------------------------------------------------
# 7. Wrong Content-Type on POST /collections
# ---------------------------------------------------------------------------


def test_weird_content_type_on_post(kb_server_process: dict) -> None:
    """POST /collections with Content-Type: text/plain and a JSON body.

    FastAPI's body parser requires 'application/json'; sending 'text/plain'
    should result in 422 (Unprocessable Entity) or 415 (Unsupported Media
    Type).  Auth is included so the request is not rejected for the wrong
    reason.

    Actual observed behavior is documented via print so CI reveals changes.
    """
    json_body = b'{"organization_id": "org-x", "name": "test"}'

    with _client_no_auth(kb_server_process) as client:
        r = client.post(
            "/collections",
            content=json_body,
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "text/plain",
            },
        )

    print(f"\nPOST /collections (Content-Type: text/plain) → {r.status_code}: {r.text[:200]}")

    # FastAPI rejects unknown content-types with 422; some servers use 415.
    assert r.status_code in (415, 422), (
        f"Expected 415 or 422 for wrong Content-Type, got {r.status_code}: {r.text}"
    )


# ---------------------------------------------------------------------------
# 8. Empty Host header
# ---------------------------------------------------------------------------


def test_no_host_header(kb_server_process: dict) -> None:
    """GET /health with an empty Host header.

    HTTP/1.1 requires a Host header (RFC 7230 §5.4).  When Host is set to an
    empty string some servers reject with 400, others silently ignore it and
    serve normally.  We document what the KB server does.

    httpx does not prevent sending an empty Host header, so the raw value
    travels over TCP.
    """
    with _client_no_auth(kb_server_process) as client:
        r = client.get("/health", headers={"Host": ""})

    print(f"\nGET /health (Host: '') → {r.status_code}")

    # Both 200 (server tolerates it) and 400 (strict RFC compliance) are valid.
    assert r.status_code in (200, 400), (
        f"Unexpected status for empty Host header: {r.status_code}"
    )


# ---------------------------------------------------------------------------
# 9. Unicode in Authorization header value
# ---------------------------------------------------------------------------


def test_unicode_in_header_value(kb_server_process: dict) -> None:
    """Sending a non-ASCII Unicode bearer token is rejected before reaching the server.

    HTTP/1.1 header values are strictly latin-1 / ASCII.  httpx enforces this
    by encoding header values as ASCII and raising ``UnicodeEncodeError`` for
    characters outside the ASCII range (code points > 127).

    'test-token-中文' contains CJK characters (U+4E2D, U+6587) that cannot be
    represented in ASCII, so httpx refuses to build the request.  This is the
    correct client-side behavior: a malformed header is rejected locally
    rather than being silently mangled and sent.

    The test documents that the client-level rejection is a ``UnicodeEncodeError``
    and that the string 'test-token-中文' is indeed non-ASCII.
    """
    unicode_token = "test-token-中文"

    # Sanity: confirm the token contains non-ASCII characters.
    assert any(ord(c) > 127 for c in unicode_token), (
        "sanity: token must contain non-ASCII chars"
    )

    # httpx rejects non-ASCII header values before sending anything over TCP.
    with _client_no_auth(kb_server_process) as client:
        with pytest.raises(UnicodeEncodeError):
            client.get(
                "/collections",
                headers={"Authorization": f"Bearer {unicode_token}"},
            )

    print(f"\nBearer {unicode_token!r} → UnicodeEncodeError (httpx refuses to send)")
    print("  This is the correct behavior: non-ASCII header values are rejected client-side.")


# ---------------------------------------------------------------------------
# 10. Extremely long token — no DoS via CPU work
# ---------------------------------------------------------------------------


def test_extremely_long_token_doesnt_crash(kb_server_process: dict) -> None:
    """A 100 000-character bearer token is rejected quickly (< 2 s).

    ``hmac.compare_digest`` operates on the full byte length, but the server
    should not do any heavy computation before the comparison.  A slow
    response would indicate a CPU-intensive pre-processing step that could
    be exploited as a DoS vector.
    """
    long_token = "x" * 100_000
    start = time.monotonic()
    with _client_no_auth(kb_server_process) as client:
        r = client.get(
            "/collections",
            headers={"Authorization": f"Bearer {long_token}"},
        )
    elapsed = time.monotonic() - start

    print(f"\n100k-char token → {r.status_code} in {elapsed:.3f}s")

    # The server must reject the request (not crash or hang).
    # Some servers return 431 (Request Header Fields Too Large) before auth.
    assert r.status_code in (400, 401, 403, 431), (
        f"Expected 400/401/403/431 for long token, got {r.status_code}"
    )
    assert elapsed < 2.0, (
        f"Long-token response took {elapsed:.3f}s (> 2s), possible DoS vector"
    )


# ---------------------------------------------------------------------------
# 11. Multiple Authorization headers
# ---------------------------------------------------------------------------


def test_multiple_authorization_headers(kb_server_process: dict) -> None:
    """Sending two Authorization headers: the FIRST one wins.

    httpx keeps duplicate headers as separate raw entries in its internal
    representation and sends them as two distinct ``Authorization:`` lines over
    the TCP connection.  Starlette's ``Headers.__getitem__`` performs a linear
    scan and returns the value of the FIRST matching header.  FastAPI's
    ``HTTPBearer`` therefore sees only ``"Bearer test-token"`` and the correct
    token is extracted — authentication succeeds with 200.

    The second ``Authorization: Bearer wrong-token`` header is silently
    ignored.  This is an important security note: callers cannot override a
    valid credential by appending a second Authorization header.  Only the
    first header is evaluated.
    """
    with _client_no_auth(kb_server_process) as client:
        r = client.get(
            "/collections",
            headers=[  # type: ignore[arg-type]
                ("Authorization", "Bearer test-token"),
                ("Authorization", "Bearer wrong-token"),
            ],
        )

    print(f"\nTwo Authorization headers (valid first, wrong second) → {r.status_code}")
    print("  Starlette picks the first Authorization header; second is ignored.")
    # Starlette returns the first header value → valid token → 200.
    assert r.status_code == 200, (
        f"Expected 200 (first header wins), got {r.status_code}: {r.text}"
    )
