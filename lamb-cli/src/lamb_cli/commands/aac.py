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
    ("title", "Title"),
    ("skill_id", "Skill"),
    ("assistant_id", "Asst"),
    ("turn_count", "Turns"),
    ("tool_calls", "Tools"),
    ("tool_errors", "Errs"),
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
# Skills
# ---------------------------------------------------------------------------


@app.command("skills")
def list_skills(
    output: str = typer.Option(None, "-o", "--output", help="Output format."),
) -> None:
    """List available AAC skills."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get("/creator/aac/skills")
    skills = data if isinstance(data, list) else []
    if fmt == "json":
        print_json(skills)
    else:
        columns = [
            ("id", "Skill ID"),
            ("name", "Name"),
            ("description", "Description"),
            ("required_context", "Requires"),
        ]
        format_output(skills, columns, fmt)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


@app.command("start")
def start_session(
    assistant_id: Optional[int] = typer.Option(None, "--assistant", "-a", help="Existing assistant ID to work on."),
    skill: Optional[str] = typer.Option(None, "--skill", "-s", help="Skill to launch (e.g., improve-assistant, create-assistant)."),
    language: Optional[str] = typer.Option(None, "--language", "--lang", help="Language for agent responses (e.g., English, Catalan, Spanish)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Start a new AAC design session.

    Without --skill: starts a free-form conversation.
    With --skill: the agent leads — it runs startup analysis and speaks first.

    Examples:
        lamb aac start --skill improve-assistant --assistant 4 --lang Catalan
        lamb aac start --skill create-assistant --lang Spanish
        lamb aac start  # free-form, no skill
    """
    fmt = output or get_output_format()
    body: dict = {}
    if assistant_id is not None:
        body["assistant_id"] = assistant_id
    if skill:
        body["skill"] = skill
        context: dict = {}
        if assistant_id is not None:
            context["assistant_id"] = assistant_id
        if language:
            context["language"] = language
        body["context"] = context

    err_console.print("[dim]Starting session...[/dim]")
    with get_client(timeout=120.0) as client:
        data = client.post("/creator/aac/sessions", json=body)

    session_id = data.get("id", "")
    print_success(f"Session started: {session_id}")

    # If skill launched, show the agent's first message
    first_message = data.get("first_message")
    if first_message:
        console.print()
        console.print(Markdown(first_message))
        stats = data.get("stats", {})
        if stats:
            err_console.print(
                f"[dim]{stats.get('tool_calls', 0)} tool calls, "
                f"{stats.get('total_tool_time_ms', 0):.0f}ms tool time[/dim]"
            )
    elif data.get("error"):
        print_error(data["error"])
    elif fmt == "json":
        print_json(data)
    else:
        format_output(data, SESSION_LIST_COLUMNS, fmt, detail_fields=SESSION_DETAIL_FIELDS)


@app.command("sessions")
def list_sessions(
    skill: Optional[str] = typer.Option(None, "--skill", "-s", help="Filter by skill (e.g., about-lamb)."),
    assistant_id: Optional[int] = typer.Option(None, "--assistant", "-a", help="Filter by assistant ID."),
    with_errors: bool = typer.Option(False, "--errors", help="Only sessions with tool errors."),
    today: bool = typer.Option(False, "--today", help="Only sessions from today."),
    limit: int = typer.Option(50, "--limit", "-l", help="Max sessions to show."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List your AAC sessions with filters. Includes sessions from UI and CLI."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get("/creator/aac/sessions")
    sessions = data if isinstance(data, list) else []

    # Apply filters
    if skill:
        sessions = [s for s in sessions if s.get("skill_id") == skill]
    if assistant_id is not None:
        sessions = [s for s in sessions if s.get("assistant_id") == assistant_id]
    if with_errors:
        sessions = [s for s in sessions if (s.get("tool_errors") or 0) > 0]
    if today:
        from datetime import datetime
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        sessions = [s for s in sessions if (s.get("created_at") or "").startswith(today_str)]

    sessions = sessions[:limit]

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
    with get_client(timeout=300.0) as client:
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
                with get_client(timeout=300.0) as client:
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


@app.command("tools")
def show_tools(
    session_id: str = typer.Argument(..., help="Session ID."),
    detail: bool = typer.Option(False, "--detail", "-d", help="Show command and result summary."),
    artifacts: bool = typer.Option(False, "--artifacts", help="Group by artifact."),
    filter_type: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter by resource type (assistant, rubric, kb, test)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Show the tool audit log for a session."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/aac/sessions/{session_id}")
    audit = data.get("tool_audit", [])
    title = data.get("title", "")
    created = data.get("created_at", "")[:10]

    if fmt == "json":
        print_json(audit)
        return

    if not audit:
        console.print("[dim]No tool calls recorded for this session.[/dim]")
        return

    # Filter by type
    if filter_type:
        audit = [e for e in audit if any(a.get("type") == filter_type for a in e.get("artifacts", []))]

    console.print(f"\n[bold]Session:[/bold] {title or session_id[:12]} ({created})")
    console.print()

    if artifacts:
        # Group by artifact
        from collections import defaultdict
        groups = defaultdict(list)
        for e in audit:
            for a in e.get("artifacts", [{"type": "other", "id": None, "action": "?"}]):
                key = f"{a['type']}:{a.get('id', '*')}"
                groups[key].append((e, a["action"]))

        for key, events in sorted(groups.items()):
            console.print(f"  [bold]{key}[/bold]")
            for e, action in events:
                ts = e["ts"][11:19]
                ok = "[green]✓[/green]" if e["success"] else "[red]✗[/red]"
                ms = f"{e.get('elapsed_ms', 0):6.0f}ms"
                console.print(f"    {ts}  {action:10} {ok} {ms}")
                if detail and e.get("summary"):
                    console.print(f"    [dim]→ {e['summary']}[/dim]")
            console.print()
    else:
        # Chronological timeline
        for e in audit:
            ts = e["ts"][11:19]
            intent = e.get("intent", "")[:40]
            ok = "[green]✓[/green]" if e["success"] else "[red]✗[/red]"
            ms = f"{e.get('elapsed_ms', 0):6.0f}ms"
            arts = ", ".join(f"{a['type']}:{a.get('id','*')}" for a in e.get("artifacts", []))
            console.print(f"  {ts}  {intent:40} {ok} {ms}  {arts}")
            if detail:
                console.print(f"           [dim]$ {e['command']}[/dim]")
                if e.get("summary"):
                    console.print(f"           [dim]→ {e['summary']}[/dim]")

    # Summary
    total = len(audit)
    errors = sum(1 for e in audit if not e["success"])
    total_ms = sum(e.get("elapsed_ms", 0) for e in audit)
    all_arts = set()
    for e in audit:
        for a in e.get("artifacts", []):
            all_arts.add(f"{a['type']}:{a.get('id','*')}")
    console.print(f"\n  [dim]{total} tool calls | {errors} errors | {total_ms:.0f}ms total | artifacts: {', '.join(sorted(all_arts))}[/dim]")


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
