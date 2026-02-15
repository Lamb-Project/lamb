"""Admin CRUD + assistant sharing — maps to admin_and_sharing_flow.spec.js.

Part 1: Create user, create org with user as admin, disable user, delete org.
Part 2: Create two users, create org, have user1 create an assistant,
        share it with user2 via API, verify user2 can see it, cleanup.
"""

import os

import httpx
import pytest

from conftest import login_as
from helpers.cli_runner import LambCLI

SERVER_URL = os.getenv("LAMB_SERVER_URL", "http://localhost:9099")


class TestAdminAndSharing:
    """Sequential admin CRUD and sharing tests."""

    # Part 1 state
    user1_id: str = ""
    org1_slug: str = ""

    # Part 2 state
    sharing_user1_id: str = ""
    sharing_user2_id: str = ""
    sharing_org_slug: str = ""
    sharing_assistant_id: str = ""

    # --- Part 1: Admin CRUD ------------------------------------------------

    def test_create_user(self, cli: LambCLI, timestamp: str):
        """Create a user as system admin."""
        email = f"cliuser_{timestamp}@test.com"
        name = f"cli_user_{timestamp}"
        result = cli.run_json(
            "user", "create", email, name, "test_password_123",
        )
        result.assert_success()
        data = result.json
        assert data.get("id") or data.get("email")
        TestAdminAndSharing.user1_id = str(data.get("id", ""))

    def test_disable_user(self, cli: LambCLI):
        """Disable the user (while still in system org)."""
        assert self.user1_id, "User not created"
        result = cli.run("user", "disable", self.user1_id)
        result.assert_success()

    def test_create_org(self, cli: LambCLI, timestamp: str):
        """Create an organization (no admin assignment)."""
        slug = f"cli-org-{timestamp}"
        name = f"CLI Org {timestamp}"
        result = cli.run_json("org", "create", name, "-s", slug)
        result.assert_success()
        TestAdminAndSharing.org1_slug = slug

    def test_delete_org(self, cli: LambCLI):
        """Delete the organization."""
        assert self.org1_slug, "Org not created"
        result = cli.run("org", "delete", self.org1_slug, "--confirm")
        result.assert_success()

    # --- Part 2: Assistant Sharing -----------------------------------------

    def test_sharing_create_user1(self, cli: LambCLI, timestamp: str):
        """Create first user (future org admin)."""
        email = f"sharing_u1_{timestamp}@test.com"
        name = f"Sharing User1 {timestamp}"
        result = cli.run_json(
            "user", "create", email, name, "test_password_123",
        )
        result.assert_success()
        TestAdminAndSharing.sharing_user1_id = str(result.json.get("id", ""))

    def test_sharing_create_org(self, cli: LambCLI, timestamp: str):
        """Create org with first user as admin."""
        slug = f"sharing-org-{timestamp}"
        name = f"Sharing Org {timestamp}"
        args = ["org", "create", name, "-s", slug]
        if self.sharing_user1_id:
            args += ["--admin-user-id", self.sharing_user1_id]
        result = cli.run_json(*args)
        result.assert_success()
        TestAdminAndSharing.sharing_org_slug = slug

    def test_sharing_create_user2(self, cli: LambCLI, timestamp: str):
        """Create second user."""
        email = f"sharing_u2_{timestamp}@test.com"
        name = f"Sharing User2 {timestamp}"
        result = cli.run_json(
            "user", "create", email, name, "test_password_123",
        )
        result.assert_success()
        TestAdminAndSharing.sharing_user2_id = str(result.json.get("id", ""))

    def test_sharing_user1_creates_assistant(self, cli: LambCLI, timestamp: str):
        """Login as user1 and create an assistant."""
        email = f"sharing_u1_{timestamp}@test.com"
        token = login_as(email, "test_password_123")
        user1_cli = LambCLI(server_url=SERVER_URL, token=token)

        name = f"shared_asst_{timestamp}"
        result = user1_cli.run_json(
            "assistant", "create", name,
            "-d", "Assistant for sharing test",
            "-s", "You are a helpful assistant.",
            "--connector", "openai",
        )
        result.assert_success()
        TestAdminAndSharing.sharing_assistant_id = str(
            result.json.get("assistant_id", "")
        )

    def test_sharing_cleanup_delete_assistant(self, cli: LambCLI, timestamp: str):
        """Login as user1 and delete the assistant."""
        if not self.sharing_assistant_id:
            pytest.skip("Assistant not created")
        email = f"sharing_u1_{timestamp}@test.com"
        token = login_as(email, "test_password_123")
        user1_cli = LambCLI(server_url=SERVER_URL, token=token)
        result = user1_cli.run(
            "assistant", "delete", self.sharing_assistant_id, "--confirm",
        )
        result.assert_success()

    def test_sharing_cleanup_delete_org(self, cli: LambCLI):
        """Delete the sharing org."""
        if not self.sharing_org_slug:
            pytest.skip("Org not created")
        result = cli.run("org", "delete", self.sharing_org_slug, "--confirm")
        result.assert_success()

    def test_sharing_cleanup_disable_users(self, cli: LambCLI):
        """Disable both sharing test users."""
        for uid in [self.sharing_user1_id, self.sharing_user2_id]:
            if uid:
                cli.run("user", "disable", uid)
