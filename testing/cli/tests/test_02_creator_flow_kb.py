"""Knowledge base CRUD + ingest + query — maps to creator_flow.spec.js (KB part).

Creates a KB, uploads a fixture file, queries it, then deletes it.
"""

import time
from pathlib import Path

import pytest

from helpers.cli_runner import LambCLI


class TestCreatorFlowKB:
    """Sequential KB lifecycle tests."""

    kb_id: str = ""

    def test_create_kb(self, cli: LambCLI, timestamp: str):
        """Create a knowledge base."""
        name = f"cli_kb_{timestamp}"
        result = cli.run_json("kb", "create", name, "-d", "CLI E2E knowledge base")
        result.assert_success()
        data = result.json
        kb_id = data.get("id") or data.get("kb_id")
        assert kb_id, "KB creation should return an id"
        TestCreatorFlowKB.kb_id = str(kb_id)

    def test_get_kb(self, cli: LambCLI):
        """Get the KB detail by ID."""
        assert self.kb_id, "KB not created"
        result = cli.run_json("kb", "get", self.kb_id)
        result.assert_success()
        data = result.json
        assert data.get("id") is not None

    def test_upload_fixture_file(self, cli: LambCLI, fixture_file_path: Path):
        """Upload the ikasiker_fixture.txt file."""
        assert self.kb_id, "KB not created"
        result = cli.run("kb", "upload", self.kb_id, str(fixture_file_path))
        result.assert_success()
        result.assert_stderr_contains("uploaded")

    @pytest.mark.slow
    def test_query_kb(self, cli: LambCLI):
        """Query the KB for content from the fixture file."""
        assert self.kb_id, "KB not created"
        # Wait for ingestion to complete
        time.sleep(5)
        result = cli.run_json(
            "kb", "query", self.kb_id,
            "Cuantas becas Ikasiker se convocan?",
        )
        result.assert_success()
        # The response should contain results (list or dict with results key)
        data = result.json
        results = data if isinstance(data, list) else data.get("results", [])
        assert len(results) > 0, "Query should return at least one result"

    def test_delete_kb(self, cli: LambCLI):
        """Delete the knowledge base."""
        assert self.kb_id, "KB not created"
        result = cli.run("kb", "delete", self.kb_id, "--confirm")
        result.assert_success()
        result.assert_stderr_contains("deleted")
