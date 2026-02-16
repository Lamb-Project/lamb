"""Advanced assistant management — maps to advanced_assistants_management.spec.js.

Tests: create, update (description, connector), publish, unpublish, delete.
"""

import pytest

from helpers.cli_runner import LambCLI


class TestAdvancedAssistant:
    """Sequential advanced assistant management tests."""

    assistant_id: str = ""

    def test_create_base_assistant(self, cli: LambCLI, timestamp: str):
        """Create a base assistant for subsequent tests."""
        name = f"cli_adv_asst_{timestamp}"
        result = cli.run_json(
            "assistant", "create", name,
            "-d", "Advanced management CLI assistant",
            "-s", "You are a helpful assistant for advanced CLI tests.",
            "--connector", "openai",
        )
        result.assert_success()
        data = result.json
        assert data.get("assistant_id")
        TestAdvancedAssistant.assistant_id = str(data["assistant_id"])

    def test_update_description(self, cli: LambCLI):
        """Update the assistant description."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run(
            "assistant", "update", self.assistant_id,
            "-d", "Updated description via CLI",
        )
        result.assert_success()
        result.assert_stderr_contains("updated")

    def test_update_persisted(self, cli: LambCLI):
        """Verify the update persisted by re-fetching."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run_json("assistant", "get", self.assistant_id)
        result.assert_success()
        data = result.json
        assert "updated description via cli" in data.get("description", "").lower()

    def test_publish(self, cli: LambCLI):
        """Publish the assistant."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run("assistant", "publish", self.assistant_id)
        result.assert_success()
        result.assert_stderr_contains("published")

    def test_publish_status_persisted(self, cli: LambCLI):
        """Verify publish status is true."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run_json("assistant", "get", self.assistant_id)
        result.assert_success()
        data = result.json
        # The field may be 'published' (from API) or 'publish_status'
        pub = data.get("published", data.get("publish_status"))
        assert pub in (True, "true", "True", 1), (
            f"Expected published, got {pub}"
        )

    def test_unpublish(self, cli: LambCLI):
        """Unpublish the assistant."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run("assistant", "unpublish", self.assistant_id)
        result.assert_success()
        result.assert_stderr_contains("unpublished")

    def test_cleanup_delete(self, cli: LambCLI):
        """Delete the assistant."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run("assistant", "delete", self.assistant_id, "--confirm")
        result.assert_success()
