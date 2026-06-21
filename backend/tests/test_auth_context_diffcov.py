"""
Diff-coverage tests for lamb.auth_context knowledge-store access methods.

Covers can_access_knowledge_store and require_knowledge_store_access
(feature-added lines). Mirrors the construction style of test_auth_context.py.

Run with: pytest backend/tests/test_auth_context_diffcov.py -v
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from lamb.auth_context import AuthContext


# ---------------------------------------------------------------------------
# Helpers (mirrors test_auth_context.py construction style)
# ---------------------------------------------------------------------------

def _make_user(
    user_id=1,
    email="user@example.com",
    name="Test User",
    organization_id=10,
    user_type="creator",
    role="user",
):
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


def _make_organization(org_id=10):
    config = {
        "features": {
            "rag_enabled": True,
            "mcp_enabled": True,
            "lti_publishing": True,
            "signup_enabled": False,
            "sharing_enabled": True,
        }
    }
    return {
        "id": org_id,
        "name": "Test Org",
        "slug": "test-org",
        "is_system": False,
        "status": "active",
        "config": config,
        "created_at": "2024-01-01",
        "updated_at": "2024-01-01",
    }


def _make_auth_context(user=None, org=None, org_role="member", is_admin=False):
    user = user if user is not None else _make_user()
    payload = {"email": user.get("email"), "role": "admin" if is_admin else "user", "sub": "1"}
    org = org if org is not None else _make_organization()
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
# can_access_knowledge_store
# ---------------------------------------------------------------------------

class TestCanAccessKnowledgeStore:
    def test_no_user_id_returns_none(self):
        # Lines 269-271: user has no id
        ctx = _make_auth_context(user=_make_user(user_id=None))
        assert ctx.can_access_knowledge_store("ks-1") == "none"

    def test_db_grants_owner(self):
        # Lines 273-275: db says can_access True with access_type
        ctx = _make_auth_context()
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_knowledge_store.return_value = (True, "owner")
            assert ctx.can_access_knowledge_store("ks-1") == "owner"

    def test_db_grants_shared(self):
        ctx = _make_auth_context()
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_knowledge_store.return_value = (True, "shared")
            assert ctx.can_access_knowledge_store("ks-1") == "shared"

    def test_system_admin_fallback(self):
        # Lines 277-278: system admin gets owner even when db denies
        ctx = _make_auth_context(is_admin=True)
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_knowledge_store.return_value = (False, "none")
            assert ctx.can_access_knowledge_store("ks-1") == "owner"

    def test_org_admin_same_org(self):
        # Lines 280-283: org admin, KS in same org -> owner
        ctx = _make_auth_context(org_role="admin")
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_knowledge_store.return_value = (False, "none")
            mock_db.get_knowledge_store.return_value = {"id": "ks-1", "organization_id": 10}
            assert ctx.can_access_knowledge_store("ks-1") == "owner"

    def test_org_admin_different_org_returns_none(self):
        # Lines 280-283 (false branch) + 285: org admin, KS in other org -> none
        ctx = _make_auth_context(org_role="admin")
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_knowledge_store.return_value = (False, "none")
            mock_db.get_knowledge_store.return_value = {"id": "ks-1", "organization_id": 99}
            assert ctx.can_access_knowledge_store("ks-1") == "none"

    def test_org_admin_missing_entry_returns_none(self):
        # Line 285: org admin, KS not found -> none
        ctx = _make_auth_context(org_role="admin")
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_knowledge_store.return_value = (False, "none")
            mock_db.get_knowledge_store.return_value = None
            assert ctx.can_access_knowledge_store("ks-1") == "none"

    def test_member_denied_returns_none(self):
        # Line 285: plain member, db denies -> none
        ctx = _make_auth_context(org_role="member")
        with patch("lamb.auth_context._db") as mock_db:
            mock_db.user_can_access_knowledge_store.return_value = (False, "none")
            assert ctx.can_access_knowledge_store("ks-1") == "none"


# ---------------------------------------------------------------------------
# require_knowledge_store_access
# ---------------------------------------------------------------------------

class TestRequireKnowledgeStoreAccess:
    def test_any_level_passes(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_knowledge_store", return_value="shared"):
            assert ctx.require_knowledge_store_access("ks-1", level="any") == "shared"

    def test_none_raises_404(self):
        # Lines 300-301
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_knowledge_store", return_value="none"):
            with pytest.raises(HTTPException) as exc_info:
                ctx.require_knowledge_store_access("ks-1")
            assert exc_info.value.status_code == 404

    def test_owner_level_denied_raises_403(self):
        # Lines 303-304
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_knowledge_store", return_value="shared"):
            with pytest.raises(HTTPException) as exc_info:
                ctx.require_knowledge_store_access("ks-1", level="owner")
            assert exc_info.value.status_code == 403

    def test_owner_level_passes(self):
        ctx = _make_auth_context()
        with patch.object(ctx, "can_access_knowledge_store", return_value="owner"):
            assert ctx.require_knowledge_store_access("ks-1", level="owner") == "owner"
