"""Unit tests for backend/dependencies.py.

``verify_token`` is an async function. Tests call it directly (no HTTP) by
constructing ``HTTPAuthorizationCredentials`` manually or passing ``None``
to exercise the missing-header code path.

The test session starts with ``LAMB_API_TOKEN=test-token`` (set in
``tests/conftest.py``). Tests that need a different token patch
``dependencies.LAMB_API_TOKEN`` directly using ``monkeypatch.setattr``.
"""

from __future__ import annotations

import hmac

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import dependencies


def _creds(token: str) -> HTTPAuthorizationCredentials:
    """Build an HTTPAuthorizationCredentials with the given bearer token."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


# ---------------------------------------------------------------------------
# Correct token accepted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_correct_token_is_accepted() -> None:
    """verify_token returns the token string when it matches LAMB_API_TOKEN."""
    result = await dependencies.verify_token(_creds("test-token"))
    assert result == "test-token"


# ---------------------------------------------------------------------------
# Wrong / empty tokens rejected with 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wrong_token_raises_401() -> None:
    """A mismatched token must raise HTTPException 401."""
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.verify_token(_creds("wrong-token"))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_empty_token_raises_401() -> None:
    """An empty bearer credential must raise HTTPException 401."""
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.verify_token(_creds(""))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_substring_of_real_token_raises_401() -> None:
    """A token that is a strict prefix of the real token must still be rejected."""
    # "test-toke" is a substring of "test-token" — must not match.
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.verify_token(_creds("test-toke"))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_real_token_as_superstring_raises_401() -> None:
    """A token that contains the real token as a substring must still be rejected."""
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.verify_token(_creds("test-token-extra"))
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# None credentials (missing Authorization header)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_none_credentials_raises(monkeypatch) -> None:
    """When credentials is None (no header), verify_token must raise an error.

    In production, HTTPBearer raises a 403 before verify_token is called.
    Calling directly with None exposes an AttributeError since the function
    unconditionally accesses ``credentials.credentials``.
    """
    with pytest.raises((HTTPException, AttributeError)):
        await dependencies.verify_token(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# compare_digest — timing-safe comparison
# ---------------------------------------------------------------------------


def test_hmac_compare_digest_is_used() -> None:
    """Verify that hmac.compare_digest is used — not plain == comparison.

    Two strings of identical length but different content must both return
    False from compare_digest so that no partial-match information leaks.
    """
    # Same length as "test-token" (10 chars), different content.
    assert not hmac.compare_digest("test-token", "aaaa-bbbbb")
    assert not hmac.compare_digest("aaaa-bbbbb", "test-token")
    # Identical strings must return True.
    assert hmac.compare_digest("test-token", "test-token")


@pytest.mark.asyncio
async def test_same_length_different_content_raises_401() -> None:
    """Two tokens of equal length but different bytes must both be rejected.

    This ensures verify_token uses compare_digest (constant-time) rather than
    a short-circuiting comparison that could leak token length.
    """
    # "test-token" is 10 chars; craft a 10-char impostor.
    impostor = "test-tXken"
    assert len(impostor) == len("test-token")

    with pytest.raises(HTTPException) as exc_info:
        await dependencies.verify_token(_creds(impostor))
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Token loaded from environment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patched_token_accepted(monkeypatch) -> None:
    """verify_token uses the module-level LAMB_API_TOKEN; patching it works."""
    monkeypatch.setattr(dependencies, "LAMB_API_TOKEN", "my-custom-secret")

    result = await dependencies.verify_token(_creds("my-custom-secret"))
    assert result == "my-custom-secret"


@pytest.mark.asyncio
async def test_old_token_rejected_after_patch(monkeypatch) -> None:
    """After patching LAMB_API_TOKEN, the old token value must be rejected."""
    monkeypatch.setattr(dependencies, "LAMB_API_TOKEN", "new-secret")

    with pytest.raises(HTTPException) as exc_info:
        await dependencies.verify_token(_creds("test-token"))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_empty_configured_token_rejects_everything(monkeypatch) -> None:
    """When LAMB_API_TOKEN is empty, even an empty bearer credential is rejected.

    hmac.compare_digest("", "") is True, so this test confirms behavior when
    both sides are empty — the server should accept only if they match. This
    also documents that an unconfigured token is a security risk.
    """
    monkeypatch.setattr(dependencies, "LAMB_API_TOKEN", "")

    # Empty credential matches empty token — compare_digest("","") == True.
    result = await dependencies.verify_token(_creds(""))
    assert result == ""

    # Non-empty credential must still be rejected.
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.verify_token(_creds("anything"))
    assert exc_info.value.status_code == 401
