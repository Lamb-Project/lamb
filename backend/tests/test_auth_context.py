"""
Tests for lamb.auth_context — centralized AuthContext manager.

Uses unittest.mock to isolate from the real database and JWT layer.
Run with: pytest backend/tests/test_auth_context.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from lamb.auth_context import AuthContext, _build_auth_context


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_user(
    user_id=1,
    email="user@example.com",
    name="Test User",
    organization_id=10,
    user_type="creator",
    role="user",
):
    """Return a minimal creator_users dict as the DB would."""
    return {
        "id": user_id,
        "email": email,
        "name": name,
        "organization_id": organization_id,
        "user_type": user_type,
        "role": role,
        "user_config": {},
        "enabled": True,
        "lti_user_id": None,
        "auth_provider": "password",
        "password_hash": None,
    }


def _make_organization(
    org_id=10,
    name="Test Org",
    slug="test-org",
    is_system=False,
    features=None,
):
    """Return a minimal organization dict."""
    config = {
        "features": features or {
            "rag_enabled": True,
            "mcp_enabled": True,
            "lti_publishing": True,
            "signup_enabled": False,
            "sharing_enabled": True,
        }
    }
    return {
        "id": org_id,
        "name": name,
        "slug": slug,
        "is_system": is_system,
        "status": "active",
        "config": config,
        "created_at": "2024-01-01",
        "updated_at": "2024-01-01",
    }


def _make_jwt_payload(email="user@example.com", role="user", sub="1"):
    return {"email": email, "role": role, "sub": sub}


def _make_auth_context(
    user=None,
    payload=None,
    org=None,
    org_role="member",
    is_admin=False,
):
    """Build an AuthContext with sensible defaults for testing."""
    user = user or _make_user()
    payload = payload or _make_jwt_payload(email=user["email"], role="admin" if is_admin else "user")
    org = org or _make_organization()
    features = org.get("config", {}).get("features", {})

    return AuthContext(
        user=user,
        token_payload=payload,
        is_system_admin=is_admin,
        organization_role=org_role,
        is_org_admin=org_role in ("owner", "admin"),
        organization=org,
        features=features,
    )


# ---------------------------------------------------------------------------
# Tests: AuthContext construction via _build_auth_context
# ---------------------------------------------------------------------------

class TestBuildAuthContext:
    """Tests for the _build_auth_context internal builder."""

    @patch("lamb.auth_context._db")
    @patch("lamb.auth.decode_token")
    def test_lamb_jwt_success(self, mock_decode, mock_db):
        """LAMB JWT is decoded successfully, user and org loaded."""
        mock_decode.return_value = _make_jwt_payload()
        mock_db.get_creator_user_by_email.return_value = _make_user()
        mock_db.get_organization_by_id.return_value = _make_organization()
        mock_db.get_user_organization_role.return_value = "member"

        ctx = _build_auth_context("valid-token")

        assert ctx is not None
        assert ctx.user["email"] == "user@example.com"
        assert ctx.is_system_admin is False
        assert ctx.organization_role == "member"
        assert ctx.is_org_admin is False
        assert ctx.organization["slug"] == "test-org"
        assert ctx.features.get("rag_enabled") is True

    @patch("lamb.auth_context._db")
    @patch("lamb.auth.decode_token")
    def test_admin_jwt(self, mock_decode, mock_db):
        """Admin role in JWT produces is_system_admin=True."""
        mock_decode.return_value = _make_jwt_payload(role="admin")
        mock_db.get_creator_user_by_email.return_value = _make_user(role="admin")
        mock_db.get_organization_by_id.return_value = _make_organization()
        mock_db.get_user_organization_role.return_value = "owner"

        ctx = _build_auth_context("admin-token")

        assert ctx is not None
        assert ctx.is_system_admin is True
        assert ctx.organization_role == "owner"
        assert ctx.is_org_admin is True

    @patch("lamb.auth_context._db")
    @patch("lamb.auth.decode_token")
    def test_no_email_in_jwt(self, mock_decode, mock_db):
        """JWT without email returns None."""
        mock_decode.return_value = {"role": "user", "sub": "1"}

        ctx = _build_auth_context("bad-token")

        assert ctx is None
        mock_db.get_creator_user_by_email.assert_not_called()

    @patch("lamb.auth_context._db")
    @patch("lamb.auth.decode_token")
    def test_user_not_in_db(self, mock_decode, mock_db):
        """Valid JWT but no matching creator user returns None."""
        mock_decode.return_value = _make_jwt_payload()
        mock_db.get_creator_user_by_email.return_value = None

        ctx = _build_auth_context("valid-token")

        assert ctx is None

    @patch("lamb.auth_context._db")
    @patch("lamb.auth.decode_token")
    def test_owi_fallback(self, mock_decode, mock_db):
        """When LAMB JWT fails, OWI fallback is used."""
        mock_decode.return_value = None  # LAMB JWT fails

        with patch("lamb.owi_bridge.owi_users.OwiUserManager") as MockOwi:
            owi_instance = MockOwi.return_value
            owi_instance.get_user_auth.return_value = {
                "email": "owi@example.com",
                "role": "user",
                "id": "owi-123",
            }
            mock_db.get_creator_user_by_email.return_value = _make_user(email="owi@example.com")
            mock_db.get_organization_by_id.return_value = _make_organization()
            mock_db.get_user_organization_role.return_value = "admin"

            ctx = _build_auth_context("owi-token")

        assert ctx is not None
        assert ctx.user["email"] == "owi@example.com"
        assert ctx.is_org_admin is True

    @patch("lamb.auth_context._db")
    @patch("lamb.auth.decode_token")
    def test_both_auth_fail(self, mock_decode, mock_db):
        """When both LAMB JWT and OWI fail, returns None."""
        mock_decode.return_value = None

        with patch("lamb.owi_bridge.owi_users.OwiUserManager") as MockOwi:
            owi_instance = MockOwi.return_value
            owi_instance.get_user_auth.return_value = None

            ctx = _build_auth_context("garbage-token")

        assert ctx is None

    @patch("lamb.auth_context._db")
    @patch("lamb.auth.decode_token")
    def test_org_config_string_parsed(self, mock_decode, mock_db):
        """Organization config stored as JSON string is correctly parsed."""
        mock_decode.return_value = _make_jwt_payload()
        mock_db.get_creator_user_by_email.return_value = _make_user()

        org = _make_organization()
        org["config"] = json.dumps(org["config"])  # Stored as string
        mock_db.get_organization_by_id.return_value = org
        mock_db.get_user_organization_role.return_value = "member"

        ctx = _build_auth_context("token")

        assert ctx is not None
        assert ctx.features.get("rag_enabled") is True

    @patch("lamb.auth_context._db")
    @patch("lamb.auth.decode_token")
    def test_missing_organization(self, mock_decode, mock_db):
        """User with no organization_id still gets a valid AuthContext."""
        mock_decode.return_value = _make_jwt_payload()
        user = _make_user(organization_id=None)
        mock_db.get_creator_user_by_email.return_value = user

        ctx = _build_auth_context("token")

        assert ctx is not None
        assert ctx.organization == {}
        assert ctx.organization_role is None
        assert ctx.features == {}


# ---------------------------------------------------------------------------
# Tests: Resource access checkers
# ---------------------------------------------------------------------------

class TestResourceAccess:
    """Tests for AuthContext resource access checker methods."""

    def test_assistant_access_owner(self):
        ctx = _make_auth_context()
        with patch.object(type(ctx), "can_access_assistant", wraps=ctx.can_access_assistant):
            with patch("lamb.auth_context._db") as mock_db:
                mock_db.get_assistant_by_id_with_publication.return_value = {
                    "id": 1,
                    "owner": "user@example.com",
                    "organization_id": 10,
                }
                assert ctx.can_access_assistant(1) == "owner"

    def test_assistant_access_system_admin(self):
        ctx = _make_auth_context(is_admin=True)
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.get_assistant_by_id_with_publication.return_value = {
                "id": 1,
                "owner": "other@example.com",
                "organization_id": 99,
            }
            assert ctx.can_access_assistant(1) == "org_admin"

    def test_assistant_access_org_admin(self):
        ctx = _make_auth_context(org_role="admin")
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.get_assistant_by_id_with_publication.return_value = {
                "id": 1,
                "owner": "other@example.com",
                "organization_id": 10,  # Same org
            }
            assert ctx.can_access_assistant(1) == "org_admin"

    def test_assistant_access_shared(self):
        ctx = _make_auth_context(org_role="member")
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.get_assistant_by_id_with_publication.return_value = {
                "id": 1,
                "owner": "other@example.com",
                "organization_id": 99,  # Different org
            }
            mock_db.is_assistant_shared_with_user.return_value = True
            assert ctx.can_access_assistant(1) == "shared"

    def test_assistant_access_same_org(self):
        ctx = _make_auth_context(org_role="member")
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.get_assistant_by_id_with_publication.return_value = {
                "id": 1,
                "owner": "other@example.com",
                "organization_id": 10,  # Same org
            }
            mock_db.is_assistant_shared_with_user.return_value = False
            assert ctx.can_access_assistant(1) == "shared"

    def test_assistant_access_none(self):
        ctx = _make_auth_context(org_role="member")
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.get_assistant_by_id_with_publication.return_value = {
                "id": 1,
                "owner": "other@example.com",
                "organization_id": 99,  # Different org
            }
            mock_db.is_assistant_shared_with_user.return_value = False
            assert ctx.can_access_assistant(1) == "none"

    def test_assistant_not_found(self):
        ctx = _make_auth_context()
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.get_assistant_by_id_with_publication.return_value = None
            assert ctx.can_access_assistant(999) == "none"

    def test_can_modify_assistant_owner(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_assistant", return_value="owner"):
            assert ctx.can_modify_assistant(1) is True

    def test_can_modify_assistant_org_admin_denied(self):
        ctx = _make_auth_context(org_role="admin")
        with patch.object(ctx, "can_access_assistant", return_value="org_admin"):
            # Org admin can access but not modify (only owner or system admin)
            assert ctx.can_modify_assistant(1) is False

    def test_can_modify_assistant_system_admin(self):
        ctx = _make_auth_context(is_admin=True)
        with patch.object(ctx, "can_access_assistant", return_value="org_admin"):
            assert ctx.can_modify_assistant(1) is True

    def test_kb_access_owner(self):
        ctx = _make_auth_context()
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_kb.return_value = (True, "owner")
            assert ctx.can_access_kb("kb-uuid-1") == "owner"

    def test_kb_access_shared(self):
        ctx = _make_auth_context()
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_kb.return_value = (True, "shared")
            assert ctx.can_access_kb("kb-uuid-1") == "shared"

    def test_kb_access_system_admin_fallback(self):
        ctx = _make_auth_context(is_admin=True)
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_kb.return_value = (False, "none")
            assert ctx.can_access_kb("kb-uuid-1") == "owner"

    def test_kb_access_none(self):
        ctx = _make_auth_context()
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_kb.return_value = (False, "none")
            assert ctx.can_access_kb("kb-uuid-1") == "none"


# ---------------------------------------------------------------------------
# Tests: Guard methods
# ---------------------------------------------------------------------------

class TestGuardMethods:
    """Tests for require_* guard methods."""

    def test_require_system_admin_passes(self):
        ctx = _make_auth_context(is_admin=True)
        ctx.require_system_admin()  # Should not raise

    def test_require_system_admin_fails(self):
        ctx = _make_auth_context(is_admin=False)
        with pytest.raises(HTTPException) as exc_info:
            ctx.require_system_admin()
        assert exc_info.value.status_code == 403

    def test_require_org_admin_passes_for_admin(self):
        ctx = _make_auth_context(org_role="admin")
        ctx.require_org_admin()

    def test_require_org_admin_passes_for_owner(self):
        ctx = _make_auth_context(org_role="owner")
        ctx.require_org_admin()

    def test_require_org_admin_passes_for_system_admin(self):
        ctx = _make_auth_context(is_admin=True, org_role="member")
        ctx.require_org_admin()

    def test_require_org_admin_fails_for_member(self):
        ctx = _make_auth_context(org_role="member")
        with pytest.raises(HTTPException) as exc_info:
            ctx.require_org_admin()
        assert exc_info.value.status_code == 403

    def test_require_assistant_access_any(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_assistant", return_value="shared"):
            result = ctx.require_assistant_access(1, level="any")
            assert result == "shared"

    def test_require_assistant_access_none_raises_404(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_assistant", return_value="none"):
            with pytest.raises(HTTPException) as exc_info:
                ctx.require_assistant_access(1)
            assert exc_info.value.status_code == 404

    def test_require_assistant_access_owner_level_denied(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_assistant", return_value="shared"):
            with pytest.raises(HTTPException) as exc_info:
                ctx.require_assistant_access(1, level="owner")
            assert exc_info.value.status_code == 403

    def test_require_assistant_access_owner_level_system_admin_ok(self):
        ctx = _make_auth_context(is_admin=True)
        with patch.object(ctx, "can_access_assistant", return_value="org_admin"):
            result = ctx.require_assistant_access(1, level="owner")
            assert result == "org_admin"

    def test_require_assistant_access_owner_or_admin_denied(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_assistant", return_value="shared"):
            with pytest.raises(HTTPException) as exc_info:
                ctx.require_assistant_access(1, level="owner_or_admin")
            assert exc_info.value.status_code == 403

    def test_require_kb_access_any(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_kb", return_value="shared"):
            result = ctx.require_kb_access("kb-uuid", level="any")
            assert result == "shared"

    def test_require_kb_access_none_raises_404(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_kb", return_value="none"):
            with pytest.raises(HTTPException) as exc_info:
                ctx.require_kb_access("kb-uuid")
            assert exc_info.value.status_code == 404

    def test_require_kb_access_owner_level_denied(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_kb", return_value="shared"):
            with pytest.raises(HTTPException) as exc_info:
                ctx.require_kb_access("kb-uuid", level="owner")
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Tests: to_dict serialization
# ---------------------------------------------------------------------------

class TestToDict:
    """Tests for AuthContext.to_dict() serialization."""

    def test_to_dict_structure(self):
        ctx = _make_auth_context(org_role="admin", is_admin=False)
        d = ctx.to_dict()

        assert "user" in d
        assert "roles" in d
        assert "organization" in d
        assert "features" in d

        assert d["user"]["email"] == "user@example.com"
        assert d["roles"]["is_system_admin"] is False
        assert d["roles"]["organization_role"] == "admin"
        assert d["roles"]["is_org_admin"] is True
        assert d["organization"]["slug"] == "test-org"
        assert d["features"]["sharing_enabled"] is True

    def test_to_dict_is_json_serializable(self):
        ctx = _make_auth_context()
        d = ctx.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
