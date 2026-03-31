"""AAC (Agent-Assisted Creator) commands — lamb aac *."""

from __future__ import annotations

import json
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_json, print_success

app = typer.Typer(help="Agent-Assisted Creator — design assistants with AI help.")

console = Console()
err_console = Console(stderr=True)

SESSION_LIST_COLUMNS = [
    ("id", "Session ID"),
    ("assistant_id", "Assistant"),
    ("status", "Status"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]

SESSION_DETAIL_FIELDS = [
    ("id", "Session ID"),
    ("assistant_id", "Assistant"),
    ("status", "Status"),
    ("user_email", "User"),
    ("organization_id", "Org ID"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
    ("_turn_count", "Turns"),
]


def _enrich_session(s: dict) -> dict:
    """Add computed fields for display."""
    conv = s.get("conversation", [])
    s["_turn_count"] = len([m for m in conv if m.get("role") == "user"])
    return s


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


@app.command("start")
def start_session(
    assistant_id: Optional[int] = typer.Option(None, "--assistant", "-a", help="Existing assistant ID to refine."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Start a new AAC design session."""
    fmt = output or get_output_format()
    body: dict = {}
    if assistant_id is not None:
        body["assistant_id"] = assistant_id
    with get_client() as client:
        data = client.post("/creator/aac/sessions", json=body)
    session_id = data.get("id", "")
    print_success(f"Session started: {session_id}")
    if fmt == "json":
        print_json(data)
    else:
        format_output(data, SESSION_LIST_COLUMNS, fmt, detail_fields=SESSION_DETAIL_FIELDS)


@app.command("sessions")
def list_sessions(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List your AAC sessions."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get("/creator/aac/sessions")
    sessions = data if isinstance(data, list) else []
    if fmt == "json":
        print_json(sessions)
    else:
        format_output(sessions, SESSION_LIST_COLUMNS, fmt)


@app.command("get")
def get_session(
    session_id: str = typer.Argument(..., help="Session ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get session details."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/aac/sessions/{session_id}")
    if fmt == "json":
        print_json(data)
    else:
        format_output(_enrich_session(data), SESSION_LIST_COLUMNS, fmt, detail_fields=SESSION_DETAIL_FIELDS)


@app.command("delete")
def delete_session(
    session_id: str = typer.Argument(..., help="Session ID."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation."),
) -> None:
    """Archive a session."""
    if not confirm:
        typer.confirm(f"Delete session {session_id}?", abort=True)
    with get_client() as client:
        client.delete(f"/creator/aac/sessions/{session_id}")
    print_success(f"Session {session_id} archived.")


# ---------------------------------------------------------------------------
# Agent interaction
# ---------------------------------------------------------------------------


@app.command("message")
def send_message(
    session_id: str = typer.Argument(..., help="Session ID."),
    message: str = typer.Argument(..., help="Message to send to the agent."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Send a message to the agent and get a response."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.post(
            f"/creator/aac/sessions/{session_id}/message",
            json={"message": message},
        )
    if fmt == "json":
        print_json(data)
    else:
        response = data.get("response", "")
        console.print(Markdown(response))
        stats = data.get("stats", {})
        if stats:
            tc = stats.get("tool_calls", 0)
            err = stats.get("tool_errors", 0)
            ms = stats.get("total_tool_time_ms", 0)
            err_console.print(
                f"[dim]{tc} tool calls ({err} errors), {ms:.0f}ms tool time, "
                f"model: {stats.get('model', '?')}[/dim]"
            )


@app.command("chat")
def interactive_chat(
    session_id: str = typer.Argument(..., help="Session ID."),
) -> None:
    """Interactive chat with the AAC agent.

    Type messages, get agent responses. Type /quit to exit,
    /history to show conversation, /stats for session stats.
    """
    console.print(Panel.fit(
        f"[bold]AAC Agent[/bold] — Session: [cyan]{session_id[:12]}...[/cyan]\n"
        f"Type [bold]/quit[/bold] to exit, [bold]/history[/bold] for conversation.",
        border_style="blue",
    ))

    try:
        while True:
            try:
                user_input = console.input("[bold green]You:[/bold green] ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input in ("/quit", "/exit", "/q"):
                break

            if user_input == "/history":
                _show_history(session_id)
                continue

            if user_input == "/stats":
                _show_session(session_id)
                continue

            # Send message
            err_console.print("[dim]Thinking...[/dim]")
            try:
                with get_client() as client:
                    data = client.post(
                        f"/creator/aac/sessions/{session_id}/message",
                        json={"message": user_input},
                    )
                response = data.get("response", "")
                console.print()
                console.print(Markdown(response))
                stats = data.get("stats", {})
                if stats.get("tool_calls"):
                    err_console.print(
                        f"[dim]{stats['tool_calls']} tool calls, "
                        f"{stats.get('total_tool_time_ms', 0):.0f}ms[/dim]"
                    )
            except Exception as e:
                print_error(str(e))

    except KeyboardInterrupt:
        console.print()

    console.print("[dim]Session ended.[/dim]")


@app.command("history")
def show_history(
    session_id: str = typer.Argument(..., help="Session ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Show the conversation history for a session."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/aac/sessions/{session_id}")
    conversation = data.get("conversation", [])
    if fmt == "json":
        print_json(conversation)
    else:
        _print_conversation(conversation)


def _show_history(session_id: str) -> None:
    """Helper for interactive mode."""
    try:
        with get_client() as client:
            data = client.get(f"/creator/aac/sessions/{session_id}")
        _print_conversation(data.get("conversation", []))
    except Exception as e:
        print_error(str(e))


def _show_session(session_id: str) -> None:
    """Helper for interactive mode."""
    try:
        with get_client() as client:
            data = client.get(f"/creator/aac/sessions/{session_id}")
        s = _enrich_session(data)
        console.print(f"  Turns: [cyan]{s['_turn_count']}[/cyan]")
        console.print(f"  Status: [cyan]{s.get('status', '?')}[/cyan]")
        console.print(f"  Assistant: [cyan]{s.get('assistant_id', 'None')}[/cyan]")
    except Exception as e:
        print_error(str(e))


def _print_conversation(conversation: list[dict]) -> None:
    """Pretty-print a conversation."""
    for msg in conversation:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if role == "user":
            console.print(f"\n[bold green]You:[/bold green] {content}")
        elif role == "assistant":
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    args = fn.get("arguments", "")
                    console.print(f"[dim]  → tool: {args}[/dim]")
            elif content:
                console.print(f"\n[bold blue]Agent:[/bold blue]")
                console.print(Markdown(content))
        elif role == "tool":
            # Truncate tool results for display
            raw = msg.get("content", "")
            if len(raw) > 200:
                raw = raw[:200] + "..."
            console.print(f"[dim]  ← {raw}[/dim]")
