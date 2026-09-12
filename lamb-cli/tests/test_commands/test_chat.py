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
        chunks = _make_sse_chunks("Response text", chat_id="new-chat-id")
        mock_client = MagicMock()
        mock_client.stream_post.return_value = iter(chunks)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("lamb_cli.commands.chat.get_client", return_value=mock_client):
            result = runner.invoke(app, ["chat", "1", "--message", "test"])

        assert result.exit_code == 0
        assert "Response text" in result.stdout
        assert "Chat ID: new-chat-id" in result.stderr


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


def test_chat_id_from_real_stream_header(mock_token, mock_server_url, httpx_mock):
    for _ in range(2):
        httpx_mock.add_response(method='POST', url=mock_server_url + '/creator/assistant/1/chat/completions', headers={'X-Chat-Id':'header-chat'}, text=''.join(_make_sse_chunks('Hello')))
    result = runner.invoke(app,['chat','1','--message','Hi'])
    assert result.exit_code == 0
    assert result.stdout == 'Hello\n'
    assert 'Chat ID: header-chat' in result.stderr
    followup = runner.invoke(app,['chat','1','--message','Continue','--chat-id','header-chat'])
    assert followup.exit_code == 0
    assert json.loads(httpx_mock.get_requests()[-1].content)['chat_id'] == 'header-chat'


@pytest.mark.parametrize('args,seconds',[([],300.0),(['--timeout','600'],600.0)])
def test_chat_timeout_reaches_http_transport(mock_token,mock_server_url,httpx_mock,args,seconds):
    httpx_mock.add_response(text='data: [DONE]\n\n',headers={'content-type':'text/event-stream'})
    result=runner.invoke(app,['chat','1','--message','Hello',*args])
    assert result.exit_code==0
    request=httpx_mock.get_request()
    assert request.extensions['timeout']['read']==seconds


@pytest.mark.parametrize("value",["0","nan","inf"])
def test_chat_rejects_invalid_timeout(mock_token,value):
    result=runner.invoke(app,['chat','1','--message','Hello','--timeout',value])
    assert result.exit_code==2


def test_interrupted_chat_prints_returned_id_for_inspection(mock_token,mock_server_url,httpx_mock):
    import httpx
    from lamb_cli.errors import NetworkError
    class Interrupted(httpx.SyncByteStream):
        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"Partial"}}]}\n\n'
            raise httpx.ReadTimeout('slow response')
    httpx_mock.add_response(stream=Interrupted(),headers={'X-Chat-Id':'inspect-this-chat'})
    result=runner.invoke(app,['chat','1','--message','Hello'])
    assert isinstance(result.exception,NetworkError)
    assert 'Partial' in result.stdout
    assert 'Chat ID: inspect-this-chat' in result.stderr
    assert len(httpx_mock.get_requests())==1
