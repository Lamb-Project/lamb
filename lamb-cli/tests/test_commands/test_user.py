"""Tests for user management commands."""

from __future__ import annotations

import json
import os

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()

SAMPLE_USERS = [
    {
        "id": "u-1",
        "email": "alice@uni.edu",
        "name": "Alice Smith",
        "role": "admin",
        "user_type": "creator",
        "enabled": True,
        "auth_provider": "local",
        "created_at": "2025-01-10T08:00:00Z",
        "lti_user_id": None,
    },
    {
        "id": "u-2",
        "email": "bob@uni.edu",
        "name": "Bob Jones",
        "role": "member",
        "user_type": "creator",
        "enabled": True,
        "auth_provider": "local",
        "created_at": "2025-01-12T09:00:00Z",
        "lti_user_id": None,
    },
    {
        "id": "u-3",
        "email": "charlie@uni.edu",
        "name": "Charlie Brown",
        "role": "member",
        "user_type": "end_user",
        "enabled": False,
        "auth_provider": "lti",
        "created_at": "2025-02-01T10:00:00Z",
        "lti_user_id": "lti-abc",
    },
]

SAMPLE_USER_DETAIL = SAMPLE_USERS[0]

SAMPLE_BULK_VALIDATE = {
    "valid": True,
    "total": 2,
    "errors": [],
}

SAMPLE_BULK_EXECUTE = {
    "created": 2,
    "errors": [],
}


class TestUserList:
    def test_list_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_USERS)
        result = runner.invoke(app, ["user", "list"])
        assert result.exit_code == 0
        assert "Alice Smith" in result.output
        assert "Bob Jones" in result.output

    def test_list_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_USERS)
        result = runner.invoke(app, ["user", "list", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert data[0]["email"] == "alice@uni.edu"

    def test_list_plain(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_USERS)
        result = runner.invoke(app, ["user", "list", "-o", "plain"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 3
        assert "u-1" in lines[0]

    def test_list_with_org_flag(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_USERS)
        result = runner.invoke(app, ["user", "list", "--org", "university-a"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "org=university-a" in str(req.url)


class TestUserGet:
    def test_get_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_USERS)
        result = runner.invoke(app, ["user", "get", "u-1"])
        assert result.exit_code == 0
        assert "Alice Smith" in result.output
        assert "alice@uni.edu" in result.output

    def test_get_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_USERS)
        result = runner.invoke(app, ["user", "get", "u-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "u-1"
        assert data["email"] == "alice@uni.edu"

    def test_get_not_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_USERS)
        result = runner.invoke(app, ["user", "get", "u-999"])
        assert result.exit_code != 0


class TestUserCreate:
    def test_create_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={"id": "u-new", "email": "new@uni.edu", "name": "New User", "role": "member", "user_type": "creator", "enabled": True}
        )
        result = runner.invoke(app, ["user", "create", "new@uni.edu", "New User", "pass123"])
        assert result.exit_code == 0
        assert "created" in result.output.lower() or "new@uni.edu" in result.output
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["email"] == "new@uni.edu"
        assert body["name"] == "New User"
        assert body["password"] == "pass123"
        assert body["user_type"] == "creator"
        assert body["enabled"] is True

    def test_create_with_type(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={"id": "u-eu", "email": "end@uni.edu", "name": "End User", "role": "member", "user_type": "end_user", "enabled": True}
        )
        result = runner.invoke(
            app, ["user", "create", "end@uni.edu", "End User", "pass123", "--user-type", "end_user"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["user_type"] == "end_user"

    def test_create_disabled(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={"id": "u-d", "email": "dis@uni.edu", "name": "Disabled User", "role": "member", "user_type": "creator", "enabled": False}
        )
        result = runner.invoke(
            app, ["user", "create", "dis@uni.edu", "Disabled User", "pass123", "--disabled"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["enabled"] is False


class TestUserUpdate:
    def test_update_name(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Updated"})
        result = runner.invoke(app, ["user", "update", "u-1", "--name", "Alice Renamed"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["name"] == "Alice Renamed"

    def test_update_no_fields_fails(self, mock_token):
        result = runner.invoke(app, ["user", "update", "u-1"])
        assert result.exit_code == 1


class TestUserDelete:
    def test_delete_with_confirm(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Deleted"})
        result = runner.invoke(app, ["user", "delete", "u-1", "--confirm"])
        assert result.exit_code == 0
        assert "deleted" in result.output.lower() or "Deleted" in result.output

    def test_delete_interactive_yes(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Deleted"})
        result = runner.invoke(app, ["user", "delete", "u-1"], input="y\n")
        assert result.exit_code == 0

    def test_delete_interactive_no(self, mock_token):
        result = runner.invoke(app, ["user", "delete", "u-1"], input="n\n")
        assert result.exit_code != 0

    def test_delete_with_org(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Deleted"})
        result = runner.invoke(app, ["user", "delete", "u-1", "--confirm", "--org", "university-a"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "org=university-a" in str(req.url)


class TestUserEnable:
    def test_enable_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Enabled"})
        result = runner.invoke(app, ["user", "enable", "u-3"])
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["enabled"] is True


class TestUserDisable:
    def test_disable_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Disabled"})
        result = runner.invoke(app, ["user", "disable", "u-1"])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["enabled"] is False


class TestUserResetPassword:
    def test_reset_password_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Password reset"})
        result = runner.invoke(app, ["user", "reset-password", "u-1", "newpass456"])
        assert result.exit_code == 0
        assert "reset" in result.output.lower()
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["new_password"] == "newpass456"


class TestUserBulkImport:
    def test_bulk_import_dry_run(self, httpx_mock, mock_token, tmp_path):
        payload = {
            "version": "1.0",
            "users": [
                {"email": "a@uni.edu", "name": "A", "user_type": "creator", "enabled": True},
                {"email": "b@uni.edu", "name": "B", "user_type": "creator", "enabled": True},
            ],
        }
        f = tmp_path / "users.json"
        f.write_text(json.dumps(payload))
        httpx_mock.add_response(json=SAMPLE_BULK_VALIDATE)
        result = runner.invoke(app, ["user", "bulk-import", str(f), "--dry-run"])
        assert result.exit_code == 0
        assert "validation" in result.output.lower()
        req = httpx_mock.get_request()
        assert "validate" in str(req.url)

    def test_bulk_import_execute(self, httpx_mock, mock_token, tmp_path):
        payload = {
            "version": "1.0",
            "users": [
                {"email": "a@uni.edu", "name": "A", "user_type": "creator", "enabled": True},
            ],
        }
        f = tmp_path / "users.json"
        f.write_text(json.dumps(payload))
        httpx_mock.add_response(json=SAMPLE_BULK_EXECUTE)
        result = runner.invoke(app, ["user", "bulk-import", str(f)])
        assert result.exit_code == 0
        assert "import" in result.output.lower()
        req = httpx_mock.get_request()
        assert "execute" in str(req.url)

    def test_bulk_import_file_not_found(self, mock_token):
        result = runner.invoke(app, ["user", "bulk-import", "/nonexistent/users.json"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
