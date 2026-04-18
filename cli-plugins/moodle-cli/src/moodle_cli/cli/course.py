"""Course commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.course import CourseService


@click.group()
def course() -> None:
    """Course management."""


@course.command("list")
@pass_context
@handle_errors
def list_courses(ctx: MoodleContext) -> None:
    """List all courses."""
    svc = CourseService(ctx.get_client())
    courses = svc.list_courses()
    if ctx.json_output:
        render_json([c.model_dump() for c in courses])
    else:
        rows = [{"ID": c.id, "Short Name": c.shortname, "Full Name": c.fullname, "Visible": c.visible} for c in courses]
        render_table(rows, title=f"Courses ({len(rows)})")


@course.command()
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def get(ctx: MoodleContext, course_id: int) -> None:
    """Get details of a course."""
    svc = CourseService(ctx.get_client())
    c = svc.get_course(course_id)
    if ctx.json_output:
        render_json(c.model_dump())
    else:
        console.print(f"[bold]{c.fullname}[/bold] ({c.shortname})")
        console.print(f"ID:       {c.id}")
        console.print(f"Category: {c.categoryid}")
        console.print(f"Format:   {c.format}")
        console.print(f"Visible:  {c.visible}")
        if c.summary:
            console.print(f"Summary:  {c.summary[:200]}")


@course.command()
@click.argument("query")
@pass_context
@handle_errors
def search(ctx: MoodleContext, query: str) -> None:
    """Search courses by name."""
    svc = CourseService(ctx.get_client())
    courses = svc.search_courses(query)
    if ctx.json_output:
        render_json([c.model_dump() for c in courses])
    else:
        rows = [{"ID": c.id, "Short Name": c.shortname, "Full Name": c.fullname} for c in courses]
        render_table(rows, title=f"Search results for '{query}' ({len(rows)})")


@course.command()
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def contents(ctx: MoodleContext, course_id: int) -> None:
    """Show course contents (sections and modules)."""
    svc = CourseService(ctx.get_client())
    sections = svc.get_contents(course_id)
    if ctx.json_output:
        render_json([s.model_dump() for s in sections])
    else:
        for section in sections:
            console.print(f"\n[bold]{section.name}[/bold]")
            for mod in section.modules:
                console.print(f"  [{mod.get('modname', '')}] {mod.get('name', '')}")


@course.command()
@click.option("--fullname", required=True, help="Full course name")
@click.option("--shortname", required=True, help="Short course name")
@click.option("--categoryid", required=True, type=int, help="Category ID")
@pass_context
@handle_errors
def create(ctx: MoodleContext, fullname: str, shortname: str, categoryid: int) -> None:
    """Create a new course."""
    svc = CourseService(ctx.get_client())
    c = svc.create_course(fullname, shortname, categoryid)
    if ctx.json_output:
        render_json(c.model_dump())
    else:
        console.print(f"[green]Created course '{c.fullname}' (ID: {c.id})[/green]")


@course.command()
@click.argument("course_id", type=int)
@click.option("--fullname", default=None, help="New full name")
@click.option("--shortname", default=None, help="New short name")
@click.option("--visible", default=None, type=int, help="Visibility (0 or 1)")
@pass_context
@handle_errors
def update(
    ctx: MoodleContext, course_id: int, fullname: str | None, shortname: str | None, visible: int | None,
) -> None:
    """Update a course."""
    svc = CourseService(ctx.get_client())
    kwargs = {}
    if fullname is not None:
        kwargs["fullname"] = fullname
    if shortname is not None:
        kwargs["shortname"] = shortname
    if visible is not None:
        kwargs["visible"] = visible
    svc.update_course(course_id, **kwargs)
    console.print(f"[green]Updated course {course_id}.[/green]")


@course.command()
@click.argument("course_ids", type=int, nargs=-1, required=True)
@click.confirmation_option(prompt="Are you sure you want to delete these courses?")
@pass_context
@handle_errors
def delete(ctx: MoodleContext, course_ids: tuple[int, ...]) -> None:
    """Delete courses by ID."""
    svc = CourseService(ctx.get_client())
    svc.delete_courses(list(course_ids))
    console.print(f"[green]Deleted {len(course_ids)} course(s).[/green]")
