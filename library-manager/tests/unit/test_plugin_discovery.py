"""Unit tests for ``main._discover_plugins`` (zero-touch plugin drop-in).

A fresh ``.py`` file dropped into ``backend/plugins/`` must be picked up
at startup with no code/config edits. We synthesise plugin modules inside
a tmpdir appended to the real package ``__path__`` and assert discovery
self-registers them via the decorators. ``fresh_plugin_registry`` /
``fresh_capability_registry`` guarantee no registration leaks out.
"""

from __future__ import annotations

import sys
import textwrap

import pytest
from main import _discover_plugins

_DROPIN_NAME = "test_unit_dropin_import"

_PLUGIN_SOURCE = textwrap.dedent(
    f"""
    from plugins.base import (
        ImportResult,
        LibraryImportPlugin,
        PluginParameter,
        PluginRegistry,
    )


    @PluginRegistry.register
    class UnitDropinPlugin(LibraryImportPlugin):
        name = "{_DROPIN_NAME}"
        description = "Synthetic plugin used by unit discovery test."
        supported_source_types = ["file"]
        file_extensions = ["xyz"]
        human_label = "Unit drop-in plugin"

        def get_parameters(self):
            return []

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            return ImportResult(full_text="")
    """
).strip()


@pytest.fixture
def plugins_dropin_path(tmp_path, monkeypatch, fresh_plugin_registry):
    """Append a tmpdir onto the real plugins package __path__ for discovery.

    ``fresh_plugin_registry`` already snapshots/restores the registry; this
    fixture only manages the package ``__path__`` and the synthetic modules
    in ``sys.modules`` so the next run is clean.
    """
    import plugins as plugins_pkg  # noqa: PLC0415

    original_paths = list(plugins_pkg.__path__)
    plugins_pkg.__path__.insert(0, str(tmp_path))
    try:
        yield tmp_path
    finally:
        plugins_pkg.__path__[:] = original_paths
        sys.modules.pop(f"plugins.{_DROPIN_NAME}", None)
        sys.modules.pop("plugins.broken_unit_dropin", None)


def test_dropin_plugin_is_auto_discovered(plugins_dropin_path, fresh_plugin_registry):
    """A fresh .py dropped into the plugins folder appears in the registry."""
    (plugins_dropin_path / f"{_DROPIN_NAME}.py").write_text(_PLUGIN_SOURCE, encoding="utf-8")
    assert _DROPIN_NAME not in fresh_plugin_registry._plugins

    _discover_plugins()

    assert _DROPIN_NAME in fresh_plugin_registry._plugins, (
        f"Drop-in not discovered. Registered: {sorted(fresh_plugin_registry._plugins)}"
    )


def test_broken_plugin_does_not_block_discovery(
    plugins_dropin_path, fresh_plugin_registry, caplog
):
    """A plugin with an import error degrades to a warning, never blocks others."""
    (plugins_dropin_path / "broken_unit_dropin.py").write_text(
        "raise RuntimeError('intentional')\n", encoding="utf-8"
    )
    (plugins_dropin_path / f"{_DROPIN_NAME}.py").write_text(_PLUGIN_SOURCE, encoding="utf-8")

    with caplog.at_level("WARNING"):
        _discover_plugins()

    assert _DROPIN_NAME in fresh_plugin_registry._plugins
    assert any(
        "broken_unit_dropin" in (rec.getMessage() or "") for rec in caplog.records
    ), "Expected a warning log mentioning the broken plugin file."


def test_subpackage_modules_are_recursed(
    plugins_dropin_path, fresh_plugin_registry, fresh_capability_registry
):
    """Plugins inside a sub-package (content_handlers/) are also imported."""
    import plugins.content_handlers as ch_pkg  # noqa: PLC0415
    from plugins.content_handlers.capability import CapabilityRegistry  # noqa: PLC0415

    subpkg = plugins_dropin_path / "content_handlers"
    subpkg.mkdir()
    (subpkg / "synthetic_unit_handler.py").write_text(
        textwrap.dedent(
            """
            from pathlib import Path
            from plugins.content_handlers.capability import (
                Capability,
                CapabilityPayload,
                CapabilityRegistry,
                ContentHandler,
            )


            @CapabilityRegistry.register
            class SyntheticUnitAudioHandler(ContentHandler):
                capability = Capability.AUDIO
                description = "Synthetic handler for unit discovery test."

                def get(self, item_path: Path) -> CapabilityPayload:
                    return CapabilityPayload(mime="audio/mpeg", body=b"")
            """
        ).strip(),
        encoding="utf-8",
    )

    original_ch_paths = list(ch_pkg.__path__)
    ch_pkg.__path__.insert(0, str(subpkg))
    try:
        _discover_plugins()
        assert any(
            getattr(h, "__name__", "") == "SyntheticUnitAudioHandler"
            for h in CapabilityRegistry._handlers.values()
        ), "Sub-package plugin was not discovered."
    finally:
        ch_pkg.__path__[:] = original_ch_paths
        sys.modules.pop("plugins.content_handlers.synthetic_unit_handler", None)
