"""Tests for system endpoints: health check, auth, and plugin listing."""

import pytest
from httpx import AsyncClient

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
async def test_health_no_auth(client: AsyncClient):
    """Health endpoint should respond without authentication and show component health."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["service"] == "library-manager"
    assert "checks" in data
    assert data["checks"]["database"] == "ok"


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client: AsyncClient):
    """Protected endpoints should reject requests without a valid token."""
    resp = await client.get("/plugins")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_wrong_token_rejected(client: AsyncClient):
    """Protected endpoints should reject requests with a wrong token."""
    resp = await client.get(
        "/plugins",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_plugins(client: AsyncClient):
    """Plugin listing should return all registered import plugins."""
    resp = await client.get("/plugins", headers=AUTH_HEADERS)
    assert resp.status_code == 200

    data = resp.json()
    plugins = data["plugins"]
    names = {p["name"] for p in plugins}

    assert "simple_import" in names
    assert "markitdown_import" in names
    assert "markitdown_plus_import" in names
    assert "url_import" in names
    assert "youtube_transcript_import" in names

    # Each plugin should have required fields.
    for plugin in plugins:
        assert "name" in plugin
        assert "description" in plugin
        assert "supported_source_types" in plugin
        assert "parameters" in plugin
