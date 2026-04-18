"""Site commands: info, functions."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.site import SiteService


@click.group()
def site() -> None:
    """Site information and discovery."""


@site.command()
@pass_context
@handle_errors
def info(ctx: MoodleContext) -> None:
    """Show site information."""
    client = ctx.get_client()
    svc = SiteService(client)
    si = svc.get_site_info()
    if ctx.json_output:
        render_json(si.model_dump())
    else:
        console.print(f"[bold]{si.sitename}[/bold]")
        console.print(f"URL:      {si.siteurl}")
        console.print(f"Release:  {si.release}")
        console.print(f"Version:  {si.version}")
        console.print(f"User:     {si.fullname} ({si.username})")
        console.print(f"Language: {si.lang}")


@site.command()
@click.option("--search", "-s", default=None, help="Filter functions by name")
@click.option("--component", "-c", default=None, help="Filter by component prefix (e.g. core_course)")
@pass_context
@handle_errors
def functions(ctx: MoodleContext, search: str | None, component: str | None) -> None:
    """List available web service functions."""
    client = ctx.get_client()
    svc = SiteService(client)
    funcs = svc.get_functions()

    if search:
        funcs = [f for f in funcs if search.lower() in f.name.lower()]
    if component:
        funcs = [f for f in funcs if f.name.startswith(component)]

    if ctx.json_output:
        render_json([f.model_dump() for f in funcs])
    else:
        rows = [{"Function": f.name, "Version": f.version} for f in funcs]
        render_table(rows, title=f"Functions ({len(rows)})")
