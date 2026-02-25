"""Tests for analytics commands."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()

SAMPLE_CHATS = {
    "chats": [
        {
            "id": "chat-1",
            "title": "Math help",
            "user_id": "u1",
            "user_name": "Alice",
            "user_email": "alice@example.com",
            "message_count": 5,
            "created_at": "2024-01-10T10:00:00Z",
            "updated_at": "2024-01-10T10:30:00Z",
        },
        {
            "id": "chat-2",
            "title": "History essay",
            "user_id": "u2",
            "user_name": "Bob",
            "user_email": "bob@example.com",
            "message_count": 12,
            "created_at": "2024-01-11T09:00:00Z",
            "updated_at": "2024-01-11T09:45:00Z",
        },
    ],
    "total": 2,
    "page": 1,
    "per_page": 20,
    "total_pages": 1,
}

SAMPLE_CHAT_DETAIL = {
    "id": "chat-1",
    "title": "Math help",
    "user": {"id": "u1", "name": "Alice", "email": "alice@example.com"},
    "created_at": "2024-01-10T10:00:00Z",
    "updated_at": "2024-01-10T10:30:00Z",
    "messages": [
        {"id": "m1", "role": "user", "content": "What is 2+2?", "timestamp": "2024-01-10T10:00:00Z"},
        {"id": "m2", "role": "assistant", "content": "2+2 equals 4.", "timestamp": "2024-01-10T10:00:05Z"},
    ],
}

SAMPLE_STATS = {
    "assistant_id": 1,
    "period": {"start": None, "end": None},
    "stats": {
        "total_chats": 25,
        "unique_users": 10,
        "total_messages": 150,
        "avg_messages_per_chat": 6.0,
    },
}

SAMPLE_TIMELINE = {
    "assistant_id": 1,
    "period": "day",
    "data": [
        {"date": "2024-01-10", "chat_count": 5, "message_count": 30},
        {"date": "2024-01-11", "chat_count": 8, "message_count": 45},
        {"date": "2024-01-12", "chat_count": 3, "message_count": 18},
    ],
}


class TestAnalyticsChats:
    def test_chats_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_CHATS)
        result = runner.invoke(app, ["analytics", "chats", "1"])
        assert result.exit_code == 0
        assert "Math help" in result.output
        assert "History essay" in result.output

    def test_chats_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_CHATS)
        result = runner.invoke(app, ["analytics", "chats", "1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["id"] == "chat-1"

    def test_chats_with_filters(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_CHATS)
        result = runner.invoke(
            app,
            [
                "analytics", "chats", "1",
                "--user-id", "u1",
                "--search", "math",
                "--start-date", "2024-01-01",
                "--end-date", "2024-01-31",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "user_id=u1" in str(req.url)
        assert "search_content=math" in str(req.url)

    def test_chats_with_pagination(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_CHATS)
        result = runner.invoke(app, ["analytics", "chats", "1", "--page", "2", "--per-page", "10"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "page=2" in str(req.url)
        assert "per_page=10" in str(req.url)


class TestAnalyticsChatDetail:
    def test_chat_detail_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_CHAT_DETAIL)
        result = runner.invoke(app, ["analytics", "chat-detail", "1", "chat-1"])
        assert result.exit_code == 0
        assert "Math help" in result.output
        assert "Alice" in result.output

    def test_chat_detail_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_CHAT_DETAIL)
        result = runner.invoke(app, ["analytics", "chat-detail", "1", "chat-1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "chat-1"
        assert len(data["messages"]) == 2

    def test_chat_detail_not_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=404, json={"detail": "Chat not found"})
        result = runner.invoke(app, ["analytics", "chat-detail", "1", "chat-999"])
        assert result.exit_code != 0


class TestAnalyticsStats:
    def test_stats_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_STATS)
        result = runner.invoke(app, ["analytics", "stats", "1"])
        assert result.exit_code == 0
        assert "25" in result.output
        assert "10" in result.output

    def test_stats_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_STATS)
        result = runner.invoke(app, ["analytics", "stats", "1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["stats"]["total_chats"] == 25
        assert data["stats"]["unique_users"] == 10

    def test_stats_with_dates(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_STATS)
        result = runner.invoke(
            app,
            ["analytics", "stats", "1", "--start-date", "2024-01-01", "--end-date", "2024-01-31"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "start_date=2024-01-01" in str(req.url)
        assert "end_date=2024-01-31" in str(req.url)


class TestAnalyticsTimeline:
    def test_timeline_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TIMELINE)
        result = runner.invoke(app, ["analytics", "timeline", "1"])
        assert result.exit_code == 0
        assert "2024-01-10" in result.output
        assert "2024-01-11" in result.output

    def test_timeline_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TIMELINE)
        result = runner.invoke(app, ["analytics", "timeline", "1", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["data"]) == 3
        assert data["period"] == "day"

    def test_timeline_with_period(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TIMELINE)
        result = runner.invoke(app, ["analytics", "timeline", "1", "--period", "week"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "period=week" in str(req.url)

    def test_timeline_with_dates(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_TIMELINE)
        result = runner.invoke(
            app,
            ["analytics", "timeline", "1", "--start-date", "2024-01-01", "--end-date", "2024-01-31"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert "start_date=2024-01-01" in str(req.url)
