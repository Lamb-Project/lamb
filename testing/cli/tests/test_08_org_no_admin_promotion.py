"""Org without admin + role promotion — maps to org_no_admin_and_role_promotion.spec.js.

Tests: create org without admin, create org with admin, promote/demote
via org set-role, cleanup.
"""

import pytest

from helpers.cli_runner import LambCLI


class TestOrgNoAdminPromotion:
    """Sequential org creation and role promotion tests (issue #249)."""

    no_admin_org_slug: str = ""
    promo_org_slug: str = ""
    user_id: str = ""

    def test_create_org_without_admin(self, cli: LambCLI, timestamp: str):
        """Create an org without specifying an admin."""
        slug = f"no-admin-org-{timestamp}"
        name = f"No Admin Org {timestamp}"
        result = cli.run_json("org", "create", name, "-s", slug)
        result.assert_success()
        TestOrgNoAdminPromotion.no_admin_org_slug = slug

    def test_org_without_admin_in_list(self, cli: LambCLI):
        """The org without admin appears in the list."""
        assert self.no_admin_org_slug, "Org not created"
        result = cli.run_json("org", "list")
        result.assert_success()
        orgs = result.json
        if isinstance(orgs, dict):
            orgs = orgs.get("organizations", [])
        slugs = [o.get("slug", "") for o in orgs]
        assert self.no_admin_org_slug in slugs

    def test_create_user_for_promotion(self, cli: LambCLI, timestamp: str):
        """Create a user to test promotion."""
        email = f"promo_user_{timestamp}@test.com"
        name = f"Promo User {timestamp}"
        result = cli.run_json(
            "user", "create", email, name, "TestPromo_249!",
        )
        result.assert_success()
        TestOrgNoAdminPromotion.user_id = str(result.json.get("id", ""))

    def test_create_org_with_admin(self, cli: LambCLI, timestamp: str):
        """Create org with the test user as admin."""
        slug = f"promo-org-{timestamp}"
        name = f"Promo Org {timestamp}"
        args = ["org", "create", name, "-s", slug]
        if self.user_id:
            args += ["--admin-user-id", self.user_id]
        result = cli.run_json(*args)
        result.assert_success()
        TestOrgNoAdminPromotion.promo_org_slug = slug

    def test_demote_user_to_member(self, cli: LambCLI):
        """Demote user from admin to member."""
        assert self.promo_org_slug and self.user_id
        result = cli.run("org", "set-role", self.promo_org_slug, self.user_id, "member")
        result.assert_success()

    def test_promote_user_to_admin(self, cli: LambCLI):
        """Promote user back to admin."""
        assert self.promo_org_slug and self.user_id
        result = cli.run("org", "set-role", self.promo_org_slug, self.user_id, "admin")
        result.assert_success()

    def test_invalid_role_rejected(self, cli: LambCLI):
        """Setting an invalid role is rejected."""
        assert self.promo_org_slug and self.user_id
        result = cli.run("org", "set-role", self.promo_org_slug, self.user_id, "superuser")
        result.assert_failure(expected_code=1)

    def test_cleanup_delete_no_admin_org(self, cli: LambCLI):
        """Delete org without admin."""
        if not self.no_admin_org_slug:
            pytest.skip("Org not created")
        result = cli.run("org", "delete", self.no_admin_org_slug, "--confirm")
        result.assert_success()

    def test_cleanup_delete_promo_org(self, cli: LambCLI):
        """Delete promotion test org."""
        if not self.promo_org_slug:
            pytest.skip("Org not created")
        result = cli.run("org", "delete", self.promo_org_slug, "--confirm")
        result.assert_success()

    def test_cleanup_disable_user(self, cli: LambCLI):
        """Disable the test user."""
        if not self.user_id:
            pytest.skip("User not created")
        cli.run("user", "disable", self.user_id)
