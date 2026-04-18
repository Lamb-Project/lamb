"""Grade commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import render_json, render_table
from moodle_cli.services.grade import GradeService


@click.group()
def grade() -> None:
    """Grade management."""


@grade.command()
@click.argument("course_id", type=int)
@click.option("--user-id", type=int, default=None, help="Filter by user ID")
@pass_context
@handle_errors
def get(ctx: MoodleContext, course_id: int, user_id: int | None) -> None:
    """Get grade items for a course."""
    svc = GradeService(ctx.get_client())
    items = svc.get_grades(course_id, user_id)
    if ctx.json_output:
        render_json([i.model_dump() for i in items])
    else:
        rows = [{"Item": i.itemname or "", "Grade": i.grade or "", "Max": i.grademax} for i in items]
        render_table(rows, title="Grade Items")


@grade.command()
@click.argument("course_id", type=int)
@click.option("--user-id", type=int, default=None, help="Filter by user ID")
@pass_context
@handle_errors
def report(ctx: MoodleContext, course_id: int, user_id: int | None) -> None:
    """Get full grade report for a course."""
    svc = GradeService(ctx.get_client())
    rpt = svc.get_report(course_id, user_id)
    if ctx.json_output:
        render_json(rpt.model_dump())
    else:
        for ug in rpt.usergrades:
            from moodle_cli.output import console
            console.print(f"\n[bold]User: {ug.get('userfullname', ug.get('userid', '?'))}[/bold]")
            items = ug.get("gradeitems", [])
            rows = [
                {"Item": i.get("itemname", ""), "Grade": i.get("grade", ""), "Max": i.get("grademax", "")}
                for i in items
            ]
            render_table(rows)
