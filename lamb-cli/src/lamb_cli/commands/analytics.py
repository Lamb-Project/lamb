"""Assistant analytics commands — lamb analytics *."""

from __future__ import annotations

from typing import Optional

import typer

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output

app = typer.Typer(help="View assistant analytics.")

CHAT_LIST_COLUMNS = [
    ("id", "ID"),
    ("title", "Title"),
    ("user_name", "User"),
    ("message_count", "Messages"),
    ("created_at", "Created At"),
]

CHAT_DETAIL_FIELDS = [
    ("id", "ID"),
    ("title", "Title"),
    ("user_name", "User"),
    ("user_email", "Email"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]

STATS_FIELDS = [
    ("total_chats", "Total Chats"),
    ("unique_users", "Unique Users"),
    ("total_messages", "Total Messages"),
    ("avg_messages_per_chat", "Avg Messages/Chat"),
]

TIMELINE_COLUMNS = [
    ("date", "Date"),
    ("chat_count", "Chats"),
    ("message_count", "Messages"),
]

MESSAGE_COLUMNS = [
    ("role", "Role"),
    ("content", "Content"),
]


def _flatten_stats(resp: dict) -> dict:
    """Flatten a nested stats response into a single dict."""
    stats = resp.get("stats", {})
    return {
        "total_chats": stats.get("total_chats", 0),
        "unique_users": stats.get("unique_users", 0),
        "total_messages": stats.get("total_messages", 0),
        "avg_messages_per_chat": stats.get("avg_messages_per_chat", 0.0),
    }


@app.command("chats")
def list_chats(
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    page: int = typer.Option(1, "--page", help="Page number."),
    per_page: int = typer.Option(20, "--per-page", help="Items per page."),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="Filter by user ID."),
    search: Optional[str] = typer.Option(None, "--search", help="Search chat content."),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="Filter from date (ISO format)."),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="Filter until date (ISO format)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List chats for an assistant."""
    fmt = output or get_output_format()
    params: dict = {"page": page, "per_page": per_page}
    if user_id is not None:
        params["user_id"] = user_id
    if search is not None:
        params["search_content"] = search
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    with get_client() as client:
        resp = client.get(f"/creator/analytics/assistant/{assistant_id}/chats", params=params)
    chats = resp.get("chats", [])
    format_output(chats, CHAT_LIST_COLUMNS, fmt)


@app.command("chat-detail")
def chat_detail(
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    chat_id: str = typer.Argument(..., help="Chat ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get full chat detail with messages."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/analytics/assistant/{assistant_id}/chats/{chat_id}")
    if fmt == "json":
        format_output(data, CHAT_DETAIL_FIELDS, fmt)
        return
    # Flatten user info for display
    user = data.get("user", {})
    display = {**data, "user_name": user.get("name", ""), "user_email": user.get("email", "")}
    format_output(display, CHAT_DETAIL_FIELDS, fmt, detail_fields=CHAT_DETAIL_FIELDS)
    # Show messages
    messages = data.get("messages", [])
    if messages and fmt != "plain":
        format_output(messages, MESSAGE_COLUMNS, fmt)


@app.command("stats")
def stats(
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="Stats from date (ISO format)."),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="Stats until date (ISO format)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get usage statistics for an assistant."""
    fmt = output or get_output_format()
    params: dict = {}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    with get_client() as client:
        resp = client.get(f"/creator/analytics/assistant/{assistant_id}/stats", params=params)
    if fmt == "json":
        format_output(resp, STATS_FIELDS, fmt)
        return
    flat = _flatten_stats(resp)
    format_output(flat, STATS_FIELDS, fmt, detail_fields=STATS_FIELDS)


@app.command("timeline")
def timeline(
    assistant_id: int = typer.Argument(..., help="Assistant ID."),
    period: str = typer.Option("day", "--period", help="Aggregation period: day, week, month."),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="From date (ISO format)."),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="Until date (ISO format)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get activity timeline for an assistant."""
    fmt = output or get_output_format()
    params: dict = {"period": period}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    with get_client() as client:
        resp = client.get(f"/creator/analytics/assistant/{assistant_id}/timeline", params=params)
    if fmt == "json":
        format_output(resp, TIMELINE_COLUMNS, fmt)
        return
    data = resp.get("data", [])
    format_output(data, TIMELINE_COLUMNS, fmt)
