"""Org creation options — maps to org_form_modal.spec.js.

Tests the CLI equivalents of org creation options:
creating with signup enabled/key, and basic org CRUD.
"""

import pytest

from helpers.cli_runner import LambCLI


class TestOrgCreateOptions:
    """Org creation option tests."""

    org_slug: str = ""

    def test_create_org_with_signup(self, cli: LambCLI, timestamp: str):
        """Create an org with signup enabled and a signup key."""
        slug = f"signup-org-{timestamp}"
        name = f"Signup Org {timestamp}"
        result = cli.run_json(
            "org", "create", name,
            "-s", slug,
            "--signup-enabled",
            "--signup-key", f"test-key-{timestamp}",
        )
        result.assert_success()
        TestOrgCreateOptions.org_slug = slug

    def test_cleanup_delete_org(self, cli: LambCLI):
        """Delete the signup test org."""
        if not self.org_slug:
            pytest.skip("Org not created")
        result = cli.run("org", "delete", self.org_slug, "--confirm")
        result.assert_success()
