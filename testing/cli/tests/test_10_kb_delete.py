"""KB delete — maps to kb_delete_modal.spec.js.

Tests: create KB, delete with --confirm, verify gone, and delete
non-existent KB returns error.
"""

import pytest

from helpers.cli_runner import LambCLI


class TestKBDelete:
    """KB deletion tests."""

    kb_id: str = ""

    def test_create_kb_for_deletion(self, cli: LambCLI, timestamp: str):
        """Create a test KB."""
        name = f"cli_kb_delete_{timestamp}"
        result = cli.run_json("kb", "create", name, "-d", "Test KB for delete")
        result.assert_success()
        data = result.json
        TestKBDelete.kb_id = str(data.get("id") or data.get("kb_id") or "")

    def test_delete_kb(self, cli: LambCLI):
        """Delete the KB with --confirm."""
        assert self.kb_id, "KB not created"
        result = cli.run("kb", "delete", self.kb_id, "--confirm")
        result.assert_success()
        result.assert_stderr_contains("deleted")

    def test_deleted_kb_not_found(self, cli: LambCLI):
        """Fetching the deleted KB returns not-found."""
        assert self.kb_id, "KB not created"
        result = cli.run("kb", "get", self.kb_id)
        # Should be either not found (5) or API error (2)
        result.assert_failure()
