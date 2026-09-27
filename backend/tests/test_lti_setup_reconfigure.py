"""Tests for the LTI setup page and activity reconfiguration (Manage activity).

Covers the owner-dashboard-token path that lets the dashboard's "Manage
activity" link reopen setup, and the reconfigure branch of POST /configure
(preserve type/tenant, apply rubric and assistants, redirect by type).
"""

from unittest.mock import MagicMock, patch

import pytest

from lamb import lti_router


class _Form(dict):
    """Minimal stand-in for Starlette's FormData."""

    def getlist(self, key):
        value = self.get(key, [])
        return value if isinstance(value, list) else [value]


class _Request:
    def __init__(self, form):
        self._form = form

    async def form(self):
        return self._form


@pytest.mark.asyncio
@patch("lamb.lti_router._accessible_rubrics_by_org", return_value={})
@patch("lamb.lti_router.templates")
@patch("lamb.lti_router.db_manager")
@patch("lamb.lti_router.manager")
@patch("lamb.lti_router._create_setup_token", return_value="fresh-setup")
@patch("lamb.lti_router._validate_setup_token", return_value=None)
@patch("lamb.lti_router._validate_token")
async def test_setup_reopens_with_owner_dashboard_token(
        mock_validate, mock_validate_setup, mock_create, mock_manager,
        mock_db, mock_templates, mock_rubrics):
    mock_validate.return_value = {
        "type": "dashboard", "is_owner": True,
        "resource_link_id": "rl-1", "lms_user_id": "u-1",
    }
    mock_db.get_lti_activity_by_resource_link.return_value = {
        "id": 1, "resource_link_id": "rl-1", "organization_id": 1,
        "owner_email": "teacher@x", "context_title": "Course",
    }
    mock_db.get_creator_user_by_email.return_value = {
        "id": 9, "organization_id": 1, "email": "teacher@x", "name": "Teacher",
    }
    mock_db.get_activity_assistants.return_value = []
    mock_manager.get_published_assistants_for_instructor.return_value = {}
    mock_templates.TemplateResponse.return_value = "rendered"

    resp = await lti_router.lti_setup_page(
        _Request({}), token="dashboard-token", reconfigure=True)

    assert resp == "rendered"
    # A fresh setup token is minted so the form can be submitted.
    mock_create.assert_called_once()
    kwargs = mock_templates.TemplateResponse.call_args[0][1]
    assert kwargs["reconfigure"] is True


@pytest.mark.asyncio
@patch("lamb.lti_router._validate_token", return_value=None)
@patch("lamb.lti_router._validate_setup_token", return_value=None)
async def test_setup_rejects_unknown_token(mock_setup, mock_token):
    resp = await lti_router.lti_setup_page(_Request({}), token="garbage")
    assert getattr(resp, "status_code", None) == 403


@pytest.mark.asyncio
@patch("lamb.lti_router.db_manager")
@patch("lamb.lti_router.manager")
@patch("lamb.lti_router._validate_setup_token")
async def test_configure_reconfigures_existing_workshop(
        mock_validate, mock_manager, mock_db):
    mock_validate.return_value = {
        "resource_link_id": "rl-w",
        "creator_users": [{"id": 9, "organization_id": 1,
                           "user_email": "t@x", "user_name": "T"}],
    }
    mock_db.get_lti_activity_by_resource_link.return_value = {
        "id": 5, "activity_type": "workshop", "organization_id": 1,
        "chat_visibility_enabled": 0, "resource_link_id": "rl-w",
        "rubric_id": "old-rubric",
    }
    mock_manager.get_public_base_url.return_value = "http://lamb"

    form = _Form({
        "token": "setup", "organization_id": "1",
        "activity_type": "chat", "rubric_id": "new-rubric",
        # Submitted for a workshop it must be forced off (chat-only feature).
        "chat_visibility_enabled": "1",
    })
    resp = await lti_router.lti_configure_activity(_Request(form))

    assert resp.status_code == 303
    assert "workshop/dashboard" in resp.headers["location"]
    # Type/tenant preserved; rubric applied; visibility forced off for
    # workshop; no assistant wiring.
    mock_db.update_lti_activity.assert_called_once_with(
        5, rubric_id="new-rubric", chat_visibility_enabled=False)
    mock_manager.reconfigure_activity.assert_not_called()


@pytest.mark.asyncio
@patch("lamb.lti_router.db_manager")
@patch("lamb.lti_router.manager")
@patch("lamb.lti_router._validate_setup_token")
async def test_configure_reconfigures_existing_chat_assistants(
        mock_validate, mock_manager, mock_db):
    mock_validate.return_value = {
        "resource_link_id": "rl-c",
        "creator_users": [{"id": 9, "organization_id": 1,
                           "user_email": "t@x", "user_name": "T"}],
    }
    mock_db.get_lti_activity_by_resource_link.return_value = {
        "id": 6, "activity_type": "chat", "organization_id": 1,
        "chat_visibility_enabled": 1, "resource_link_id": "rl-c",
        "rubric_id": None,
    }
    mock_manager.get_public_base_url.return_value = "http://lamb"

    form = _Form({
        "token": "setup", "organization_id": "1",
        "activity_type": "chat", "assistant_ids": ["3", "4"],
    })
    resp = await lti_router.lti_configure_activity(_Request(form))

    assert resp.status_code == 303
    assert "/lamb/v1/lti/dashboard" in resp.headers["location"]
    mock_manager.reconfigure_activity.assert_called_once()
    called_ids = mock_manager.reconfigure_activity.call_args[0][1]
    assert called_ids == [3, 4]


@pytest.mark.asyncio
@patch("lamb.lti_router.db_manager")
@patch("lamb.lti_router.manager")
@patch("lamb.lti_router._validate_setup_token")
async def test_configure_creates_new_workshop_redirects_to_workshop(
        mock_validate, mock_manager, mock_db):
    mock_validate.return_value = {
        "resource_link_id": "rl-new",
        "creator_users": [{"id": 9, "organization_id": 1,
                           "user_email": "t@x", "user_name": "T"}],
    }
    mock_db.get_lti_activity_by_resource_link.return_value = None
    mock_manager.get_public_base_url.return_value = "http://lamb"
    mock_manager.configure_activity.return_value = {
        "id": 7, "activity_type": "workshop", "resource_link_id": "rl-new",
    }

    form = _Form({
        "token": "setup", "organization_id": "1",
        "activity_type": "workshop", "rubric_id": "rub-1",
    })
    resp = await lti_router.lti_configure_activity(_Request(form))

    assert resp.status_code == 303
    assert "workshop/dashboard" in resp.headers["location"]
    mock_manager.configure_activity.assert_called_once()
    assert mock_manager.configure_activity.call_args[1]["activity_type"] == "workshop"
