"""Auto-discovery regression test for library-manager plugins.

The product thesis is **zero-touch plugin drop-in**: a fresh ``.py`` file
in ``backend/plugins/`` must be picked up at startup with no code edits
and no config edits. This test exercises ``_discover_plugins`` against a
synthetic plugin module placed inside a tmpdir and confirms the module
self-registered via ``@PluginRegistry.register``.

Pattern:
    1. Create a tmpdir laid out as a Python package mirror of the real
       ``plugins/`` package (``plugins/__init__.py`` + a fresh module).
    2. ``monkeypatch.syspath_prepend`` so ``import plugins`` resolves there.
    3. Pop ``plugins`` (and any subpackage) out of ``sys.modules`` so the
       new path is used on next import.
    4. Call the production ``_discover_plugins`` helper.
    5. Assert the synthetic plugin name is in ``PluginRegistry``.
    6. Cleanup: restore the original ``plugins`` package on teardown so
       subsequent tests don't see the synthetic plugin.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from main import _discover_plugins
from plugins.base import PluginRegistry

_DROPIN_NAME = "test_dropin_import_h"


_PLUGIN_SOURCE = textwrap.dedent(
    f"""
    from plugins.base import (
        ImportResult,
        LibraryImportPlugin,
        PluginParameter,
        PluginRegistry,
    )


    @PluginRegistry.register
    class TestDropinPlugin(LibraryImportPlugin):
        name = "{_DROPIN_NAME}"
        description = "Synthetic plugin used by test_plugin_discovery."
        supported_source_types = ["file"]
        file_extensions = ["xyz"]
        human_label = "Drop-in plugin for discovery test"

        def get_parameters(self):
            return []

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            return ImportResult(full_text="")
    """
).strip()


@pytest.fixture
def isolate_plugins_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Mirror the real plugins package into a tmpdir and shadow it on sys.path.

    Copying every module is overkill for this test — instead we re-export
    the real package by re-using its filesystem path AND adding the tmpdir
    onto its ``__path__``. That way the real registry survives, AND
    ``pkgutil.iter_modules`` picks up our synthetic module on the next scan.
    """
    import plugins as plugins_pkg  # noqa: PLC0415

    # Snapshot for teardown.
    original_paths = list(plugins_pkg.__path__)
    original_registry = dict(PluginRegistry._plugins)

    plugins_pkg.__path__.insert(0, str(tmp_path))

    yield tmp_path

    # Restore __path__ exactly as we found it.
    plugins_pkg.__path__[:] = original_paths
    # Restore registry exactly as we found it (drop synthetic plugin).
    PluginRegistry._plugins.clear()
    PluginRegistry._plugins.update(original_registry)
    # Forget our synthetic module so it is GC'd and a re-run is clean.
    sys.modules.pop(f"plugins.{_DROPIN_NAME}", None)


def test_dropin_plugin_is_auto_discovered(isolate_plugins_package: Path) -> None:
    """A fresh .py dropped into the plugins folder appears in the registry."""
    plugin_file = isolate_plugins_package / f"{_DROPIN_NAME}.py"
    plugin_file.write_text(_PLUGIN_SOURCE, encoding="utf-8")

    # Sanity: not already registered before discovery.
    assert _DROPIN_NAME not in PluginRegistry._plugins

    _discover_plugins()

    assert _DROPIN_NAME in PluginRegistry._plugins, (
        "Drop-in plugin was not picked up by _discover_plugins. "
        f"Registered: {sorted(PluginRegistry._plugins)}"
    )


def test_broken_plugin_does_not_block_discovery(
    isolate_plugins_package: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A plugin with a syntax/import error must not break other plugins.

    The discovery helper wraps every ``importlib.import_module`` in a
    try/except so a single broken file degrades to a warning, never a
    startup failure. We prove that by dropping in TWO files — one broken,
    one valid — and asserting the valid one still registers.
    """
    broken = isolate_plugins_package / "broken_test_dropin.py"
    broken.write_text("raise RuntimeError('intentional')\n", encoding="utf-8")

    valid = isolate_plugins_package / f"{_DROPIN_NAME}.py"
    valid.write_text(_PLUGIN_SOURCE, encoding="utf-8")

    with caplog.at_level("WARNING"):
        _discover_plugins()

    assert _DROPIN_NAME in PluginRegistry._plugins
    # Some logger message should reference the broken module name.
    assert any("broken_test_dropin" in (rec.getMessage() or "") for rec in caplog.records), (
        "Expected a warning log mentioning the broken plugin file."
    )


def test_subpackage_modules_are_recursed(
    isolate_plugins_package: Path,
) -> None:
    """Plugins inside a sub-package (e.g. content_handlers/) are also imported.

    The capability plugins live under ``plugins/content_handlers/`` and
    must keep working. This drops a fresh module into a sub-folder and
    asserts ``_discover_plugins`` recurses into it.
    """
    from plugins.content_handlers.capability import CapabilityRegistry  # noqa: PLC0415

    snapshot = dict(CapabilityRegistry._handlers)

    subpkg = isolate_plugins_package / "content_handlers"
    subpkg.mkdir()
    # We mirror the real sub-package by giving it an __init__ that imports
    # the real one — but the cleanest approach is just to extend the real
    # sub-package's __path__ in the same way as the parent.
    import plugins.content_handlers as ch_pkg  # noqa: PLC0415

    original_ch_paths = list(ch_pkg.__path__)
    ch_pkg.__path__.insert(0, str(subpkg))

    synthetic = subpkg / "synthetic_handler_h.py"
    synthetic.write_text(
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
            class SyntheticAudioHandler(ContentHandler):
                capability = Capability.AUDIO
                description = "Synthetic handler for discovery test."

                def get(self, item_path: Path) -> CapabilityPayload:
                    return CapabilityPayload(mime="audio/mpeg", body=b"")
            """
        ).strip(),
        encoding="utf-8",
    )

    try:
        _discover_plugins()
        assert any(
            getattr(h, "__name__", "") == "SyntheticAudioHandler"
            for h in CapabilityRegistry._handlers.values()
        ), "Sub-package plugin was not discovered."
    finally:
        ch_pkg.__path__[:] = original_ch_paths
        CapabilityRegistry._handlers.clear()
        CapabilityRegistry._handlers.update(snapshot)
        sys.modules.pop("plugins.content_handlers.synthetic_handler_h", None)
