"""Forum commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.forum import ForumService


@click.group()
def forum() -> None:
    """Forum management."""


@forum.command("list")
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def list_forums(ctx: MoodleContext, course_id: int) -> None:
    """List forums in a course."""
    svc = ForumService(ctx.get_client())
    forums = svc.list_forums(course_id)
    if ctx.json_output:
        render_json([f.model_dump() for f in forums])
    else:
        rows = [{"ID": f.id, "Name": f.name, "Type": f.type} for f in forums]
        render_table(rows, title=f"Forums ({len(rows)})")


@forum.command()
@click.argument("forum_id", type=int)
@pass_context
@handle_errors
def discussions(ctx: MoodleContext, forum_id: int) -> None:
    """List discussions in a forum."""
    svc = ForumService(ctx.get_client())
    discs = svc.get_discussions(forum_id)
    if ctx.json_output:
        render_json([d.model_dump() for d in discs])
    else:
        rows = [{"ID": d.id, "Subject": d.subject or d.name, "Author": d.userfullname} for d in discs]
        render_table(rows, title=f"Discussions ({len(rows)})")


@forum.command()
@click.option("--forum-id", required=True, type=int)
@click.option("--subject", required=True)
@click.option("--message", required=True)
@pass_context
@handle_errors
def post(ctx: MoodleContext, forum_id: int, subject: str, message: str) -> None:
    """Post a new discussion to a forum."""
    svc = ForumService(ctx.get_client())
    disc_id = svc.add_discussion(forum_id, subject, message)
    console.print(f"[green]Created discussion {disc_id} in forum {forum_id}[/green]")
