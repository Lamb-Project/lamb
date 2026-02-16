"""KB file management — maps to kb_detail_modals.spec.js.

Tests: create KB, upload file, list files via get, delete file, cleanup.
"""

import time
from pathlib import Path

import pytest

from helpers.cli_runner import LambCLI


class TestKBFileManagement:
    """Sequential KB file management tests."""

    kb_id: str = ""
    file_id: str = ""

    def test_create_kb(self, cli: LambCLI, timestamp: str):
        """Create a KB for file management tests."""
        name = f"cli_kb_files_{timestamp}"
        result = cli.run_json("kb", "create", name, "-d", "Test KB for file management")
        result.assert_success()
        data = result.json
        TestKBFileManagement.kb_id = str(data.get("id") or data.get("kb_id") or "")

    def test_upload_file(self, cli: LambCLI, fixture_file_path: Path):
        """Upload a file to the KB."""
        assert self.kb_id, "KB not created"
        result = cli.run("kb", "upload", self.kb_id, str(fixture_file_path))
        result.assert_success()
        result.assert_stderr_contains("uploaded")

    def test_get_kb_shows_files(self, cli: LambCLI):
        """Get KB detail in JSON shows files list."""
        assert self.kb_id, "KB not created"
        # Small wait for the upload to be processed
        time.sleep(2)
        result = cli.run_json("kb", "get", self.kb_id)
        result.assert_success()
        data = result.json
        files = data.get("files", [])
        assert len(files) > 0, "KB should have at least one file"
        TestKBFileManagement.file_id = str(files[0].get("id", ""))

    def test_delete_file(self, cli: LambCLI):
        """Delete the file from the KB."""
        assert self.kb_id and self.file_id, "KB or file not created"
        result = cli.run("kb", "delete-file", self.kb_id, self.file_id, "--confirm")
        result.assert_success()

    def test_cleanup_delete_kb(self, cli: LambCLI):
        """Delete the KB."""
        assert self.kb_id, "KB not created"
        result = cli.run("kb", "delete", self.kb_id, "--confirm")
        result.assert_success()
