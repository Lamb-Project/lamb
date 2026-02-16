"""Assistant CRUD — maps to creator_flow.spec.js (assistant part).

Creates an assistant, lists it, gets it, then deletes it.
"""

import pytest

from helpers.cli_runner import LambCLI


class TestCreatorFlowAssistant:
    """Sequential assistant lifecycle tests."""

    assistant_id: str = ""

    def test_create_assistant(self, cli: LambCLI, timestamp: str):
        """Create an assistant with explicit connector (no interactive wizard)."""
        name = f"cli_asst_{timestamp}"
        result = cli.run_json(
            "assistant", "create", name,
            "-d", "CLI E2E assistant",
            "-s", "You are a helpful assistant.",
            "--connector", "openai",
        )
        result.assert_success()
        data = result.json
        assert data.get("assistant_id"), "Should return assistant_id"
        TestCreatorFlowAssistant.assistant_id = str(data["assistant_id"])

    def test_list_assistants_contains_new(self, cli: LambCLI, timestamp: str):
        """The newly created assistant appears in the list."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run_json("assistant", "list")
        result.assert_success()
        assistants = result.json
        if isinstance(assistants, dict):
            assistants = assistants.get("assistants", [])
        ids = [str(a.get("id") or a.get("assistant_id", "")) for a in assistants]
        assert self.assistant_id in ids, (
            f"Assistant {self.assistant_id} not found in list"
        )

    def test_get_assistant(self, cli: LambCLI):
        """Get assistant detail returns expected fields."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run_json("assistant", "get", self.assistant_id)
        result.assert_success()
        data = result.json
        assert data.get("id") is not None or data.get("assistant_id") is not None
        assert data.get("name"), "Assistant should have a name"

    def test_get_assistant_has_system_prompt(self, cli: LambCLI):
        """Assistant detail includes the system prompt we set."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run_json("assistant", "get", self.assistant_id)
        result.assert_success()
        data = result.json
        assert "helpful assistant" in data.get("system_prompt", "").lower()

    def test_delete_assistant(self, cli: LambCLI):
        """Delete the assistant."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run("assistant", "delete", self.assistant_id, "--confirm")
        result.assert_success()
        result.assert_stderr_contains("deleted")
