"""Terminal chat command — lamb chat."""

from __future__ import annotations

import json
import sys
from typing import Optional

import typer

from lamb_cli.client import get_client
from lamb_cli.output import print_error


def _stream_response(client, assistant_id: int, message: str, chat_id: str | None, persist: bool) -> str | None:
    """Send a message and stream the response, returning the chat_id."""
    body: dict = {
        "model": f"lamb_assistant.{assistant_id}",
        "messages": [{"role": "user", "content": message}],
        "stream": True,
        "persist_chat": persist,
    }
    if chat_id:
        body["chat_id"] = chat_id

    returned_chat_id = chat_id
    for chunk in client.stream_post(
        f"/creator/assistant/{assistant_id}/chat/completions",
        json=body,
    ):
        for line in chunk.split("\n"):
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                data = json.loads(payload)
                delta = data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    sys.stdout.write(content)
                    sys.stdout.flush()
                # Capture chat_id from response if present
                if not returned_chat_id and data.get("chat_id"):
                    returned_chat_id = data["chat_id"]
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
    sys.stdout.write("\n")
    return returned_chat_id


def chat(
    assistant_id: int = typer.Argument(..., help="Assistant ID to chat with."),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Single message (non-interactive)."),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="Continue an existing chat."),
    no_persist: bool = typer.Option(False, "--no-persist", help="Don't save chat history on server."),
) -> None:
    """Chat with a learning assistant.

    Interactive mode: run without --message for a REPL. Type /quit to exit.
    Single-message mode: pass --message to send one message and exit.
    Pipe mode: pipe text via stdin (no --message, non-TTY).
    """
    persist = not no_persist

    with get_client() as client:
        if message:
            # Single-message mode
            _stream_response(client, assistant_id, message, chat_id, persist)
            return

        if sys.stdin.isatty():
            # Interactive REPL
            current_chat_id = chat_id
            try:
                while True:
                    try:
                        user_input = input("You: ")
                    except EOFError:
                        break
                    if user_input.strip().lower() in ("/quit", "/exit"):
                        break
                    if not user_input.strip():
                        continue
                    sys.stdout.write("Assistant: ")
                    current_chat_id = _stream_response(client, assistant_id, user_input, current_chat_id, persist)
            except KeyboardInterrupt:
                sys.stdout.write("\n")
        else:
            # Pipe mode — read all of stdin as the message
            pipe_message = sys.stdin.read().strip()
            if not pipe_message:
                print_error("No message provided via stdin.")
                raise typer.Exit(1)
            _stream_response(client, assistant_id, pipe_message, chat_id, persist)
