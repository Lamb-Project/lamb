"""Enrolment commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import render_json, render_table
from moodle_cli.services.enrol import EnrolService
from moodle_cli.services.user import UserService


@click.group()
def enrol() -> None:
    """Enrolment management."""


@enrol.command("my-courses")
@pass_context
@handle_errors
def my_courses(ctx: MoodleContext) -> None:
    """List courses the current user is enrolled in."""
    client = ctx.get_client()
    user_svc = UserService(client)
    me = user_svc.get_me()
    svc = EnrolService(client)
    courses = svc.get_my_courses(userid=me.id)
    if ctx.json_output:
        render_json([c.model_dump() for c in courses])
    else:
        rows = [{"ID": c.id, "Short Name": c.shortname, "Full Name": c.fullname} for c in courses]
        render_table(rows, title=f"My Courses ({len(rows)})")


@enrol.command("list-users")
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def list_users(ctx: MoodleContext, course_id: int) -> None:
    """List enrolled users in a course."""
    svc = EnrolService(ctx.get_client())
    users = svc.list_enrolled_users(course_id)
    if ctx.json_output:
        render_json([u.model_dump() for u in users])
    else:
        rows = [{"ID": u.id, "Username": u.username, "Full Name": u.fullname, "Email": u.email} for u in users]
        render_table(rows, title=f"Enrolled Users ({len(rows)})")
