"""YouTube ingestion — maps to youtube_titles.spec.js.

Tests: create KB, ingest YouTube transcript, verify file has descriptive title, cleanup.
"""

import os
import time

import pytest

from helpers.cli_runner import LambCLI

VIDEO_URL = os.getenv("VIDEO_URL", "https://www.youtube.com/watch?v=YA9FlHLE9ts")
VIDEO_LANG = os.getenv("VIDEO_LANG", "es")


class TestYouTubeIngest:
    """Sequential YouTube ingestion tests."""

    kb_id: str = ""

    def test_create_kb(self, cli: LambCLI, timestamp: str):
        """Create a KB for YouTube ingestion."""
        name = f"cli_yt_kb_{timestamp}"
        result = cli.run_json("kb", "create", name, "-d", "YouTube ingestion test")
        result.assert_success()
        data = result.json
        TestYouTubeIngest.kb_id = str(data.get("id") or data.get("kb_id") or "")

    def test_ingest_youtube(self, cli: LambCLI):
        """Ingest a YouTube transcript."""
        assert self.kb_id, "KB not created"
        result = cli.run(
            "kb", "ingest", self.kb_id,
            "-p", "youtube_transcript_ingest",
            "--youtube", VIDEO_URL,
            "--param", f"language={VIDEO_LANG}",
        )
        result.assert_success()
        result.assert_stderr_contains("ingestion")

    @pytest.mark.slow
    def test_file_has_descriptive_title(self, cli: LambCLI):
        """The ingested file should have a descriptive name, not just the video ID."""
        assert self.kb_id, "KB not created"
        time.sleep(5)
        result = cli.run_json("kb", "get", self.kb_id)
        result.assert_success()
        data = result.json
        files = data.get("files", [])
        assert len(files) > 0, "KB should have files after YouTube ingestion"

        # Extract the video ID from the URL
        video_id = VIDEO_URL.split("v=")[-1].split("&")[0] if "v=" in VIDEO_URL else ""

        filename = files[0].get("filename", "")
        assert filename, "File should have a filename"
        # The filename should not be just the video ID
        is_just_id = filename.strip() in (video_id, f"{video_id}.txt")
        has_multiple_words = len(filename.split()) > 1 or len(filename.split("_")) > 1
        assert not is_just_id or has_multiple_words, (
            f"Filename should be descriptive, got: {filename}"
        )

    def test_cleanup_delete_kb(self, cli: LambCLI):
        """Delete the KB."""
        assert self.kb_id, "KB not created"
        result = cli.run("kb", "delete", self.kb_id, "--confirm")
        result.assert_success()
