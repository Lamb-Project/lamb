"""Assignment commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.assign import AssignService


@click.group()
def assign() -> None:
    """Assignment management."""


@assign.command("list")
@click.option("--course-id", type=int, multiple=True, help="Filter by course ID(s)")
@pass_context
@handle_errors
def list_assignments(ctx: MoodleContext, course_id: tuple[int, ...]) -> None:
    """List assignments."""
    svc = AssignService(ctx.get_client())
    ids = list(course_id) if course_id else None
    assignments = svc.list_assignments(ids)
    if ctx.json_output:
        render_json([a.model_dump() for a in assignments])
    else:
        rows = [{"ID": a.id, "Course": a.course, "Name": a.name, "Due": a.duedate} for a in assignments]
        render_table(rows, title=f"Assignments ({len(rows)})")


@assign.command()
@click.argument("assignment_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def submissions(ctx: MoodleContext, assignment_ids: tuple[int, ...]) -> None:
    """Get submissions for assignment(s)."""
    svc = AssignService(ctx.get_client())
    subs = svc.get_submissions(list(assignment_ids))
    if ctx.json_output:
        render_json([s.model_dump() for s in subs])
    else:
        rows = [{"ID": s.id, "User": s.userid, "Status": s.status, "Grading": s.gradingstatus} for s in subs]
        render_table(rows, title=f"Submissions ({len(rows)})")


@assign.command()
@click.option("--assignment-id", required=True, type=int)
@click.option("--user-id", required=True, type=int)
@click.option("--grade", "grade_value", required=True, type=float)
@click.option("--feedback", default="", help="Feedback comment")
@pass_context
@handle_errors
def grade(ctx: MoodleContext, assignment_id: int, user_id: int, grade_value: float, feedback: str) -> None:
    """Grade a submission."""
    svc = AssignService(ctx.get_client())
    svc.grade_submission(assignment_id, user_id, grade_value, feedback)
    console.print(f"[green]Graded user {user_id} on assignment {assignment_id}: {grade_value}[/green]")
