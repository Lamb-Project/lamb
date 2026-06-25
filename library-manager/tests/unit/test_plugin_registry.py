"""Unit tests for ``plugins.base``: dataclasses and ``PluginRegistry``.

These exercise the registry classmethods directly (no FastAPI, no HTTP)
and use the ``fresh_plugin_registry`` fixture to snapshot/restore the
class-level ``_plugins`` dict so no registration leaks into other tests.
"""

from __future__ import annotations

import pytest
from plugins.base import (
    ExtractedImage,
    ImportResult,
    LibraryImportPlugin,
    PageContent,
    PluginParameter,
)


def _make_plugin_cls(
    plugin_name: str,
    *,
    parameters: list[PluginParameter] | None = None,
    source_types: set[str] | None = None,
    extensions: list[str] | None = None,
    capabilities: list | None = None,
    label: str = "",
    desc: str = "A throwaway plugin",
    keys: list[str] | None = None,
):
    """Build a concrete throwaway ``LibraryImportPlugin`` subclass for tests."""
    params = parameters or []

    class _Throwaway(LibraryImportPlugin):
        name = plugin_name
        description = desc
        supported_source_types = source_types if source_types is not None else {"file"}
        required_keys = keys if keys is not None else []
        produces_capabilities = capabilities or []
        file_extensions = extensions or []
        human_label = label

        def import_content(self, source_path, *, api_keys=None, **kwargs):
            return ImportResult(full_text="")

        def get_parameters(self):
            return params

    return _Throwaway


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


def test_page_content_fields():
    """PageContent stores page number and markdown text."""
    page = PageContent(page_number=3, text="# Hi")
    assert page.page_number == 3
    assert page.text == "# Hi"


def test_extracted_image_defaults():
    """ExtractedImage defaults page_number and description to None."""
    img = ExtractedImage(filename="img_001.png", data=b"\x89PNG")
    assert img.filename == "img_001.png"
    assert img.data == b"\x89PNG"
    assert img.page_number is None
    assert img.description is None


def test_import_result_default_factories_are_independent():
    """ImportResult mutable defaults come from independent factories."""
    a = ImportResult(full_text="a")
    b = ImportResult(full_text="b")
    assert a.pages == [] and a.images == [] and a.metadata == {} and a.source_ref == {}
    a.pages.append(PageContent(1, "x"))
    a.metadata["k"] = "v"
    # b must not see a's mutations — proves default_factory, not shared default.
    assert b.pages == []
    assert b.metadata == {}


def test_plugin_parameter_defaults():
    """PluginParameter applies the documented defaults for optional fields."""
    param = PluginParameter(name="chunk", type="int")
    assert param.description == ""
    assert param.default is None
    assert param.required is False
    assert param.choices is None
    assert param.min_value is None
    assert param.max_value is None
    assert param.advanced is False


# ---------------------------------------------------------------------------
# LibraryImportPlugin.report_progress
# ---------------------------------------------------------------------------


def test_report_progress_invokes_callable_callback():
    """report_progress forwards (current, total, message) to a callable callback."""
    plugin = _make_plugin_cls("rp_a")()
    calls = []
    kwargs = {"progress_callback": lambda c, t, m: calls.append((c, t, m))}
    plugin.report_progress(kwargs, 2, 5, "halfway")
    assert calls == [(2, 5, "halfway")]


def test_report_progress_noop_when_no_callback():
    """report_progress is a silent no-op when no callback is supplied."""
    plugin = _make_plugin_cls("rp_b")()
    plugin.report_progress({}, 1, 1, "done")  # must not raise


def test_report_progress_noop_when_callback_not_callable():
    """report_progress ignores a non-callable progress_callback value."""
    plugin = _make_plugin_cls("rp_c")()
    plugin.report_progress({"progress_callback": "nope"}, 1, 1, "x")  # must not raise


# ---------------------------------------------------------------------------
# PluginRegistry.register
# ---------------------------------------------------------------------------


def test_register_adds_plugin_and_returns_class(fresh_plugin_registry):
    """register stores the class and returns it unchanged (decorator-friendly)."""
    cls = _make_plugin_cls("reg_default")
    returned = fresh_plugin_registry.register(cls)
    assert returned is cls
    assert fresh_plugin_registry._plugins["reg_default"] is cls


def test_register_respects_disable_env(fresh_plugin_registry, monkeypatch):
    """register skips storage when PLUGIN_<NAME>=DISABLE but still returns the class."""
    monkeypatch.setenv("PLUGIN_REG_DISABLED", "DISABLE")
    cls = _make_plugin_cls("reg_disabled")
    returned = fresh_plugin_registry.register(cls)
    assert returned is cls
    assert "reg_disabled" not in fresh_plugin_registry._plugins


# ---------------------------------------------------------------------------
# PluginRegistry.get_plugin
# ---------------------------------------------------------------------------


def test_get_plugin_returns_fresh_instance(fresh_plugin_registry):
    """get_plugin instantiates a new object each call."""
    cls = _make_plugin_cls("gp_fresh")
    fresh_plugin_registry.register(cls)
    a = fresh_plugin_registry.get_plugin("gp_fresh")
    b = fresh_plugin_registry.get_plugin("gp_fresh")
    assert isinstance(a, cls)
    assert a is not b


def test_get_plugin_none_when_missing(fresh_plugin_registry):
    """get_plugin returns None for an unregistered name."""
    assert fresh_plugin_registry.get_plugin("does_not_exist") is None


def test_get_plugin_none_when_disabled(fresh_plugin_registry, monkeypatch):
    """A DISABLE'd plugin never enters the registry, so get_plugin is None."""
    monkeypatch.setenv("PLUGIN_GP_DISABLED", "DISABLE")
    fresh_plugin_registry.register(_make_plugin_cls("gp_disabled"))
    assert fresh_plugin_registry.get_plugin("gp_disabled") is None


# ---------------------------------------------------------------------------
# PluginRegistry.get_plugin_mode
# ---------------------------------------------------------------------------


def test_get_plugin_mode_defaults_advanced(fresh_plugin_registry, monkeypatch):
    """Mode defaults to ADVANCED when no env var is set."""
    monkeypatch.delenv("PLUGIN_MODE_X", raising=False)
    assert fresh_plugin_registry.get_plugin_mode("mode_x") == "ADVANCED"


@pytest.mark.parametrize("value", ["DISABLE", "SIMPLIFIED", "ADVANCED"])
def test_get_plugin_mode_reads_env(fresh_plugin_registry, monkeypatch, value):
    """Mode reads PLUGIN_<UPPER> and recognises the three valid values."""
    monkeypatch.setenv("PLUGIN_MODE_Y", value.lower())
    assert fresh_plugin_registry.get_plugin_mode("mode_y") == value


def test_get_plugin_mode_unrecognized_falls_back_advanced(fresh_plugin_registry, monkeypatch):
    """An unrecognised env value falls back to ADVANCED."""
    monkeypatch.setenv("PLUGIN_MODE_Z", "bogus")
    assert fresh_plugin_registry.get_plugin_mode("mode_z") == "ADVANCED"


# ---------------------------------------------------------------------------
# PluginRegistry.list_plugins
# ---------------------------------------------------------------------------


def test_list_plugins_metadata_shape(fresh_plugin_registry, monkeypatch):
    """list_plugins returns the documented keys with derived/normalised values."""
    from plugins.content_handlers.capability import Capability  # noqa: PLC0415

    monkeypatch.delenv("PLUGIN_LP_SHAPE", raising=False)
    cls = _make_plugin_cls(
        "lp_shape",
        parameters=[PluginParameter(name="depth", type="int")],
        source_types={"url", "file"},
        extensions=[".PDF", "Docx"],
        capabilities=[Capability.TEXT, Capability.PAGES],
        label="Nice Label",
        keys=["openai_vision"],
    )
    # mutate the dict directly so the fixture's attribute rebind restores cleanly
    fresh_plugin_registry._plugins["lp_shape"] = cls

    rows = [r for r in fresh_plugin_registry.list_plugins() if r["name"] == "lp_shape"]
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {
        "name", "description", "source_type", "supported_source_types",
        "required_keys", "produces_capabilities", "file_extensions",
        "human_label", "mode", "parameters",
    }
    # source_type is the first sorted supported source type.
    assert row["supported_source_types"] == ["file", "url"]
    assert row["source_type"] == "file"
    # extensions normalised: lowercase, no leading dot.
    assert row["file_extensions"] == ["pdf", "docx"]
    # capabilities serialised to their string values.
    assert row["produces_capabilities"] == ["text", "pages"]
    assert row["human_label"] == "Nice Label"
    assert row["required_keys"] == ["openai_vision"]
    assert row["mode"] == "ADVANCED"
    assert row["parameters"][0]["name"] == "depth"


def test_list_plugins_human_label_falls_back_to_name(fresh_plugin_registry):
    """An empty human_label falls back to the plugin name."""
    fresh_plugin_registry._plugins["lp_nolabel"] = _make_plugin_cls("lp_nolabel", label="")
    row = next(r for r in fresh_plugin_registry.list_plugins() if r["name"] == "lp_nolabel")
    assert row["human_label"] == "lp_nolabel"


def test_list_plugins_no_source_types_defaults_file(fresh_plugin_registry):
    """A plugin with no supported source types reports source_type 'file'."""
    fresh_plugin_registry._plugins["lp_nosrc"] = _make_plugin_cls(
        "lp_nosrc", source_types=set()
    )
    row = next(r for r in fresh_plugin_registry.list_plugins() if r["name"] == "lp_nosrc")
    assert row["supported_source_types"] == []
    assert row["source_type"] == "file"


def test_list_plugins_simplified_strips_advanced_params(fresh_plugin_registry, monkeypatch):
    """In SIMPLIFIED mode advanced parameters are dropped from the listing."""
    monkeypatch.setenv("PLUGIN_LP_SIMPLE", "SIMPLIFIED")
    fresh_plugin_registry._plugins["lp_simple"] = _make_plugin_cls(
        "lp_simple",
        parameters=[
            PluginParameter(name="basic", type="string"),
            PluginParameter(name="expert", type="int", advanced=True),
        ],
    )
    row = next(r for r in fresh_plugin_registry.list_plugins() if r["name"] == "lp_simple")
    assert row["mode"] == "SIMPLIFIED"
    names = [p["name"] for p in row["parameters"]]
    assert names == ["basic"]


# ---------------------------------------------------------------------------
# PluginRegistry.sanitize_params
# ---------------------------------------------------------------------------


def test_sanitize_params_drops_unknown_always(fresh_plugin_registry, monkeypatch):
    """sanitize_params strips parameters the plugin does not declare."""
    monkeypatch.delenv("PLUGIN_SP_ADV", raising=False)
    fresh_plugin_registry._plugins["sp_adv"] = _make_plugin_cls(
        "sp_adv",
        parameters=[PluginParameter(name="known", type="string")],
    )
    out = fresh_plugin_registry.sanitize_params(
        "sp_adv", {"known": 1, "bogus": 2}
    )
    assert out == {"known": 1}


def test_sanitize_params_drops_advanced_in_simplified(fresh_plugin_registry, monkeypatch):
    """In SIMPLIFIED mode advanced params are stripped as well as unknown ones."""
    monkeypatch.setenv("PLUGIN_SP_SIMPLE", "SIMPLIFIED")
    fresh_plugin_registry._plugins["sp_simple"] = _make_plugin_cls(
        "sp_simple",
        parameters=[
            PluginParameter(name="basic", type="string"),
            PluginParameter(name="expert", type="int", advanced=True),
        ],
    )
    out = fresh_plugin_registry.sanitize_params(
        "sp_simple", {"basic": 1, "expert": 2, "bogus": 3}
    )
    assert out == {"basic": 1}


def test_sanitize_params_keeps_advanced_in_advanced(fresh_plugin_registry, monkeypatch):
    """In ADVANCED mode advanced params survive sanitisation."""
    monkeypatch.delenv("PLUGIN_SP_KEEP", raising=False)
    fresh_plugin_registry._plugins["sp_keep"] = _make_plugin_cls(
        "sp_keep",
        parameters=[
            PluginParameter(name="basic", type="string"),
            PluginParameter(name="expert", type="int", advanced=True),
        ],
    )
    out = fresh_plugin_registry.sanitize_params(
        "sp_keep", {"basic": 1, "expert": 2}
    )
    assert out == {"basic": 1, "expert": 2}


def test_sanitize_params_unknown_plugin_returns_empty(fresh_plugin_registry):
    """sanitize_params returns {} for a plugin that is not registered."""
    assert fresh_plugin_registry.sanitize_params("nope_plugin", {"a": 1}) == {}
