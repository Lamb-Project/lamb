"""Cohort commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.cohort import CohortService


@click.group()
def cohort() -> None:
    """Cohort management."""


@cohort.command("list")
@pass_context
@handle_errors
def list_cohorts(ctx: MoodleContext) -> None:
    """List all cohorts."""
    svc = CohortService(ctx.get_client())
    cohorts = svc.list_cohorts()
    if ctx.json_output:
        render_json([c.model_dump() for c in cohorts])
    else:
        rows = [
            {"ID": c.id, "Name": c.name, "ID Number": c.idnumber, "Description": c.description[:60]}
            for c in cohorts
        ]
        render_table(rows, title=f"Cohorts ({len(rows)})")


@cohort.command()
@click.option("--name", required=True, help="Cohort name")
@click.option("--idnumber", default="", help="ID number")
@click.option("--description", default="", help="Description")
@pass_context
@handle_errors
def create(ctx: MoodleContext, name: str, idnumber: str, description: str) -> None:
    """Create a cohort."""
    svc = CohortService(ctx.get_client())
    c = svc.create_cohort(name, idnumber=idnumber, description=description)
    if ctx.json_output:
        render_json(c.model_dump())
    else:
        console.print(f"[green]Created cohort '{c.name}' (ID: {c.id})[/green]")


@cohort.command()
@click.argument("cohort_ids", type=int, nargs=-1, required=True)
@click.confirmation_option(prompt="Are you sure you want to delete these cohorts?")
@pass_context
@handle_errors
def delete(ctx: MoodleContext, cohort_ids: tuple[int, ...]) -> None:
    """Delete cohorts by ID."""
    svc = CohortService(ctx.get_client())
    svc.delete_cohorts(list(cohort_ids))
    console.print(f"[green]Deleted {len(cohort_ids)} cohort(s).[/green]")


@cohort.command("add-members")
@click.argument("cohort_id", type=int)
@click.argument("user_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def add_members(ctx: MoodleContext, cohort_id: int, user_ids: tuple[int, ...]) -> None:
    """Add users to a cohort."""
    svc = CohortService(ctx.get_client())
    svc.add_members(cohort_id, list(user_ids))
    console.print(f"[green]Added {len(user_ids)} member(s) to cohort {cohort_id}.[/green]")


@cohort.command("remove-members")
@click.argument("cohort_id", type=int)
@click.argument("user_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def remove_members(ctx: MoodleContext, cohort_id: int, user_ids: tuple[int, ...]) -> None:
    """Remove users from a cohort."""
    svc = CohortService(ctx.get_client())
    svc.remove_members(cohort_id, list(user_ids))
    console.print(f"[green]Removed {len(user_ids)} member(s) from cohort {cohort_id}.[/green]")
