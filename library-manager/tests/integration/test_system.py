"""System endpoints: health check and plugin listing.

Ports ``tests/test_system.py`` into the integration tier. ``GET /health``
reports component health (database + worker) and needs no auth; ``GET
/plugins`` lists every registered import plugin in the documented shape.

Source: ``backend/routers/system.py``.
"""

from __future__ import annotations

from _helpers import AUTH_HEADERS
from httpx import AsyncClient

# Plugins discovered at session start (root conftest calls _discover_plugins).
_EXPECTED_PLUGINS = {
    "simple_import",
    "markitdown_import",
    "markitdown_plus_import",
    "url_import",
    "youtube_transcript_import",
}


async def test_health_ok_with_worker_running(client: AsyncClient) -> None:
    """With the worker running, /health reports status ok and both checks ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok", data
    assert data["service"] == "library-manager"
    assert data["version"] == "1.0.0"
    assert data["checks"] == {"database": "ok", "worker": "ok"}


async def test_health_degraded_without_worker(client_no_worker: AsyncClient) -> None:
    """Without the worker the DB is still ok but status degrades."""
    resp = await client_no_worker.get("/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "degraded", data
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["worker"] == "error"


async def test_list_plugins_lists_registered(client: AsyncClient) -> None:
    """/plugins returns all registered import plugins."""
    resp = await client.get("/plugins", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    plugins = resp.json()["plugins"]
    names = {p["name"] for p in plugins}
    assert _EXPECTED_PLUGINS.issubset(names), names


async def test_plugin_shape(client: AsyncClient) -> None:
    """Each plugin entry carries name, description, source types, and parameters."""
    resp = await client.get("/plugins", headers=AUTH_HEADERS)
    assert resp.status_code == 200, resp.text
    for plugin in resp.json()["plugins"]:
        assert isinstance(plugin["name"], str) and plugin["name"]
        assert "description" in plugin
        assert isinstance(plugin["supported_source_types"], list)
        assert isinstance(plugin["parameters"], list)
