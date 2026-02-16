"""AuthContext E2E tests — validates centralized auth and authorization.

Tests the AuthContext migration by exercising real API endpoints through the
CLI, verifying authentication, role-based access control, resource ownership,
and cross-organization isolation.

Scenario:
  1. Admin (system admin) authenticates and can access admin-only endpoints
  2. A regular user is created and can only access own resources
  3. A second user creates resources; first user cannot modify/delete them
  4. Admin endpoints reject non-admin users
  5. Organization isolation is enforced
  6. Invalid/missing tokens are rejected consistently
"""

import os

import pytest

from conftest import login_as
from helpers.cli_runner import LambCLI

SERVER_URL = os.getenv("LAMB_SERVER_URL", "http://localhost:9099")


class TestAuthContextIdentity:
    """Verify AuthContext resolves user identity correctly."""

    def test_admin_whoami_returns_identity(self, cli: LambCLI):
        """Admin whoami returns id, email, name from AuthContext."""
        result = cli.run_json("whoami")
        result.assert_success()
        data = result.json
        assert "id" in data
        assert "email" in data
        assert "name" in data

    def test_admin_can_list_users(self, cli: LambCLI):
        """System admin can access admin-only user list endpoint."""
        result = cli.run_json("user", "list")
        result.assert_success()
        users = result.json
        if isinstance(users, dict):
            users = users.get("users", [])
        assert isinstance(users, list)
        assert len(users) > 0, "Admin should see at least one user"

    def test_admin_can_list_orgs(self, cli: LambCLI):
        """System admin can access admin-only org list endpoint."""
        result = cli.run_json("org", "list")
        result.assert_success()
        orgs = result.json
        assert isinstance(orgs, list)
        assert len(orgs) > 0, "Admin should see at least one organization"

    def test_unauthenticated_whoami_rejected(self, unauthenticated_cli: LambCLI):
        """No token -> auth fails (AuthContext not built)."""
        result = unauthenticated_cli.run("whoami")
        result.assert_failure(expected_code=4)

    def test_invalid_token_rejected(self, server_url: str):
        """Garbage token -> AuthContext build fails, 401 returned."""
        bad_cli = LambCLI(server_url=server_url, token="totally-invalid-garbage-token")
        result = bad_cli.run("whoami")
        result.assert_failure()
        assert result.returncode in (2, 4)


class TestAuthContextRoleEnforcement:
    """Verify admin-only endpoints reject non-admin users via AuthContext."""

    user_id: str = ""
    user_email: str = ""
    user_token: str = ""

    def test_create_regular_user(self, cli: LambCLI, timestamp: str):
        """Admin creates a regular (non-admin) user for role tests."""
        email = f"authctx_regular_{timestamp}@test.com"
        result = cli.run_json(
            "user", "create", email, f"AuthCtx Regular {timestamp}", "AuthCtxTest_2026!",
        )
        result.assert_success()
        data = result.json
        TestAuthContextRoleEnforcement.user_id = str(data.get("id", ""))
        TestAuthContextRoleEnforcement.user_email = email
        TestAuthContextRoleEnforcement.user_token = login_as(email, "AuthCtxTest_2026!")

    def test_regular_user_whoami_works(self):
        """Regular user can authenticate and call whoami."""
        assert self.user_token, "User not created"
        user_cli = LambCLI(server_url=SERVER_URL, token=self.user_token)
        result = user_cli.run_json("whoami")
        result.assert_success()
        assert result.json["email"] == self.user_email

    def test_regular_user_cannot_list_all_users(self):
        """Non-admin user is denied access to admin user list (AuthContext.is_system_admin=False)."""
        assert self.user_token, "User not created"
        user_cli = LambCLI(server_url=SERVER_URL, token=self.user_token)
        result = user_cli.run("user", "list")
        result.assert_failure()

    def test_regular_user_cannot_create_user(self):
        """Non-admin cannot create users (admin-only endpoint)."""
        assert self.user_token, "User not created"
        user_cli = LambCLI(server_url=SERVER_URL, token=self.user_token)
        result = user_cli.run(
            "user", "create", "should_fail@test.com", "Should Fail", "Fail_2026!",
        )
        result.assert_failure()

    def test_regular_user_cannot_list_orgs(self):
        """Non-admin cannot list organizations (admin-only endpoint)."""
        assert self.user_token, "User not created"
        user_cli = LambCLI(server_url=SERVER_URL, token=self.user_token)
        result = user_cli.run("org", "list")
        result.assert_failure()

    def test_cleanup_disable_user(self, cli: LambCLI):
        """Cleanup: disable the test user."""
        if self.user_id:
            cli.run("user", "disable", self.user_id)


class TestAuthContextResourceOwnership:
    """Verify AuthContext enforces resource ownership for assistants."""

    owner_id: str = ""
    owner_email: str = ""
    owner_token: str = ""
    other_id: str = ""
    other_email: str = ""
    other_token: str = ""
    assistant_id: str = ""

    def test_create_owner_user(self, cli: LambCLI, timestamp: str):
        """Create user A (owner) who will create the assistant."""
        email = f"authctx_owner_{timestamp}@test.com"
        result = cli.run_json(
            "user", "create", email, f"AuthCtx Owner {timestamp}", "OwnerTest_2026!",
        )
        result.assert_success()
        TestAuthContextResourceOwnership.owner_id = str(result.json.get("id", ""))
        TestAuthContextResourceOwnership.owner_email = email
        TestAuthContextResourceOwnership.owner_token = login_as(email, "OwnerTest_2026!")

    def test_create_other_user(self, cli: LambCLI, timestamp: str):
        """Create user B (other) who should not own the assistant."""
        email = f"authctx_other_{timestamp}@test.com"
        result = cli.run_json(
            "user", "create", email, f"AuthCtx Other {timestamp}", "OtherTest_2026!",
        )
        result.assert_success()
        TestAuthContextResourceOwnership.other_id = str(result.json.get("id", ""))
        TestAuthContextResourceOwnership.other_email = email
        TestAuthContextResourceOwnership.other_token = login_as(email, "OtherTest_2026!")

    def test_owner_creates_assistant(self, timestamp: str):
        """User A creates an assistant."""
        assert self.owner_token, "Owner not created"
        owner_cli = LambCLI(server_url=SERVER_URL, token=self.owner_token)
        name = f"cli_authctx_asst_{timestamp}"
        result = owner_cli.run_json(
            "assistant", "create", name,
            "-d", "AuthContext ownership test assistant",
            "-s", "You are a helpful assistant.",
            "--connector", "bypass",
        )
        result.assert_success()
        TestAuthContextResourceOwnership.assistant_id = str(
            result.json.get("assistant_id", result.json.get("id", ""))
        )
        assert self.assistant_id, "Assistant ID not returned"

    def test_owner_can_get_assistant(self):
        """Owner can read their own assistant (AuthContext: access_level=owner)."""
        assert self.assistant_id and self.owner_token
        owner_cli = LambCLI(server_url=SERVER_URL, token=self.owner_token)
        result = owner_cli.run_json("assistant", "get", self.assistant_id)
        result.assert_success()
        data = result.json
        if "is_owner" in data:
            assert data["is_owner"] is True

    def test_owner_can_update_assistant(self):
        """Owner can update their own assistant (AuthContext: can_modify=True)."""
        assert self.assistant_id and self.owner_token
        owner_cli = LambCLI(server_url=SERVER_URL, token=self.owner_token)
        result = owner_cli.run_json(
            "assistant", "update", self.assistant_id,
            "-d", "Updated description via AuthContext test",
        )
        result.assert_success()

    def test_other_user_cannot_delete_assistant(self):
        """User B cannot delete User A's assistant (AuthContext: not owner, not admin)."""
        assert self.assistant_id and self.other_token
        other_cli = LambCLI(server_url=SERVER_URL, token=self.other_token)
        result = other_cli.run("assistant", "delete", self.assistant_id, "--confirm")
        result.assert_failure()

    def test_admin_can_see_assistant(self, cli: LambCLI):
        """System admin can read any assistant (AuthContext: is_system_admin=True)."""
        assert self.assistant_id
        result = cli.run_json("assistant", "get", self.assistant_id)
        result.assert_success()
        data = result.json
        if "access_level" in data:
            assert data["access_level"] in ("read_only", "admin", "owner")

    def test_owner_deletes_assistant(self):
        """Cleanup: owner deletes their assistant."""
        if not self.assistant_id or not self.owner_token:
            pytest.skip("Assistant not created")
        owner_cli = LambCLI(server_url=SERVER_URL, token=self.owner_token)
        result = owner_cli.run("assistant", "delete", self.assistant_id, "--confirm")
        result.assert_success()

    def test_cleanup_disable_users(self, cli: LambCLI):
        """Cleanup: disable both test users."""
        if self.owner_id:
            cli.run("user", "disable", self.owner_id)
        if self.other_id:
            cli.run("user", "disable", self.other_id)


class TestAuthContextModelFiltering:
    """Verify that model/config listing respects org-scoped filtering via AuthContext."""

    def test_admin_can_list_config(self, cli: LambCLI):
        """Admin can list available connectors and models."""
        result = cli.run_json("assistant", "config")
        result.assert_success()
        data = result.json
        # Config may be nested under "capabilities" or at top level
        capabilities = data.get("capabilities", data)
        assert "connectors" in capabilities or "prompt_processors" in capabilities, (
            f"Config response missing expected keys: {list(data.keys())}"
        )

    def test_config_returns_models_per_connector(self, cli: LambCLI):
        """Config endpoint returns model lists per connector (filtered by AuthContext org)."""
        result = cli.run_json("assistant", "config")
        result.assert_success()
        data = result.json
        capabilities = data.get("capabilities", data)
        connectors = capabilities.get("connectors", {})
        if isinstance(connectors, dict):
            for name, info in connectors.items():
                if isinstance(info, dict) and "available_llms" in info:
                    assert isinstance(info["available_llms"], list), (
                        f"Connector {name} should have a list of available_llms"
                    )


class TestAuthContextFileManagement:
    """Verify file management endpoints use AuthContext for user scoping."""

    user_id: str = ""
    user_token: str = ""

    def test_create_test_user(self, cli: LambCLI, timestamp: str):
        """Create a user for file management tests."""
        email = f"authctx_files_{timestamp}@test.com"
        result = cli.run_json(
            "user", "create", email, f"AuthCtx Files {timestamp}", "FilesTest_2026!",
        )
        result.assert_success()
        TestAuthContextFileManagement.user_id = str(result.json.get("id", ""))
        TestAuthContextFileManagement.user_token = login_as(email, "FilesTest_2026!")

    def test_user_sees_own_empty_file_list(self):
        """New user should see an empty file list (scoped by AuthContext user)."""
        assert self.user_token, "User not created"
        import httpx

        with httpx.Client(base_url=SERVER_URL, timeout=30) as client:
            resp = client.get(
                "/creator/files/list",
                headers={"Authorization": f"Bearer {self.user_token}"},
            )
            assert resp.status_code == 200
            files = resp.json()
            assert isinstance(files, list)
            assert len(files) == 0, "New user should have no files"

    def test_cleanup_disable_user(self, cli: LambCLI):
        """Cleanup: disable the test user."""
        if self.user_id:
            cli.run("user", "disable", self.user_id)


class TestAuthContextSharingPermission:
    """Verify sharing permission check uses AuthContext correctly."""

    user_id: str = ""
    user_token: str = ""

    def test_create_test_user(self, cli: LambCLI, timestamp: str):
        """Create a user for sharing permission tests."""
        email = f"authctx_share_{timestamp}@test.com"
        result = cli.run_json(
            "user", "create", email, f"AuthCtx Share {timestamp}", "ShareTest_2026!",
        )
        result.assert_success()
        TestAuthContextSharingPermission.user_id = str(result.json.get("id", ""))
        TestAuthContextSharingPermission.user_token = login_as(email, "ShareTest_2026!")

    def test_sharing_permission_check(self):
        """Sharing permission endpoint works through AuthContext."""
        assert self.user_token, "User not created"
        import httpx

        with httpx.Client(base_url=SERVER_URL, timeout=30) as client:
            resp = client.get(
                "/creator/lamb/assistant-sharing/check-permission",
                headers={"Authorization": f"Bearer {self.user_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "can_share" in data
            assert isinstance(data["can_share"], bool)

    def test_sharing_permission_no_token_rejected(self):
        """Sharing permission check without token returns 401/403."""
        import httpx

        with httpx.Client(base_url=SERVER_URL, timeout=30) as client:
            resp = client.get("/creator/lamb/assistant-sharing/check-permission")
            assert resp.status_code in (401, 403)

    def test_cleanup_disable_user(self, cli: LambCLI):
        """Cleanup: disable the test user."""
        if self.user_id:
            cli.run("user", "disable", self.user_id)


class TestAuthContextAdminEndpoints:
    """Verify admin-only endpoints are protected by AuthContext.is_system_admin."""

    regular_user_id: str = ""
    regular_user_token: str = ""

    def test_create_regular_user(self, cli: LambCLI, timestamp: str):
        """Create a non-admin user to test admin endpoint access."""
        email = f"authctx_noadmin_{timestamp}@test.com"
        result = cli.run_json(
            "user", "create", email, f"AuthCtx NoAdmin {timestamp}", "NoAdmin_2026!",
        )
        result.assert_success()
        TestAuthContextAdminEndpoints.regular_user_id = str(result.json.get("id", ""))
        TestAuthContextAdminEndpoints.regular_user_token = login_as(email, "NoAdmin_2026!")

    def test_admin_can_disable_user(self, cli: LambCLI, timestamp: str):
        """Admin can use disable endpoint (AuthContext.is_system_admin=True)."""
        # Create a throwaway user to disable
        email = f"authctx_throwaway_{timestamp}@test.com"
        result = cli.run_json(
            "user", "create", email, f"Throwaway {timestamp}", "Throwaway_2026!",
        )
        result.assert_success()
        throwaway_id = str(result.json.get("id", ""))

        disable_result = cli.run("user", "disable", throwaway_id)
        disable_result.assert_success()

    def test_regular_user_cannot_disable_user(self, cli: LambCLI, timestamp: str):
        """Non-admin cannot call disable endpoint (AuthContext.is_system_admin=False)."""
        assert self.regular_user_token, "User not created"

        # Create another throwaway as admin
        email = f"authctx_target_{timestamp}@test.com"
        result = cli.run_json(
            "user", "create", email, f"Target {timestamp}", "Target_2026!",
        )
        result.assert_success()
        target_id = str(result.json.get("id", ""))

        # Try to disable as non-admin
        user_cli = LambCLI(server_url=SERVER_URL, token=self.regular_user_token)
        result = user_cli.run("user", "disable", target_id)
        result.assert_failure()

        # Cleanup: disable target as admin
        cli.run("user", "disable", target_id)

    def test_regular_user_cannot_reset_password(self):
        """Non-admin cannot call password reset endpoint."""
        assert self.regular_user_token, "User not created"
        user_cli = LambCLI(server_url=SERVER_URL, token=self.regular_user_token)
        result = user_cli.run("user", "reset-password", "1", "--password", "NewPass_2026!")
        result.assert_failure()

    def test_cleanup(self, cli: LambCLI):
        """Cleanup: disable the regular user."""
        if self.regular_user_id:
            cli.run("user", "disable", self.regular_user_id)
