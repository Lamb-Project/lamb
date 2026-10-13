"""W1 regression tests — workshop token renewal.

A 45–60 minute lesson outlives the 30-minute workshop token, so the wizard
renews it in the background. Two rules matter and are pinned here:

* an *expired* token is reported as ``401 detail="token_expired"`` (a machine
  readable string the frontend acts on), never as a generic "invalid token";
* an expired token can **never** be renewed — renewal requires a still-valid
  one, otherwise the TTL would be meaningless.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException

from lamb import auth as lamb_auth
from lamb.modules.workshop import routers, service


def _token_payload(**overrides):
    payload = {
        "scope": "workshop_student",
        "session_id": "ws-1",
        "activity_id": 1,
        "email": "student@lamb-lti.local",
        "organization_id": 10,
    }
    payload.update(overrides)
    return payload


class TestDecodeTokenEx:
    """decode_token_ex is the new primitive; decode_token keeps its contract."""

    def test_valid_token_has_no_reason(self):
        token = lamb_auth.create_token(_token_payload())
        data, reason = lamb_auth.decode_token_ex(token)
        assert reason is None
        assert data["session_id"] == "ws-1"

    def test_expired_token_reports_expired(self):
        token = lamb_auth.create_token(
            _token_payload(), expires_delta=timedelta(seconds=-10))
        data, reason = lamb_auth.decode_token_ex(token)
        assert data is None
        assert reason == "expired"

    def test_garbage_token_reports_invalid(self):
        data, reason = lamb_auth.decode_token_ex("not-a-jwt")
        assert data is None
        assert reason == "invalid"

    def test_decode_token_still_returns_none_on_expiry(self):
        """Regression: the wrapper keeps the old boolean behaviour."""
        token = lamb_auth.create_token(
            _token_payload(), expires_delta=timedelta(seconds=-10))
        assert lamb_auth.decode_token(token) is None

    def test_decode_token_roundtrip(self):
        token = lamb_auth.create_token(_token_payload())
        assert lamb_auth.decode_token(token)["email"] == "student@lamb-lti.local"

    def test_bad_signature_reports_invalid(self):
        token = jwt.encode(
            {**_token_payload(),
             "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            "another-secret", algorithm="HS256")
        assert lamb_auth.decode_token_ex(token)[1] == "invalid"


class TestExpiredTokenReporting:
    """Every workshop entry point must say *why* it refused the token."""

    def test_principal_raises_token_expired(self):
        with patch("lamb.auth.decode_token", return_value=None), \
             patch("lamb.auth.decode_token_ex", return_value=(None, "expired")):
            with pytest.raises(HTTPException) as exc:
                routers._verify_workshop_principal("ws-1", "tok")
        assert exc.value.status_code == 401
        assert exc.value.detail == "token_expired"

    def test_principal_raises_invalid_for_garbage(self):
        with patch("lamb.auth.decode_token", return_value=None), \
             patch("lamb.auth.decode_token_ex", return_value=(None, "invalid")):
            with pytest.raises(HTTPException) as exc:
                routers._verify_workshop_principal("ws-1", "tok")
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid workshop token"

    def test_consent_decode_raises_token_expired(self):
        with patch("lamb.auth.decode_token", return_value=None), \
             patch("lamb.auth.decode_token_ex", return_value=(None, "expired")):
            with pytest.raises(HTTPException) as exc:
                routers._decode_workshop_student("tok")
        assert exc.value.detail == "token_expired"

    @pytest.mark.asyncio
    async def test_expired_token_gives_token_expired_on_a_route(self):
        token = lamb_auth.create_token(
            _token_payload(), expires_delta=timedelta(seconds=-10))
        with pytest.raises(HTTPException) as exc:
            await routers.get_workshop_session(session_id="ws-1", token=token)
        assert exc.value.status_code == 401
        assert exc.value.detail == "token_expired"


class TestRefreshEndpoint:
    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_refresh_returns_new_token(self, mock_db):
        mock_db.get_workshop_session_by_id.return_value = {"id": "ws-1"}
        token = lamb_auth.create_token(_token_payload())

        result = await routers.refresh_workshop_token(
            session_id="ws-1", token=token)

        assert result["success"] is True
        assert result["expires_in"] == service.workshop_token_ttl()
        assert result["token"] != token

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_refreshed_token_keeps_scope_and_session(self, mock_db):
        mock_db.get_workshop_session_by_id.return_value = {"id": "ws-1"}
        token = lamb_auth.create_token(_token_payload())

        result = await routers.refresh_workshop_token(
            session_id="ws-1", token=token)
        payload = lamb_auth.decode_token(result["token"])

        assert payload["scope"] == "workshop_student"
        assert payload["session_id"] == "ws-1"
        assert payload["email"] == "student@lamb-lti.local"
        assert payload["organization_id"] == 10
        # The renewed token is minted with the workshop TTL, not inherited.
        lifetime = payload["exp"] - payload["iat"]
        assert lifetime <= service.workshop_token_ttl() + 5

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_expired_token_cannot_be_renewed(self, mock_db):
        mock_db.get_workshop_session_by_id.return_value = {"id": "ws-1"}
        token = lamb_auth.create_token(
            _token_payload(), expires_delta=timedelta(seconds=-10))

        with pytest.raises(HTTPException) as exc:
            await routers.refresh_workshop_token(session_id="ws-1", token=token)
        assert exc.value.status_code == 401
        assert exc.value.detail == "token_expired"

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_cross_session_refresh_rejected(self, mock_db):
        mock_db.get_workshop_session_by_id.return_value = {"id": "ws-2"}
        token = lamb_auth.create_token(_token_payload(session_id="ws-1"))

        with pytest.raises(HTTPException) as exc:
            await routers.refresh_workshop_token(session_id="ws-2", token=token)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_missing_session_is_404(self, mock_db):
        mock_db.get_workshop_session_by_id.return_value = None
        token = lamb_auth.create_token(_token_payload())

        with pytest.raises(HTTPException) as exc:
            await routers.refresh_workshop_token(session_id="ws-1", token=token)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    @patch("lamb.modules.workshop.routers._db_manager")
    async def test_non_workshop_scope_rejected(self, mock_db):
        token = lamb_auth.create_token(
            {**_token_payload(), "scope": "lti_unified"})

        with pytest.raises(HTTPException) as exc:
            await routers.refresh_workshop_token(session_id="ws-1", token=token)
        assert exc.value.status_code == 401


class TestTokenTtl:
    def test_default_ttl_is_1800(self):
        assert service.DEFAULT_WORKSHOP_TOKEN_TTL == 1800
        assert service.workshop_token_ttl() == 1800

    def test_env_override(self):
        with patch.dict("os.environ",
                        {"WORKSHOP_TOKEN_TTL_SECONDS": "5400"}):
            assert service.workshop_token_ttl() == 5400

    def test_invalid_env_falls_back(self):
        with patch.dict("os.environ",
                        {"WORKSHOP_TOKEN_TTL_SECONDS": "not-a-number"}):
            assert service.workshop_token_ttl() == 1800
        with patch.dict("os.environ", {"WORKSHOP_TOKEN_TTL_SECONDS": "0"}):
            assert service.workshop_token_ttl() == 1800

    def test_issued_token_uses_configured_ttl(self):
        with patch.dict("os.environ",
                        {"WORKSHOP_TOKEN_TTL_SECONDS": "120"}):
            token = service._create_workshop_token(_token_payload())
        payload = lamb_auth.decode_token(token)
        lifetime = payload["exp"] - payload["iat"]
        assert 100 <= lifetime <= 140
