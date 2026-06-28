"""Unit tests for ``backend/dependencies.py`` bearer-token verification."""

from __future__ import annotations

import dependencies
import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials


def _creds(token: str) -> HTTPAuthorizationCredentials:
    """Build a Bearer credentials object carrying ``token``."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestVerifyToken:
    """``verify_token`` accepts the configured token and rejects others."""

    async def test_correct_token_passes(self):
        """A matching token is returned unchanged."""
        result = await dependencies.verify_token(_creds(dependencies.LAMB_API_TOKEN))
        assert result == dependencies.LAMB_API_TOKEN

    async def test_known_token_value(self):
        """The session token (``test-token``) is the one accepted here."""
        # The root conftest sets LAMB_API_TOKEN=test-token before import.
        result = await dependencies.verify_token(_creds("test-token"))
        assert result == "test-token"

    async def test_wrong_token_raises_401(self):
        """A non-matching token raises HTTPException 401."""
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_token(_creds("wrong-token"))
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Invalid service token."

    async def test_empty_token_raises_401(self):
        """An empty credentials string does not match the real token."""
        with pytest.raises(HTTPException) as exc_info:
            await dependencies.verify_token(_creds(""))
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_prefix_of_token_rejected(self):
        """A prefix of the valid token is rejected (compare_digest is exact)."""
        prefix = dependencies.LAMB_API_TOKEN[:-1]
        with pytest.raises(HTTPException):
            await dependencies.verify_token(_creds(prefix))
