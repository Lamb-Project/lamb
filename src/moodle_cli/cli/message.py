"""Message commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.message import MessageService
from moodle_cli.services.user import UserService


@click.group()
def message() -> None:
    """Messaging."""


@message.command()
@click.argument("user_id", type=int)
@click.argument("text")
@pass_context
@handle_errors
def send(ctx: MoodleContext, user_id: int, text: str) -> None:
    """Send a message to a user."""
    svc = MessageService(ctx.get_client())
    msg_id = svc.send_message(user_id, text)
    console.print(f"[green]Sent message {msg_id} to user {user_id}[/green]")


@message.command("list")
@click.option("--from-user", type=int, default=0, help="Filter by sender user ID")
@pass_context
@handle_errors
def list_messages(ctx: MoodleContext, from_user: int) -> None:
    """List recent messages."""
    client = ctx.get_client()
    me = UserService(client).get_me()
    svc = MessageService(client)
    msgs = svc.get_messages(me.id, user_id_from=from_user)
    if ctx.json_output:
        render_json([m.model_dump() for m in msgs])
    else:
        rows = [{"ID": m.id, "From": m.useridfrom, "Text": m.text[:80], "Time": m.timecreated} for m in msgs]
        render_table(rows, title=f"Messages ({len(rows)})")


@message.command()
@pass_context
@handle_errors
def conversations(ctx: MoodleContext) -> None:
    """List conversations."""
    client = ctx.get_client()
    me = UserService(client).get_me()
    svc = MessageService(client)
    convs = svc.get_conversations(me.id)
    if ctx.json_output:
        render_json([c.model_dump() for c in convs])
    else:
        rows = [
            {"ID": c.id, "Name": c.name or "(unnamed)", "Members": c.membercount, "Unread": c.unreadcount}
            for c in convs
        ]
        render_table(rows, title=f"Conversations ({len(rows)})")
