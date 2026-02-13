"""Tests for organization commands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()

SAMPLE_ORGS = [
    {
        "id": "org-1",
        "slug": "university-a",
        "name": "University A",
        "status": "active",
        "is_system": False,
        "created_at": "2025-01-10T08:00:00Z",
        "updated_at": "2025-01-15T12:00:00Z",
    },
    {
        "id": "org-2",
        "slug": "college-b",
        "name": "College B",
        "status": "active",
        "is_system": False,
        "created_at": "2025-02-01T09:00:00Z",
        "updated_at": "2025-02-05T10:00:00Z",
    },
]

SAMPLE_ORG_DETAIL = {
    "id": "org-1",
    "slug": "university-a",
    "name": "University A",
    "status": "active",
    "is_system": False,
    "created_at": "2025-01-10T08:00:00Z",
    "updated_at": "2025-01-15T12:00:00Z",
}

SAMPLE_DASHBOARD = {
    "organization": {
        "name": "University A",
        "slug": "university-a",
        "status": "active",
    },
    "stats": {
        "total_users": 25,
        "active_users": 20,
        "total_assistants": 10,
        "total_knowledge_bases": 5,
    },
    "settings_status": {
        "llm_configured": True,
        "kb_configured": True,
    },
}

SAMPLE_EXPORT = {
    "organization": SAMPLE_ORG_DETAIL,
    "members": [
        {"id": "u-1", "email": "admin@uni.edu", "role": "admin"},
    ],
    "assistants": [],
}


class TestOrgList:
    def test_list_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ORGS)
        result = runner.invoke(app, ["org", "list"])
        assert result.exit_code == 0
        assert "University A" in result.output
        assert "College B" in result.output

    def test_list_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ORGS)
        result = runner.invoke(app, ["org", "list", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["slug"] == "university-a"

    def test_list_plain(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ORGS)
        result = runner.invoke(app, ["org", "list", "-o", "plain"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 2
        assert "org-1" in lines[0]


class TestOrgGet:
    def test_get_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ORG_DETAIL)
        result = runner.invoke(app, ["org", "get", "university-a"])
        assert result.exit_code == 0
        assert "University A" in result.output
        assert "active" in result.output.lower()

    def test_get_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_ORG_DETAIL)
        result = runner.invoke(app, ["org", "get", "university-a", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slug"] == "university-a"
        assert data["name"] == "University A"

    def test_get_not_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=404, json={"detail": "Not found"})
        result = runner.invoke(app, ["org", "get", "nonexistent"])
        assert result.exit_code != 0


class TestOrgCreate:
    def test_create_basic(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={"id": "org-new", "slug": "new-org", "name": "New Org", "status": "active", "is_system": False}
        )
        result = runner.invoke(app, ["org", "create", "New Org", "--slug", "new-org"])
        assert result.exit_code == 0
        assert "created" in result.output.lower() or "new-org" in result.output
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["name"] == "New Org"
        assert body["slug"] == "new-org"

    def test_create_with_admin_user_id(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={"id": "org-new", "slug": "admin-org", "name": "Admin Org", "status": "active", "is_system": False}
        )
        result = runner.invoke(
            app, ["org", "create", "Admin Org", "--slug", "admin-org", "--admin-user-id", "user-123"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["admin_user_id"] == "user-123"

    def test_create_with_signup(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={"id": "org-s", "slug": "signup-org", "name": "Signup Org", "status": "active", "is_system": False}
        )
        result = runner.invoke(
            app,
            ["org", "create", "Signup Org", "--slug", "signup-org", "--signup-enabled", "--signup-key", "secret123"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["signup_enabled"] is True
        assert body["signup_key"] == "secret123"


class TestOrgUpdate:
    def test_update_name(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Updated"})
        result = runner.invoke(app, ["org", "update", "university-a", "--name", "Uni A Renamed"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["name"] == "Uni A Renamed"

    def test_update_status(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Updated"})
        result = runner.invoke(app, ["org", "update", "university-a", "--status", "inactive"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["status"] == "inactive"

    def test_update_no_fields_fails(self, mock_token):
        result = runner.invoke(app, ["org", "update", "university-a"])
        assert result.exit_code == 1


class TestOrgDelete:
    def test_delete_with_confirm(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Deleted"})
        result = runner.invoke(app, ["org", "delete", "university-a", "--confirm"])
        assert result.exit_code == 0
        assert "deleted" in result.output.lower() or "Deleted" in result.output

    def test_delete_interactive_yes(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Deleted"})
        result = runner.invoke(app, ["org", "delete", "university-a"], input="y\n")
        assert result.exit_code == 0

    def test_delete_interactive_no(self, mock_token):
        result = runner.invoke(app, ["org", "delete", "university-a"], input="n\n")
        assert result.exit_code != 0


class TestOrgExport:
    def test_export_stdout(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_EXPORT)
        result = runner.invoke(app, ["org", "export", "university-a"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "organization" in data
        assert data["organization"]["slug"] == "university-a"

    def test_export_to_file(self, httpx_mock, mock_token, tmp_path):
        httpx_mock.add_response(json=SAMPLE_EXPORT)
        out_file = tmp_path / "org-export.json"
        result = runner.invoke(app, ["org", "export", "university-a", "-f", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["organization"]["slug"] == "university-a"


class TestOrgSetRole:
    def test_set_role_admin(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Role updated"})
        result = runner.invoke(app, ["org", "set-role", "university-a", "user-1", "admin"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["role"] == "admin"

    def test_set_role_member(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Role updated"})
        result = runner.invoke(app, ["org", "set-role", "university-a", "user-1", "member"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["role"] == "member"

    def test_set_role_invalid(self, mock_token):
        result = runner.invoke(app, ["org", "set-role", "university-a", "user-1", "superadmin"])
        assert result.exit_code == 1


class TestOrgDashboard:
    def test_dashboard_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_DASHBOARD)
        result = runner.invoke(app, ["org", "dashboard"])
        assert result.exit_code == 0
        assert "University A" in result.output
        assert "25" in result.output  # total_users

    def test_dashboard_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_DASHBOARD)
        result = runner.invoke(app, ["org", "dashboard", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["organization"]["name"] == "University A"
        assert data["stats"]["total_users"] == 25

    def test_dashboard_with_org_flag(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_DASHBOARD)
        result = runner.invoke(app, ["org", "dashboard", "--org", "university-a"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "org=university-a" in str(req.url)
