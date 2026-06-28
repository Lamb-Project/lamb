"""Shared fixtures for backend integration tests.

These fixtures build a minimal FastAPI app that mounts only the routers
under test (``library_router`` and ``knowledge_store_router``) so the
heavy ``main.app`` lifespan (DB maintenance loops, news cache loop, OWI
boot) is bypassed. Downstream services (Library Manager, KB Server v2)
and the LAMB DB are stubbed via ``unittest.mock``.

Pattern: each test grabs the ``client`` fixture, then patches the
module-level singletons ``library_router._db``, ``library_router._client``,
``knowledge_store_router._db``, ``knowledge_store_router._client``,
``knowledge_store_router._library_client`` with mocks. The auth dependency
is overridden with a fake ``AuthContext`` whose ACL methods are patched
per test as needed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Make ``backend/`` importable without requiring PYTHONPATH on the CLI.
_BACKEND_ROOT = Path(__file__).parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from lamb.auth_context import AuthContext, get_auth_context  # noqa: E402

DEFAULT_USER = {
    "id": 1,
    "email": "creator@example.com",
    "name": "Creator User",
    "organization_id": 1,
    "user_type": "creator",
    "role": "user",
    "user_config": {},
    "enabled": True,
    "lti_user_id": None,
    "auth_provider": "password",
    "password_hash": None,
}

DEFAULT_ORG = {
    "id": 1,
    "name": "Test Org",
    "slug": "test-org",
    "is_system": False,
    "status": "active",
    "config": {
        "features": {
            "rag_enabled": True,
            "mcp_enabled": True,
            "lti_publishing": True,
            "signup_enabled": False,
            "sharing_enabled": True,
        }
    },
    "created_at": "2024-01-01",
    "updated_at": "2024-01-01",
}


def make_auth_context(
    *,
    user: Optional[Dict[str, Any]] = None,
    org: Optional[Dict[str, Any]] = None,
    is_admin: bool = False,
    org_role: str = "owner",
) -> AuthContext:
    """Construct a real ``AuthContext`` with sensible defaults for tests."""
    user = user or dict(DEFAULT_USER)
    org = org or dict(DEFAULT_ORG)
    features = org.get("config", {}).get("features", {})
    return AuthContext(
        user=user,
        token_payload={"email": user["email"], "role": "admin" if is_admin else "user", "sub": str(user["id"])},
        is_system_admin=is_admin,
        organization_role=org_role,
        is_org_admin=org_role in ("owner", "admin"),
        organization=org,
        features=features,
    )


@pytest.fixture
def auth_ctx() -> AuthContext:
    """The default auth context — owner of org id=1, creator user id=1.

    The resource-access methods (``can_access_library`` /
    ``can_access_knowledge_store``) are patched to return ``"owner"`` by
    default, so tests don't need to wire ``_db.user_can_access_library`` /
    ``user_can_access_knowledge_store`` on the auth_context's own DB
    singleton (which is a different instance from the routers' ``_db``).
    Tests can override per-call via ``monkeypatch.setattr`` if they need a
    different access level.
    """
    ctx = make_auth_context()

    def _can_access_library(_library_id: str) -> str:
        return "owner"

    def _can_access_ks(_ks_id: str) -> str:
        return "owner"

    ctx.can_access_library = _can_access_library  # type: ignore[assignment]
    ctx.can_access_knowledge_store = _can_access_ks  # type: ignore[assignment]
    return ctx


@pytest.fixture
def app(auth_ctx: AuthContext) -> FastAPI:
    """Minimal FastAPI app with only the two routers under test mounted.

    The auth dependency is overridden to return ``auth_ctx`` so tests don't
    need to forge JWTs.
    """
    from creator_interface.library_router import router as library_router
    from creator_interface.knowledge_store_router import router as knowledge_store_router

    application = FastAPI()
    application.include_router(library_router, prefix="/creator/libraries")
    application.include_router(knowledge_store_router, prefix="/creator/knowledge-stores")

    async def _override_auth() -> AuthContext:
        return auth_ctx

    application.dependency_overrides[get_auth_context] = _override_auth
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """``TestClient`` bound to the minimal app with auth pre-overridden."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def lib_db(monkeypatch):
    """Replace ``library_router._db`` with a fresh ``MagicMock`` per test."""
    from creator_interface import library_router as lib_router

    mock_db = MagicMock(name="library_router._db")
    monkeypatch.setattr(lib_router, "_db", mock_db)
    return mock_db


@pytest.fixture
def lib_client(monkeypatch):
    """Replace ``library_router._client`` with an async-compatible MagicMock."""
    from creator_interface import library_router as lib_router

    mock_client = MagicMock(name="library_router._client")
    monkeypatch.setattr(lib_router, "_client", mock_client)
    return mock_client


@pytest.fixture
def ks_db(monkeypatch):
    """Replace ``knowledge_store_router._db`` with a MagicMock per test."""
    from creator_interface import knowledge_store_router as ks_router

    mock_db = MagicMock(name="knowledge_store_router._db")
    monkeypatch.setattr(ks_router, "_db", mock_db)
    return mock_db


@pytest.fixture
def ks_client(monkeypatch):
    """Replace ``knowledge_store_router._client`` with a MagicMock per test."""
    from creator_interface import knowledge_store_router as ks_router

    mock_client = MagicMock(name="knowledge_store_router._client")
    monkeypatch.setattr(ks_router, "_client", mock_client)
    return mock_client


@pytest.fixture
def ks_library_client(monkeypatch):
    """Replace ``knowledge_store_router._library_client`` with a MagicMock."""
    from creator_interface import knowledge_store_router as ks_router

    mock_client = MagicMock(name="knowledge_store_router._library_client")
    monkeypatch.setattr(ks_router, "_library_client", mock_client)
    return mock_client


def _async_return(value):
    """Wrap a value in an awaitable for use as a ``MagicMock`` return."""

    async def _coro(*args, **kwargs):
        return value

    return _coro


def _async_raise(exc):
    """Make a callable that, when awaited, raises ``exc``."""

    async def _coro(*args, **kwargs):
        raise exc

    return _coro


@pytest.fixture
def async_return():
    """Helper to assign coroutine returns to ``MagicMock`` attributes."""
    return _async_return


@pytest.fixture
def async_raise():
    """Helper to assign coroutine-raising callables to ``MagicMock`` attributes."""
    return _async_raise
