"""URL ingestion — maps to url_ingest.spec.js.

Tests: create KB, ingest URL content via plugin, query after ingestion, cleanup.
"""

import os
import time

import pytest

from helpers.cli_runner import LambCLI

TEST_URL = os.getenv(
    "TEST_URL",
    "https://www.cervantesvirtual.com/obra-visor/the-political-constitution-of-the-spanish-monarchy-promulgated-in-cadiz-the-nineteenth-day-of-march--0/html/ffd04084-82b1-11df-acc7-002185ce6064_1.html",
)
TEST_QUERY = os.getenv(
    "TEST_QUERY",
    "What did the article number 14 in the Spanish Constitution of 1812 say?",
)
INGESTION_WAIT = int(os.getenv("INGESTION_WAIT_SECONDS", "5"))


class TestURLIngest:
    """Sequential URL ingestion tests."""

    kb_id: str = ""

    def test_create_kb(self, cli: LambCLI, timestamp: str):
        """Create a KB for URL ingestion."""
        name = f"cli_url_kb_{timestamp}"
        result = cli.run_json("kb", "create", name, "-d", "URL ingestion test")
        result.assert_success()
        data = result.json
        TestURLIngest.kb_id = str(data.get("id") or data.get("kb_id") or "")

    def test_ingest_url(self, cli: LambCLI):
        """Ingest URL content via the url_ingest plugin."""
        assert self.kb_id, "KB not created"
        result = cli.run(
            "kb", "ingest", self.kb_id,
            "-p", "url_ingest",
            "--url", TEST_URL,
        )
        result.assert_success()
        result.assert_stderr_contains("ingestion")

    @pytest.mark.slow
    @pytest.mark.xfail(reason="URL ingestion embedding may not complete in time")
    def test_query_after_ingest(self, cli: LambCLI):
        """Query the KB after URL ingestion."""
        assert self.kb_id, "KB not created"
        # URL ingestion can take a while — retry with increasing waits
        results = []
        for wait in [INGESTION_WAIT, 10, 15, 20]:
            time.sleep(wait)
            result = cli.run_json("kb", "query", self.kb_id, TEST_QUERY)
            result.assert_success()
            data = result.json
            results = data if isinstance(data, list) else data.get("results", [])
            if len(results) > 0:
                break
        assert len(results) > 0, "Query should return results after ingestion"

    def test_kb_has_files_after_ingest(self, cli: LambCLI):
        """The KB should have files after ingestion."""
        assert self.kb_id, "KB not created"
        result = cli.run_json("kb", "get", self.kb_id)
        result.assert_success()
        data = result.json
        files = data.get("files", [])
        assert len(files) > 0, "KB should have files after URL ingestion"

    def test_cleanup_delete_kb(self, cli: LambCLI):
        """Delete the KB."""
        assert self.kb_id, "KB not created"
        result = cli.run("kb", "delete", self.kb_id, "--confirm")
        result.assert_success()
