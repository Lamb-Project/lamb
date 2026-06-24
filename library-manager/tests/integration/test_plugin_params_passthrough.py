"""``plugin_params`` flow from the HTTP wire to ``import_content`` kwargs.

Ported and extended from the old flat
``tests/test_plugin_params_passthrough.py``. The router must forward every
schema-declared key unchanged (the "drop in a plugin, change nothing else"
contract), merge the YouTube top-level ``language`` field into plugin_params,
and the worker must sanitize out unknown / advanced-in-SIMPLIFIED keys before
calling the plugin.

Source under test: ``routers/importing.py`` (param merge),
``services/import_service.py`` (sanitize + dispatch),
``plugins/base.PluginRegistry.sanitize_params``.
"""

from __future__ import annotations

from typing import Any

from _helpers import AUTH_HEADERS, poll_until_ready
from httpx import AsyncClient
from plugins.base import ImportResult, PluginRegistry


def _spy_capturing(captured: dict[str, Any]):
    """Build an ``import_content`` replacement that records its kwargs."""

    def spy(self, source_path, *, api_keys=None, **kwargs):
        captured.update(kwargs)
        return ImportResult(
            full_text="# stub", pages=[], images=[], metadata={}, source_ref={}
        )

    return spy


async def test_url_plugin_params_reach_import_content(
    client: AsyncClient, library: dict, monkeypatch
) -> None:
    """Schema-declared url_import params arrive unchanged at the plugin."""
    lib_id = library["id"]
    captured: dict[str, Any] = {}
    plugin_cls = PluginRegistry.get_plugin("url_import").__class__
    monkeypatch.setattr(plugin_cls, "import_content", _spy_capturing(captured))

    custom = {"limit": 7, "max_discovery_depth": 3}
    resp = await client.post(
        f"/libraries/{lib_id}/import/url",
        headers=AUTH_HEADERS,
        json={
            "url": "https://example.com",
            "plugin_name": "url_import",
            "title": "Passthrough",
            "plugin_params": custom,
        },
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    assert await poll_until_ready(client, lib_id, item_id) == "ready"

    for key, value in custom.items():
        assert captured.get(key) == value, (key, captured)


async def test_youtube_language_from_plugin_params_wins(
    client: AsyncClient, library: dict, monkeypatch
) -> None:
    """plugin_params['language'] overrides the deprecated top-level field."""
    lib_id = library["id"]
    captured: dict[str, Any] = {}
    plugin_cls = PluginRegistry.get_plugin("youtube_transcript_import").__class__
    monkeypatch.setattr(plugin_cls, "import_content", _spy_capturing(captured))

    resp = await client.post(
        f"/libraries/{lib_id}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://www.youtube.com/watch?v=stub",
            "plugin_name": "youtube_transcript_import",
            "title": "YT Params",
            "language": "en",
            "plugin_params": {"language": "fr"},
        },
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    assert await poll_until_ready(client, lib_id, item_id) == "ready"
    assert captured.get("language") == "fr", captured


async def test_youtube_top_level_language_fallback(
    client: AsyncClient, library: dict, monkeypatch
) -> None:
    """When plugin_params omits language, the top-level field fills it in."""
    lib_id = library["id"]
    captured: dict[str, Any] = {}
    plugin_cls = PluginRegistry.get_plugin("youtube_transcript_import").__class__
    monkeypatch.setattr(plugin_cls, "import_content", _spy_capturing(captured))

    resp = await client.post(
        f"/libraries/{lib_id}/import/youtube",
        headers=AUTH_HEADERS,
        json={
            "video_url": "https://www.youtube.com/watch?v=stub",
            "plugin_name": "youtube_transcript_import",
            "title": "YT Fallback",
            "language": "de",
        },
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    assert await poll_until_ready(client, lib_id, item_id) == "ready"
    assert captured.get("language") == "de", captured


async def test_unknown_params_sanitized_out(
    client: AsyncClient, library: dict, monkeypatch
) -> None:
    """Unknown keys never reach the plugin (sanitize_params strips them)."""
    lib_id = library["id"]
    captured: dict[str, Any] = {}
    plugin_cls = PluginRegistry.get_plugin("url_import").__class__
    monkeypatch.setattr(plugin_cls, "import_content", _spy_capturing(captured))

    resp = await client.post(
        f"/libraries/{lib_id}/import/url",
        headers=AUTH_HEADERS,
        json={
            "url": "https://example.com",
            "plugin_name": "url_import",
            "title": "Sanitize",
            "plugin_params": {"limit": 5, "totally_made_up": "evil", "__proto__": 1},
        },
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    assert await poll_until_ready(client, lib_id, item_id) == "ready"

    assert captured.get("limit") == 5, captured
    assert "totally_made_up" not in captured, captured
    assert "__proto__" not in captured, captured


async def test_simplified_mode_drops_advanced_params(
    client: AsyncClient, library: dict, monkeypatch
) -> None:
    """In SIMPLIFIED mode, advanced params are stripped before the plugin call.

    ``url_import``'s ``limit`` is an *advanced* param; ``max_discovery_depth``
    is not. With governance set to SIMPLIFIED the advanced one must not reach
    the plugin while the non-advanced one still does.
    """
    lib_id = library["id"]
    captured: dict[str, Any] = {}
    plugin_cls = PluginRegistry.get_plugin("url_import").__class__
    monkeypatch.setattr(plugin_cls, "import_content", _spy_capturing(captured))
    # sanitize_params reads PLUGIN_<NAME> from the environment at call time.
    monkeypatch.setenv("PLUGIN_URL_IMPORT", "SIMPLIFIED")

    resp = await client.post(
        f"/libraries/{lib_id}/import/url",
        headers=AUTH_HEADERS,
        json={
            "url": "https://example.com",
            "plugin_name": "url_import",
            "title": "Simplified",
            "plugin_params": {"limit": 9, "max_discovery_depth": 4},
        },
    )
    assert resp.status_code == 202, resp.text
    item_id = resp.json()["item_id"]
    assert await poll_until_ready(client, lib_id, item_id) == "ready"

    assert captured.get("max_discovery_depth") == 4, captured
    assert "limit" not in captured, captured
