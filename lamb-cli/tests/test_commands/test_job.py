"""Tests for ingestion job commands."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()

SAMPLE_JOBS = {
    "total": 3,
    "items": [
        {
            "id": "job-1",
            "original_filename": "chapter1.pdf",
            "status": "completed",
            "progress": {"percentage": 100},
            "created_at": "2025-01-15T10:00:00Z",
            "plugin_name": "file_upload",
        },
        {
            "id": "job-2",
            "original_filename": "notes.txt",
            "status": "processing",
            "progress": {"percentage": 45},
            "created_at": "2025-01-15T11:00:00Z",
            "plugin_name": "file_upload",
        },
        {
            "id": "job-3",
            "original_filename": "web_page",
            "status": "failed",
            "progress": {"percentage": 10},
            "created_at": "2025-01-15T12:00:00Z",
            "plugin_name": "web_scraper",
            "error_message": "Connection timeout",
        },
    ],
    "has_more": False,
}

SAMPLE_JOB_PROCESSING = {
    "id": "job-2",
    "original_filename": "notes.txt",
    "status": "processing",
    "progress": {"percentage": 45},
    "created_at": "2025-01-15T11:00:00Z",
    "plugin_name": "file_upload",
    "document_count": 3,
    "error_message": None,
    "processing_duration_seconds": 12.5,
}

SAMPLE_JOB_COMPLETED = {
    "id": "job-1",
    "original_filename": "chapter1.pdf",
    "status": "completed",
    "progress": {"percentage": 100},
    "created_at": "2025-01-15T10:00:00Z",
    "plugin_name": "file_upload",
    "document_count": 15,
    "error_message": None,
    "processing_duration_seconds": 45.3,
}

SAMPLE_JOB_FAILED = {
    "id": "job-3",
    "original_filename": "web_page",
    "status": "failed",
    "progress": {"percentage": 10},
    "created_at": "2025-01-15T12:00:00Z",
    "plugin_name": "web_scraper",
    "document_count": 0,
    "error_message": "Connection timeout",
    "processing_duration_seconds": 5.0,
}

SAMPLE_STATUS = {
    "total_jobs": 10,
    "by_status": {
        "completed": 7,
        "processing": 1,
        "failed": 2,
    },
    "currently_processing": 1,
    "recent_failures": [
        {"id": "job-3", "error_message": "Connection timeout"},
    ],
}


class TestJobList:
    def test_list_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_JOBS)
        result = runner.invoke(app, ["job", "list", "kb-1"])
        assert result.exit_code == 0
        assert "chapter1.pdf" in result.output
        assert "notes.txt" in result.output

    def test_list_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_JOBS)
        result = runner.invoke(app, ["job", "list", "kb-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3

    def test_list_plain(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_JOBS)
        result = runner.invoke(app, ["job", "list", "kb-1", "-o", "plain"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 3

    def test_list_with_filters(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"total": 0, "items": [], "has_more": False})
        result = runner.invoke(
            app,
            ["job", "list", "kb-1", "--status", "failed", "--limit", "5", "--offset", "10"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "status=failed" in str(req.url)
        assert "limit=5" in str(req.url)
        assert "offset=10" in str(req.url)

    def test_list_with_sort(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"total": 0, "items": [], "has_more": False})
        result = runner.invoke(
            app,
            ["job", "list", "kb-1", "--sort-by", "created_at", "--sort-order", "desc"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "sort_by=created_at" in str(req.url)
        assert "sort_order=desc" in str(req.url)


class TestJobGet:
    def test_get_processing(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_JOB_PROCESSING)
        result = runner.invoke(app, ["job", "get", "kb-1", "job-2"])
        assert result.exit_code == 0
        assert "processing" in result.output.lower()
        assert "notes.txt" in result.output

    def test_get_completed(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_JOB_COMPLETED)
        result = runner.invoke(app, ["job", "get", "kb-1", "job-1"])
        assert result.exit_code == 0
        assert "completed" in result.output.lower()

    def test_get_failed(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_JOB_FAILED)
        result = runner.invoke(app, ["job", "get", "kb-1", "job-3"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower()
        assert "Connection timeout" in result.output

    def test_get_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_JOB_COMPLETED)
        result = runner.invoke(app, ["job", "get", "kb-1", "job-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "job-1"
        assert data["status"] == "completed"


class TestJobRetry:
    def test_retry_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Retry started"})
        result = runner.invoke(app, ["job", "retry", "kb-1", "job-3"])
        assert result.exit_code == 0
        assert "retry" in result.output.lower()

    def test_retry_already_running(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=409, json={"detail": "Job is already running"})
        result = runner.invoke(app, ["job", "retry", "kb-1", "job-2"])
        assert result.exit_code != 0


class TestJobCancel:
    def test_cancel_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "Cancelled"})
        result = runner.invoke(app, ["job", "cancel", "kb-1", "job-2"])
        assert result.exit_code == 0
        assert "cancel" in result.output.lower()


class TestJobWatch:
    def test_watch_non_tty(self, httpx_mock, mock_token):
        """When stdout is not a TTY, should print a single status line."""
        httpx_mock.add_response(json=SAMPLE_JOB_COMPLETED)
        result = runner.invoke(app, ["job", "watch", "kb-1", "job-1"])
        assert result.exit_code == 0
        assert "job-1" in result.output
        assert "completed" in result.output

    @patch("lamb_cli.commands.job.time.sleep")
    def test_watch_polling_to_completed(self, mock_sleep, httpx_mock, mock_token):
        """Simulate polling: pending → processing → completed.

        CliRunner doesn't have a real TTY, so we test the non-TTY fallback path.
        The first call returns the status and exits.
        """
        httpx_mock.add_response(json=SAMPLE_JOB_COMPLETED)
        result = runner.invoke(app, ["job", "watch", "kb-1", "job-1"])
        assert result.exit_code == 0
        assert "completed" in result.output

    @patch("lamb_cli.commands.job.time.sleep")
    def test_watch_failed_job(self, mock_sleep, httpx_mock, mock_token):
        """Watch a failed job — non-TTY path."""
        httpx_mock.add_response(json=SAMPLE_JOB_FAILED)
        result = runner.invoke(app, ["job", "watch", "kb-1", "job-3"])
        assert result.exit_code == 0
        assert "failed" in result.output


class TestJobStatus:
    def test_status_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_STATUS)
        result = runner.invoke(app, ["job", "status", "kb-1"])
        assert result.exit_code == 0
        assert "10" in result.output  # total_jobs
        assert "1" in result.output   # currently_processing

    def test_status_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_STATUS)
        result = runner.invoke(app, ["job", "status", "kb-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_jobs"] == 10
        assert data["by_status"]["completed"] == 7

    def test_status_with_by_status(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_STATUS)
        result = runner.invoke(app, ["job", "status", "kb-1"])
        assert result.exit_code == 0
        # The by_status fields should be expanded
        assert "completed" in result.output.lower()
