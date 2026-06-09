"""Verify ``plugin_params`` flow from the HTTP layer to ``import_content`` kwargs.

Each import-route accepts a ``plugin_params`` dict that mirrors the
plugin's declared parameter schema. The router must forward every key
unchanged so a drop-in plugin's parameters arrive at the plugin without
any router-side knowledge of them.

This contract is what makes the "add a plugin file, no other code
changes" promise hold across the renderer → service → router → worker
chain.
"""

import asyncio
import time
from typing import Any

import pytest
from httpx import AsyncClient
from plugins.base import PluginRegistry

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


async def _wait_for_done(
    client: AsyncClient, lib_id: str, item_id: str, timeout: float = 10.0
) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/libraries/{lib_id}/items/{item_id}/status",
            headers=AUTH_HEADERS,
        )
        status = resp.json()["status"]
        if status in ("ready", "failed"):
            return status
        await asyncio.sleep(0.3)
    return "timeout"


@pytest.mark.asyncio
async def test_url_import_forwards_plugin_params(client: AsyncClient, library: dict, monkeypatch):
    """POST /import/url with plugin_params must reach the plugin's import_content kwargs.

    We monkey-patch ``UrlImportPlugin.import_content`` to capture the kwargs
    it receives, then submit a request with a contrived param dict.
    """
    lib_id = library["id"]
    captured: dict[str, Any] = {}

    plugin = PluginRegistry.get_plugin("url_import")
    assert plugin is not None
    plugin_cls = plugin.__class__
    original = plugin_cls.import_content

    def spy(self, source_path, *, api_keys=None, **kwargs):
        captured.update(kwargs)
        # Return a minimal valid ImportResult so the worker can finish.
        from plugins.base import ImportResult
        return ImportResult(
            full_text="# stub", pages=[], images=[], metadata={}, source_ref={}
        )

    monkeypatch.setattr(plugin_cls, "import_content", spy)

    # All keys are schema-declared params from url_import's get_parameters().
    # The router/worker sanitizes against the plugin's declared schema and
    # drops unknown keys — so the test pins schema-declared keys to confirm
    # the wire format actually delivers them end-to-end.
    custom_params = {
        "limit": 7,
        "max_discovery_depth": 3,
    }
    resp = await client.post(
        f"/libraries/{lib_id}/import/url",
        headers=AUTH_HEADERS,
        json={
            "url": "https://example.com",
            "plugin_name": "url_import",
            "title": "Passthrough Test",
            "plugin_params": custom_params,
        },
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    final = await _wait_for_done(client, lib_id, item_id)
    assert final == "ready", f"worker did not finish: {final}"

    # Every schema-declared key the caller supplied must appear in the
    # plugin's kwargs unchanged.
    for key, value in custom_params.items():
        assert captured.get(key) == value, (
            f"plugin_params['{key}'] did not reach the plugin (got {captured})"
        )

    # Restore — pytest's monkeypatch cleans up, but be explicit anyway.
    monkeypatch.setattr(plugin_cls, "import_content", original)


@pytest.mark.asyncio
async def test_youtube_import_language_via_plugin_params(
    client: AsyncClient, library: dict, monkeypatch
):
    """``plugin_params['language']`` overrides the top-level ``language`` field.

    This is the schema-driven path the UI now uses; the top-level
    ``language`` field is kept only for backward compat. When both are
    sent, ``plugin_params['language']`` wins.
    """
    lib_id = library["id"]
    captured: dict[str, Any] = {}

    plugin = PluginRegistry.get_plugin("youtube_transcript_import")
    assert plugin is not None
    plugin_cls = plugin.__class__

    def spy(self, source_path, *, api_keys=None, **kwargs):
        captured.update(kwargs)
        from plugins.base import ImportResult
        return ImportResult(
            full_text="# stub", pages=[], images=[], metadata={}, source_ref={}
        )

    monkeypatch.setattr(plugin_cls, "import_content", spy)

    resp = await client.post(
        f"/libraries/{lib_id}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://www.youtube.com/watch?v=stub",
            "plugin_name": "youtube_transcript_import",
            "title": "YT Plugin Params Test",
            # Both transports set — plugin_params wins.
            "language": "en",
            "plugin_params": {"language": "fr"},
        },
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    final = await _wait_for_done(client, lib_id, item_id)
    assert final == "ready"
    assert captured.get("language") == "fr"


@pytest.mark.asyncio
async def test_youtube_import_top_level_language_fallback(
    client: AsyncClient, library: dict, monkeypatch
):
    """When ``plugin_params`` omits ``language``, the top-level field fills the gap.

    Preserves backward compat for API clients that haven't migrated to
    sending all knobs via ``plugin_params``.
    """
    lib_id = library["id"]
    captured: dict[str, Any] = {}

    plugin = PluginRegistry.get_plugin("youtube_transcript_import")
    plugin_cls = plugin.__class__

    def spy(self, source_path, *, api_keys=None, **kwargs):
        captured.update(kwargs)
        from plugins.base import ImportResult
        return ImportResult(
            full_text="# stub", pages=[], images=[], metadata={}, source_ref={}
        )

    monkeypatch.setattr(plugin_cls, "import_content", spy)

    resp = await client.post(
        f"/libraries/{lib_id}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://www.youtube.com/watch?v=stub",
            "plugin_name": "youtube_transcript_import",
            "title": "YT Fallback Test",
            "language": "de",
            # No plugin_params at all.
        },
    )
    assert resp.status_code == 202
    item_id = resp.json()["item_id"]

    final = await _wait_for_done(client, lib_id, item_id)
    assert final == "ready"
    assert captured.get("language") == "de"
