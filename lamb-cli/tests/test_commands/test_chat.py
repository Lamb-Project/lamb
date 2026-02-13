"""Tests for chat command."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()


def _make_sse_chunks(*texts, chat_id=None):
    """Build SSE chunk strings for testing."""
    chunks = []
    for text in texts:
        data = {"choices": [{"delta": {"content": text}}]}
        if chat_id:
            data["chat_id"] = chat_id
        chunks.append(f"data: {json.dumps(data)}\n\n")
    chunks.append("data: [DONE]\n\n")
    return chunks


class TestChatSingleMessage:
    def test_single_message(self, mock_token):
        chunks = _make_sse_chunks("Hello ", "world!")
        mock_client = MagicMock()
        mock_client.stream_post.return_value = iter(chunks)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("lamb_cli.commands.chat.get_client", return_value=mock_client):
            result = runner.invoke(app, ["chat", "1", "--message", "Hi"])

        assert result.exit_code == 0
        assert "Hello " in result.output
        assert "world!" in result.output

        # Verify the request
        mock_client.stream_post.assert_called_once()
        call_kwargs = mock_client.stream_post.call_args
        body = call_kwargs.kwargs["json"]
        assert body["model"] == "lamb_assistant.1"
        assert body["messages"] == [{"role": "user", "content": "Hi"}]
        assert body["stream"] is True
        assert body["persist_chat"] is True

    def test_single_message_json_output(self, mock_token):
        chunks = _make_sse_chunks("Response text")
        mock_client = MagicMock()
        mock_client.stream_post.return_value = iter(chunks)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("lamb_cli.commands.chat.get_client", return_value=mock_client):
            result = runner.invoke(app, ["chat", "1", "--message", "test"])

        assert result.exit_code == 0
        assert "Response text" in result.output


class TestChatNoPersist:
    def test_no_persist_flag(self, mock_token):
        chunks = _make_sse_chunks("ok")
        mock_client = MagicMock()
        mock_client.stream_post.return_value = iter(chunks)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("lamb_cli.commands.chat.get_client", return_value=mock_client):
            result = runner.invoke(app, ["chat", "1", "--message", "Hi", "--no-persist"])

        assert result.exit_code == 0
        body = mock_client.stream_post.call_args.kwargs["json"]
        assert body["persist_chat"] is False


class TestChatWithChatId:
    def test_chat_id_passed(self, mock_token):
        chunks = _make_sse_chunks("continued")
        mock_client = MagicMock()
        mock_client.stream_post.return_value = iter(chunks)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("lamb_cli.commands.chat.get_client", return_value=mock_client):
            result = runner.invoke(
                app, ["chat", "1", "--message", "more", "--chat-id", "abc-123"]
            )

        assert result.exit_code == 0
        body = mock_client.stream_post.call_args.kwargs["json"]
        assert body["chat_id"] == "abc-123"


class TestChatNoMessage:
    def test_pipe_stdin(self, mock_token):
        chunks = _make_sse_chunks("piped response")
        mock_client = MagicMock()
        mock_client.stream_post.return_value = iter(chunks)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("lamb_cli.commands.chat.get_client", return_value=mock_client):
            result = runner.invoke(app, ["chat", "1"], input="Hello from pipe\n")

        assert result.exit_code == 0
        assert "piped response" in result.output

    def test_empty_stdin_fails(self, mock_token):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("lamb_cli.commands.chat.get_client", return_value=mock_client):
            result = runner.invoke(app, ["chat", "1"], input="")

        assert result.exit_code == 1


class TestChatEndpoint:
    def test_correct_endpoint(self, mock_token):
        chunks = _make_sse_chunks("hi")
        mock_client = MagicMock()
        mock_client.stream_post.return_value = iter(chunks)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("lamb_cli.commands.chat.get_client", return_value=mock_client):
            result = runner.invoke(app, ["chat", "42", "--message", "test"])

        assert result.exit_code == 0
        call_args = mock_client.stream_post.call_args
        assert call_args.args[0] == "/creator/assistant/42/chat/completions"
