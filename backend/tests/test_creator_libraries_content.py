"""Tests for the new GET /content and /kb-links routes on library items.

Run with: pytest backend/tests/test_creator_libraries_content.py -v
"""

from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from creator_interface import library_router
from lamb.auth_context import AuthContext, get_auth_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_auth_context(library_access="any"):
    """Build a minimal AuthContext whose can_access_library returns the
    configured value. We bypass the real DB by patching the method."""

    ctx = AuthContext(
        user={"id": 1, "email": "u@e.test", "name": "U", "organization_id": 10,
              "user_type": "creator"},
        token_payload={"email": "u@e.test", "role": "user", "sub": "1"},
        is_system_admin=False,
        organization_role="member",
        is_org_admin=False,
        organization={"id": 10, "name": "Org", "slug": "org", "is_system": False,
                      "status": "active", "config": {}},
        features={},
    )

    def fake_can_access(library_id):  # noqa: ARG001
        return library_access

    ctx.can_access_library = fake_can_access  # type: ignore[method-assign]
    return ctx


@pytest.fixture
def app_with_router():
    """FastAPI app with just the library router mounted, used by every test."""

    app = FastAPI()
    app.include_router(library_router.router, prefix="/creator/libraries")
    return app


@pytest.fixture
def client_factory(app_with_router):
    """Yield a function that builds a TestClient with custom auth + proxy."""

    def _make(auth_ctx, proxy_content):
        def override_auth():
            return auth_ctx

        app_with_router.dependency_overrides[get_auth_context] = override_auth
        library_router._client.proxy_content = proxy_content  # type: ignore[method-assign]
        return TestClient(app_with_router)

    yield _make
    app_with_router.dependency_overrides.clear()


def _proxy_returning(content: bytes, content_type: str = "text/markdown"):
    """Build an async stub that mimics proxy_content's httpx.Response."""

    async def _proxy(library_id, item_id, subpath, creator_user=None):  # noqa: ARG001
        return httpx.Response(
            status_code=200,
            content=content,
            headers={"content-type": content_type},
        )

    return _proxy


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetItemContent:
    """Tests for GET /creator/libraries/{lib}/items/{item}/content."""

    def test_happy_path_markdown(self, client_factory):
        auth = _make_auth_context(library_access="any")
        proxy = _proxy_returning(b"# Hello\n\nbody")
        client = client_factory(auth, proxy)

        resp = client.get("/creator/libraries/L1/items/I1/content")

        assert resp.status_code == 200
        assert resp.text == "# Hello\n\nbody"
        assert resp.headers["content-type"].startswith("text/markdown")

    def test_text_format(self, client_factory):
        auth = _make_auth_context(library_access="any")
        captured = {}

        async def proxy(library_id, item_id, subpath, creator_user=None):  # noqa: ARG001
            captured["subpath"] = subpath
            return httpx.Response(
                status_code=200,
                content=b"plain",
                headers={"content-type": "text/plain"},
            )

        client = client_factory(auth, proxy)
        resp = client.get("/creator/libraries/L1/items/I1/content?format=text")

        assert resp.status_code == 200
        assert resp.text == "plain"
        assert resp.headers["content-type"].startswith("text/plain")
        assert "format=text" in captured["subpath"]

    def test_html_format_rejected_with_422(self, client_factory):
        """HTML format is intentionally blocked at the proxy boundary."""
        auth = _make_auth_context(library_access="any")
        proxy = _proxy_returning(b"<p>x</p>")
        client = client_factory(auth, proxy)

        resp = client.get("/creator/libraries/L1/items/I1/content?format=html")

        assert resp.status_code == 422

    def test_size_cap_returns_413(self, client_factory):
        """Content over MAX_CONTENT_BYTES returns 413."""
        auth = _make_auth_context(library_access="any")
        huge = b"x" * (library_router.MAX_CONTENT_BYTES + 1)
        proxy = _proxy_returning(huge)
        client = client_factory(auth, proxy)

        resp = client.get("/creator/libraries/L1/items/I1/content")

        assert resp.status_code == 413
        assert "exceeds" in resp.json()["detail"].lower()

    def test_no_library_access_returns_404(self, client_factory):
        """If can_access_library returns 'none' the route raises 404."""
        auth = _make_auth_context(library_access="none")
        proxy = _proxy_returning(b"unreachable")
        client = client_factory(auth, proxy)

        resp = client.get("/creator/libraries/L1/items/I1/content")

        assert resp.status_code == 404

    def test_unauthenticated_returns_401_or_403(self, app_with_router):
        """No auth dependency override → real get_auth_context raises 401."""

        async def fail_auth():
            raise HTTPException(status_code=401, detail="missing token")

        app_with_router.dependency_overrides[get_auth_context] = fail_auth
        client = TestClient(app_with_router)

        resp = client.get("/creator/libraries/L1/items/I1/content")

        assert resp.status_code == 401
        app_with_router.dependency_overrides.clear()


class TestGetItemKbLinks:
    """Tests for GET /creator/libraries/{lib}/items/{item}/kb-links."""

    @pytest.fixture(autouse=True)
    def _stub_db(self):
        """Patch _db.get_kb_content_links_for_item per-test."""
        original = library_router._db.get_kb_content_links_for_item
        yield
        library_router._db.get_kb_content_links_for_item = original

    def test_returns_active_blockers(self, app_with_router):
        """Active links are returned as {id, name, status} entries."""
        library_router._db.get_kb_content_links_for_item = lambda _item_id: [
            {
                "knowledge_store_id": "KS-1",
                "knowledge_store_name": "Course Materials",
                "status": "ready",
            },
            {
                "knowledge_store_id": "KS-2",
                "knowledge_store_name": "Notes",
                "status": "processing",
            },
        ]
        app_with_router.dependency_overrides[get_auth_context] = lambda: _make_auth_context(
            library_access="any"
        )
        client = TestClient(app_with_router)

        resp = client.get("/creator/libraries/L1/items/I1/kb-links")

        assert resp.status_code == 200
        body = resp.json()
        assert body["item_id"] == "I1"
        ks_list = body["knowledge_stores"]
        assert len(ks_list) == 2
        assert {k["id"] for k in ks_list} == {"KS-1", "KS-2"}
        assert all({"id", "name", "status"} <= set(k.keys()) for k in ks_list)
        app_with_router.dependency_overrides.clear()

    def test_filters_out_failed_links(self, app_with_router):
        """Failed ingestions don't block deletion, so they're excluded."""
        library_router._db.get_kb_content_links_for_item = lambda _item_id: [
            {"knowledge_store_id": "KS-1", "knowledge_store_name": "Good", "status": "ready"},
            {"knowledge_store_id": "KS-2", "knowledge_store_name": "Bad", "status": "failed"},
        ]
        app_with_router.dependency_overrides[get_auth_context] = lambda: _make_auth_context(
            library_access="any"
        )
        client = TestClient(app_with_router)

        resp = client.get("/creator/libraries/L1/items/I1/kb-links")

        assert resp.status_code == 200
        ids = [k["id"] for k in resp.json()["knowledge_stores"]]
        assert ids == ["KS-1"]
        app_with_router.dependency_overrides.clear()

    def test_empty_when_no_links(self, app_with_router):
        """Returns an empty list when no KS references this item."""
        library_router._db.get_kb_content_links_for_item = lambda _item_id: []
        app_with_router.dependency_overrides[get_auth_context] = lambda: _make_auth_context(
            library_access="any"
        )
        client = TestClient(app_with_router)

        resp = client.get("/creator/libraries/L1/items/I1/kb-links")

        assert resp.status_code == 200
        assert resp.json()["knowledge_stores"] == []
        app_with_router.dependency_overrides.clear()

    def test_no_library_access_returns_404(self, app_with_router):
        """ACL gate runs before the DB lookup."""
        library_router._db.get_kb_content_links_for_item = lambda _item_id: [
            {"knowledge_store_id": "KS-1", "knowledge_store_name": "X", "status": "ready"}
        ]
        app_with_router.dependency_overrides[get_auth_context] = lambda: _make_auth_context(
            library_access="none"
        )
        client = TestClient(app_with_router)

        resp = client.get("/creator/libraries/L1/items/I1/kb-links")

        assert resp.status_code == 404
        app_with_router.dependency_overrides.clear()
