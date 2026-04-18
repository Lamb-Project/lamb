"""File commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.file import FileService


@click.group()
def file() -> None:
    """File management."""


@file.command("list")
@click.argument("contextid", type=int)
@click.option("--component", default="user", help="File component")
@click.option("--filearea", default="private", help="File area")
@click.option("--itemid", default=0, type=int, help="Item ID")
@click.option("--filepath", default="/", help="File path")
@pass_context
@handle_errors
def list_files(
    ctx: MoodleContext,
    contextid: int,
    component: str,
    filearea: str,
    itemid: int,
    filepath: str,
) -> None:
    """List files in a Moodle file area."""
    svc = FileService(ctx.get_client())
    files = svc.list_files(contextid, component, filearea, itemid, filepath)
    if ctx.json_output:
        render_json([f.model_dump() for f in files])
    else:
        rows = [{"Name": f.filename, "Size": f.filesize, "URL": f.fileurl} for f in files]
        render_table(rows, title=f"Files ({len(rows)})")


@file.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--component", default="user", help="File component")
@click.option("--filearea", default="draft", help="File area")
@click.option("--itemid", default=0, type=int, help="Item ID")
@pass_context
@handle_errors
def upload(
    ctx: MoodleContext,
    file_path: str,
    component: str,
    filearea: str,
    itemid: int,
) -> None:
    """Upload a file to Moodle."""
    svc = FileService(ctx.get_client())
    result = svc.upload(file_path, component, filearea, itemid)
    if ctx.json_output:
        render_json(result)
    else:
        console.print("[green]Uploaded file successfully.[/green]")
        if isinstance(result, list) and result:
            console.print(f"Item ID: {result[0].get('itemid', 'N/A')}")
