"""
Tests for the workshop module (contract alignment with #277 ActivityModule).
"""

from lamb.modules.workshop import WorkshopModule, module
from lamb.modules import discover_modules, get_module


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
