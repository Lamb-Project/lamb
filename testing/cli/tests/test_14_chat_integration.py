"""Chat integration — CLI-specific tests for ``lamb chat``.

Tests: create assistant, send single message, verify response,
test with non-existent assistant, test without auth, cleanup.
"""

import os

import pytest

from helpers.cli_runner import LambCLI

SERVER_URL = os.getenv("LAMB_SERVER_URL", "http://localhost:9099")
# Optional: pre-existing assistant ID for extended chat tests
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "")


class TestChatIntegration:
    """Sequential chat integration tests."""

    assistant_id: str = ""

    def test_create_assistant_for_chat(self, cli: LambCLI, timestamp: str):
        """Create a simple assistant for chat testing."""
        name = f"cli_chat_asst_{timestamp}"
        result = cli.run_json(
            "assistant", "create", name,
            "-d", "Chat test assistant",
            "-s", "You are a helpful assistant. Always respond with exactly: Hello from LAMB!",
            "--connector", "openai",
            "--rag-processor", "no_rag",
        )
        result.assert_success()
        TestChatIntegration.assistant_id = str(result.json.get("assistant_id", ""))

    def test_single_message_chat(self, cli: LambCLI):
        """Send a single message via --message and get a response."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run(
            "chat", self.assistant_id,
            "--message", "Hello",
            "--no-persist",
            timeout=90,
        )
        result.assert_success()
        # The assistant should respond with something (streamed to stdout)
        assert len(result.stdout.strip()) > 0, "Chat should return a response"

    def test_chat_response_is_text(self, cli: LambCLI):
        """Chat response should be plain text on stdout."""
        assert self.assistant_id, "Assistant not created"
        result = cli.run(
            "chat", self.assistant_id,
            "--message", "Say hi",
            "--no-persist",
            timeout=90,
        )
        result.assert_success()
        # Should not be JSON (it's streamed text)
        assert not result.stdout.strip().startswith("{"), (
            "Chat output should be plain text, not JSON"
        )

    def test_chat_nonexistent_assistant(self, cli: LambCLI):
        """Chatting with a non-existent assistant ID fails."""
        result = cli.run(
            "chat", "999999",
            "--message", "Hello",
            "--no-persist",
            timeout=30,
        )
        result.assert_failure()

    def test_chat_without_auth(self, server_url: str):
        """Chat without authentication fails."""
        no_auth_cli = LambCLI(server_url=server_url, token=None)
        result = no_auth_cli.run(
            "chat", "1",
            "--message", "Hello",
            "--no-persist",
            timeout=30,
        )
        result.assert_failure(expected_code=4)

    @pytest.mark.skipif(not ASSISTANT_ID, reason="ASSISTANT_ID not set")
    def test_chat_with_preconfigured_assistant(self, cli: LambCLI):
        """Chat with a pre-configured assistant (if ASSISTANT_ID is set)."""
        result = cli.run(
            "chat", ASSISTANT_ID,
            "--message", "Cuantas becas se convocan?",
            "--no-persist",
            timeout=90,
        )
        result.assert_success()
        assert len(result.stdout.strip()) > 0

    def test_cleanup_delete_assistant(self, cli: LambCLI):
        """Delete the chat test assistant."""
        if not self.assistant_id:
            pytest.skip("Assistant not created")
        result = cli.run("assistant", "delete", self.assistant_id, "--confirm")
        result.assert_success()
