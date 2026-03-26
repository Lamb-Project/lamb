"""Tests for login, logout, whoami, and status commands."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()

SERVER = "http://localhost:9099"


class TestLogin:
    def test_login_success(self, httpx_mock, tmp_config_dir):
        httpx_mock.add_response(
            url=f"{SERVER}/creator/login",
            json={
                "success": True,
                "data": {
                    "token": "jwt-123",
                    "name": "Test User",
                    "email": "test@example.com",
                    "role": "admin",
                    "user_type": "creator",
                    "organization_role": "owner",
                },
            },
        )
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            os.environ.pop("LAMB_SERVER_URL", None)
            result = runner.invoke(
                app, ["login", "--email", "test@example.com", "--password", "pass123"]
            )
        assert result.exit_code == 0
        # Verify credentials were saved with role info
        from lamb_cli.config import get_user_info
        info = get_user_info()
        assert info["role"] == "admin"
        assert info["organization_role"] == "owner"
        assert info["email"] == "test@example.com"

    def test_login_failure(self, httpx_mock, tmp_config_dir):
        httpx_mock.add_response(
            url=f"{SERVER}/creator/login",
            json={"success": False, "detail": "Invalid credentials"},
        )
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            os.environ.pop("LAMB_SERVER_URL", None)
            result = runner.invoke(
                app, ["login", "--email", "bad@example.com", "--password", "wrong"]
            )
        assert result.exit_code == 4

    def test_login_saves_role_info(self, httpx_mock, tmp_config_dir):
        httpx_mock.add_response(
            url=f"{SERVER}/creator/login",
            json={
                "success": True,
                "data": {
                    "token": "jwt-456",
                    "name": "Org Admin",
                    "email": "orgadmin@uni.edu",
                    "role": "user",
                    "user_type": "creator",
                    "organization_role": "admin",
                },
            },
        )
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            os.environ.pop("LAMB_SERVER_URL", None)
            result = runner.invoke(
                app, ["login", "--email", "orgadmin@uni.edu", "--password", "pass"]
            )
        assert result.exit_code == 0
        # Verify credentials file stores role info
        from lamb_cli.config import get_user_info
        info = get_user_info()
        assert info["organization_role"] == "admin"
        assert info["role"] == "user"
        assert info["user_type"] == "creator"

    def test_login_with_server_url(self, httpx_mock, tmp_config_dir):
        custom_server = "http://custom:9099"
        httpx_mock.add_response(
            url=f"{custom_server}/creator/login",
            json={
                "success": True,
                "data": {
                    "token": "jwt-789",
                    "name": "User",
                    "email": "u@test.com",
                    "role": "",
                    "user_type": "creator",
                    "organization_role": "",
                },
            },
        )
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            os.environ.pop("LAMB_SERVER_URL", None)
            result = runner.invoke(
                app,
                ["login", "--email", "u@test.com", "--password", "p", "--server-url", custom_server],
            )
        assert result.exit_code == 0


class TestLogout:
    def test_logout(self, tmp_config_dir):
        from lamb_cli.config import save_credentials
        save_credentials("tok", "a@b.com")
        result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0
        assert "Logged out" in result.output


class TestStatus:
    def test_server_running(self, httpx_mock, tmp_config_dir):
        httpx_mock.add_response(url=f"{SERVER}/status", json={"status": True})
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            os.environ.pop("LAMB_SERVER_URL", None)
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "running" in result.output

    def test_server_bad_response(self, httpx_mock, tmp_config_dir):
        httpx_mock.add_response(url=f"{SERVER}/status", json={"status": False})
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LAMB_TOKEN", None)
            os.environ.pop("LAMB_SERVER_URL", None)
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 2


class TestWhoami:
    def test_whoami_table(self, httpx_mock, tmp_config_dir, mock_token):
        httpx_mock.add_response(
            url=f"{SERVER}/creator/user/current",
            json={"id": "u1", "email": "me@test.com", "name": "Me"},
        )
        # Simulate stored role info from login
        from lamb_cli.config import save_credentials
        save_credentials(
            "test-token-abc123", "me@test.com",
            name="Me", role="admin",
            user_type="creator", organization_role="owner",
        )
        result = runner.invoke(app, ["whoami"])
        assert result.exit_code == 0
        assert "me@test.com" in result.output
        assert "admin" in result.output
        assert "owner" in result.output

    def test_whoami_json(self, httpx_mock, tmp_config_dir, mock_token):
        httpx_mock.add_response(
            url=f"{SERVER}/creator/user/current",
            json={
                "id": "u1", "email": "me@test.com", "name": "Me",
                "role": "admin", "user_type": "creator", "organization_role": "owner",
            },
        )
        result = runner.invoke(app, ["whoami", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["email"] == "me@test.com"
        assert data["role"] == "admin"
        assert data["organization_role"] == "owner"
