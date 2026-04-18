"""Calendar commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.calendar import CalendarService


@click.group()
def calendar() -> None:
    """Calendar management."""


@calendar.command()
@click.option("--course-id", type=int, multiple=True, help="Filter by course ID(s)")
@pass_context
@handle_errors
def events(ctx: MoodleContext, course_id: tuple[int, ...]) -> None:
    """List calendar events."""
    svc = CalendarService(ctx.get_client())
    ids = list(course_id) if course_id else None
    evts = svc.get_events(ids)
    if ctx.json_output:
        render_json([e.model_dump() for e in evts])
    else:
        rows = [{"ID": e.id, "Name": e.name, "Type": e.eventtype, "Start": e.timestart} for e in evts]
        render_table(rows, title=f"Events ({len(rows)})")


@calendar.command()
@click.option("--name", required=True, help="Event name")
@click.option("--timestart", required=True, type=int, help="Start time (unix timestamp)")
@click.option("--duration", default=0, type=int, help="Duration in seconds")
@click.option("--description", default="", help="Event description")
@click.option("--course-id", default=0, type=int, help="Course ID (for course events)")
@click.option("--type", "eventtype", default="user", help="Event type (user, course, site)")
@pass_context
@handle_errors
def create(
    ctx: MoodleContext,
    name: str,
    timestart: int,
    duration: int,
    description: str,
    course_id: int,
    eventtype: str,
) -> None:
    """Create a calendar event."""
    svc = CalendarService(ctx.get_client())
    evt = svc.create_event(
        name=name,
        eventtype=eventtype,
        timestart=timestart,
        timeduration=duration,
        description=description,
        courseid=course_id,
    )
    if ctx.json_output:
        render_json(evt.model_dump())
    else:
        console.print(f"[green]Created event '{evt.name}' (ID: {evt.id})[/green]")
