"""
Tests for the workshop module (contract alignment with #277 ActivityModule).
"""

from lamb.modules.workshop import WorkshopModule, module
from lamb.modules import discover_modules, get_module
from lamb.modules.workshop.routers import _resolve_tool_definitions
from lamb.completions.tools.definitions import CALCULATOR_DEF


def test_module_discovered():
    """WM1: workshop module is discoverable with correct metadata."""
    modules = discover_modules()
    assert "workshop" in modules
    assert modules["workshop"].name == "workshop"
    assert modules["workshop"].display_name == "AI Workshop"

    # get_module convenience
    ws = get_module("workshop")
    assert ws is not None
    assert ws.name == "workshop"


def test_module_contract_methods():
    """WM2: workshop module implements the ActivityModule contract surface."""
    required = [
        "get_migrations",
        "get_routers",
        "get_setup_fields",
        "on_activity_configured",
        "on_student_launch",
        "on_instructor_launch",
        "launch_user",
        "get_dashboard_stats",
        "get_frontend_build_path",
    ]
    for method in required:
        assert hasattr(module, method), f"Missing contract method: {method}"
        assert callable(getattr(module, method))


def test_module_defaults():
    """Module exposes sensible defaults for the contract surfaces."""
    assert module.get_migrations() == []
    assert module.get_setup_fields() == []
    assert module.get_frontend_build_path() == "/m/workshop/"


def test_resolve_tool_definitions_completes_name_only_stub():
    """Name-only stubs get filled with the canonical parameters schema.

    Regression: the frontend sent ``[{type:function, function:{name:
    "calculator"}}]`` with no parameter schema, so the model invented malformed
    args like ``{"x":3,"y":5}`` and the tool failed with "No expression
    provided". Resolution must attach the full schema (expression + required).
    """
    stubs = [{"type": "function", "function": {"name": "calculator"}}]
    resolved = _resolve_tool_definitions(stubs)
    assert resolved == [CALCULATOR_DEF]
    fn = resolved[0]["function"]
    assert "expression" in fn["parameters"]["properties"]
    assert fn["parameters"]["required"] == ["expression"]


def test_resolve_tool_definitions_passthrough_full_schema():
    """Already-fully-specified definitions are passed through untouched."""
    resolved = _resolve_tool_definitions([CALCULATOR_DEF])
    assert resolved == [CALCULATOR_DEF]


def test_resolve_tool_definitions_drops_unknown():
    """Unknown tool names and empty input resolve to None (no tools)."""
    assert _resolve_tool_definitions(None) is None
    assert _resolve_tool_definitions([]) is None
    assert _resolve_tool_definitions([{"type": "function", "function": {"name": "nope"}}]) is None
