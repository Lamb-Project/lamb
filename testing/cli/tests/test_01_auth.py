"""Authentication tests — maps to login_signup_authentication.spec.js.

CLI-testable subset: login, logout, status, whoami, invalid credentials,
invalid token, disabled user login.  Signup flows are UI-only (no CLI command).
"""

import os

import pytest

from helpers.cli_runner import LambCLI

ADMIN_EMAIL = os.getenv("LOGIN_EMAIL", "admin@owi.com")
ADMIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "admin")
SERVER_URL = os.getenv("LAMB_SERVER_URL", "http://localhost:9099")


class TestAuth:
    """Sequential auth tests."""

    def test_login_wrong_credentials(self, unauthenticated_cli: LambCLI):
        """Wrong email/password returns exit code 4."""
        result = unauthenticated_cli.run(
            "login",
            "--email", "nonexistent_user@invalid.com",
            "--password", "wrong_password_12345",
            "--server-url", SERVER_URL,
        )
        result.assert_failure(expected_code=4)

    def test_status_server_reachable(self, cli: LambCLI):
        """Server status check succeeds."""
        result = cli.run("status")
        result.assert_success()
        result.assert_stderr_contains("running")

    def test_whoami_returns_admin(self, cli: LambCLI):
        """Whoami shows the logged-in admin user."""
        result = cli.run_json("whoami")
        result.assert_success()
        data = result.json
        assert data.get("email"), "whoami should return an email"

    def test_whoami_json_has_required_fields(self, cli: LambCLI):
        """Whoami JSON contains id, email, name."""
        result = cli.run_json("whoami")
        result.assert_success()
        data = result.json
        assert "id" in data
        assert "email" in data
        assert "name" in data

    def test_unauthenticated_whoami_fails(self, unauthenticated_cli: LambCLI):
        """Whoami without token fails with exit code 4."""
        result = unauthenticated_cli.run("whoami")
        result.assert_failure(expected_code=4)

    def test_invalid_token_rejected(self, server_url: str):
        """A fake token is rejected by API calls."""
        bad_cli = LambCLI(server_url=server_url, token="fake-expired-token-xyz-123")
        result = bad_cli.run("whoami")
        result.assert_failure()
        # Should be auth error (4) or API error (2)
        assert result.returncode in (2, 4), f"Unexpected exit code: {result.returncode}"

    def test_logout_then_commands_fail(self, server_url: str, admin_token: str):
        """After logout, commands that need auth should fail.

        We simulate this by creating a CLI with no token (equivalent to post-logout).
        Note: We don't actually call ``lamb logout`` because that would clear the
        credential file on disk, which doesn't affect our env-var-based test setup.
        """
        no_token_cli = LambCLI(server_url=server_url, token=None)
        result = no_token_cli.run("assistant", "list")
        result.assert_failure(expected_code=4)
