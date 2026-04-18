"""Completion commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.completion import CompletionService


@click.group()
def completion() -> None:
    """Activity completion."""


@completion.command()
@click.argument("course_id", type=int)
@click.option("--user-id", type=int, default=None, help="User ID (defaults to current user)")
@pass_context
@handle_errors
def status(ctx: MoodleContext, course_id: int, user_id: int | None) -> None:
    """Show activity completion status for a course."""
    svc = CompletionService(ctx.get_client())
    statuses = svc.get_status(course_id, user_id)
    if ctx.json_output:
        render_json([s.model_dump() for s in statuses])
    else:
        state_map = {0: "Not completed", 1: "Completed", 2: "Complete (pass)", 3: "Complete (fail)"}
        rows = [{"CMID": s.cmid, "Module": s.modname, "State": state_map.get(s.state, str(s.state))} for s in statuses]
        render_table(rows, title=f"Completion Status ({len(rows)})")


@completion.command("update")
@click.argument("cmid", type=int)
@click.argument("completed", type=bool)
@pass_context
@handle_errors
def update_status(ctx: MoodleContext, cmid: int, completed: bool) -> None:
    """Manually mark an activity as complete or incomplete."""
    svc = CompletionService(ctx.get_client())
    svc.update_status(cmid, completed)
    state = "complete" if completed else "incomplete"
    console.print(f"[green]Marked activity {cmid} as {state}.[/green]")
