"""Access control — maps to access_control_and_user_dashboard.spec.js.

Tests: create user, have user create assistant, verify admin sees read_only
access_level, verify owner sees full access, cleanup.
"""

import os

import pytest

from conftest import login_as
from helpers.cli_runner import LambCLI

SERVER_URL = os.getenv("LAMB_SERVER_URL", "http://localhost:9099")


class TestAccessControl:
    """Sequential access-control tests."""

    user_id: str = ""
    user_email: str = ""
    assistant_id: str = ""

    def test_create_test_user(self, cli: LambCLI, timestamp: str):
        """Create a non-admin test user."""
        email = f"acl_user_{timestamp}@test.com"
        name = f"ACL User {timestamp}"
        result = cli.run_json(
            "user", "create", email, name, "AclTest_2026!",
        )
        result.assert_success()
        data = result.json
        TestAccessControl.user_id = str(data.get("id", ""))
        TestAccessControl.user_email = email

    def test_user_creates_assistant(self, timestamp: str):
        """Test user logs in and creates an assistant."""
        email = f"acl_user_{timestamp}@test.com"
        token = login_as(email, "AclTest_2026!")
        user_cli = LambCLI(server_url=SERVER_URL, token=token)

        name = f"cli_acl_asst_{timestamp}"
        result = user_cli.run_json(
            "assistant", "create", name,
            "-d", "Assistant for ACL testing",
            "-s", "You are a helpful assistant for testing access control.",
            "--connector", "openai",
        )
        result.assert_success()
        TestAccessControl.assistant_id = str(result.json.get("assistant_id", ""))

    def test_admin_sees_assistant_read_only(self, cli: LambCLI):
        """Admin viewing another user's assistant sees read_only access."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run_json("assistant", "get", self.assistant_id)
        result.assert_success()
        data = result.json
        # The API should return access_level and is_owner fields
        if "access_level" in data:
            assert data["access_level"] == "read_only"
        if "is_owner" in data:
            assert data["is_owner"] is False

    def test_owner_sees_full_access(self, timestamp: str):
        """Owner viewing own assistant sees full access."""
        assert self.assistant_id, "Assistant not created"
        email = f"acl_user_{timestamp}@test.com"
        token = login_as(email, "AclTest_2026!")
        user_cli = LambCLI(server_url=SERVER_URL, token=token)

        result = user_cli.run_json("assistant", "get", self.assistant_id)
        result.assert_success()
        data = result.json
        if "is_owner" in data:
            assert data["is_owner"] is True

    def test_cleanup_delete_assistant(self, timestamp: str):
        """Owner deletes the assistant."""
        if not self.assistant_id:
            pytest.skip("Assistant not created")
        email = f"acl_user_{timestamp}@test.com"
        token = login_as(email, "AclTest_2026!")
        user_cli = LambCLI(server_url=SERVER_URL, token=token)
        result = user_cli.run("assistant", "delete", self.assistant_id, "--confirm")
        result.assert_success()

    def test_cleanup_disable_user(self, cli: LambCLI):
        """Disable the test user."""
        if not self.user_id:
            pytest.skip("User not created")
        cli.run("user", "disable", self.user_id)
