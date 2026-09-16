"""
Tests for the workshop module (contract alignment with #277 ActivityModule).
"""

from unittest.mock import MagicMock, patch

from lamb.modules.workshop import WorkshopModule, module
from lamb.modules import discover_modules, get_module
from lamb.modules.workshop.routers import _resolve_tool_definitions
from lamb.completions.tools.definitions import CALCULATOR_DEF
from lamb.lti_activity_manager import LtiActivityManager


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


def _bare_manager():
    """An LtiActivityManager with mocked collaborators (bypass __init__)."""
    mgr = LtiActivityManager.__new__(LtiActivityManager)
    mgr.db_manager = MagicMock()
    mgr.owi_user_manager = MagicMock()
    mgr.owi_group_manager = MagicMock()
    return mgr


def test_configure_activity_workshop_persists_type_without_owi():
    """A workshop activity is DB-only: activity_type stored, no OWI group,
    no assistant links, even with an empty assistant list."""
    mgr = _bare_manager()
    mgr.db_manager.create_lti_activity.return_value = 5
    mgr.db_manager.get_lti_activity_by_resource_link.return_value = {
        "id": 5, "activity_type": "workshop"}

    result = mgr.configure_activity(
        resource_link_id="rl-w", organization_id=1, assistant_ids=[],
        configured_by_email="t@x.com", activity_name="WS",
        activity_type="workshop",
    )

    assert result["activity_type"] == "workshop"
    mgr.owi_user_manager.get_user_by_email.assert_not_called()
    mgr.owi_group_manager.create_group.assert_not_called()
    mgr.db_manager.add_assistants_to_activity.assert_not_called()
    _, kwargs = mgr.db_manager.create_lti_activity.call_args
    assert kwargs["activity_type"] == "workshop"


def test_configure_activity_chat_creates_group_and_links_assistants():
    """Chat activities keep the existing OWI-group + assistant-link behavior
    and forward activity_type='chat'."""
    mgr = _bare_manager()
    mgr.owi_user_manager.get_user_by_email.return_value = {"id": "u1"}
    mgr.owi_group_manager.create_group.return_value = {"id": "g1"}
    mgr.db_manager.create_lti_activity.return_value = 7
    mgr.db_manager.get_lti_activity_by_resource_link.return_value = {"id": 7}

    with patch("lamb.lti_activity_manager.OwiDatabaseManager"), \
            patch("lamb.lti_activity_manager.OWIModel") as mock_model:
        mock_model.return_value.add_group_to_model.return_value = True
        mgr.configure_activity(
            resource_link_id="rl-c", organization_id=1, assistant_ids=[3],
            configured_by_email="t@x.com", activity_type="chat",
        )

    mgr.owi_group_manager.create_group.assert_called_once()
    mgr.db_manager.add_assistants_to_activity.assert_called_once_with(7, [3])
    _, kwargs = mgr.db_manager.create_lti_activity.call_args
    assert kwargs["activity_type"] == "chat"
