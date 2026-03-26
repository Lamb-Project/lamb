"""Prompt template management commands — lamb template *."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_json, print_success

app = typer.Typer(help="Manage prompt templates.")

TEMPLATE_LIST_COLUMNS = [
    ("id", "ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("is_shared", "Shared"),
    ("is_owner", "Owner"),
]

TEMPLATE_DETAIL_FIELDS = [
    ("id", "ID"),
    ("name", "Name"),
    ("description", "Description"),
    ("is_shared", "Shared"),
    ("is_owner", "Owner"),
    ("system_prompt", "System Prompt"),
    ("prompt_template", "Prompt Template"),
    ("owner_name", "Owner Name"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]


@app.command("list")
def list_templates(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of templates."),
    offset: int = typer.Option(0, "--offset", help="Pagination offset."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List your prompt templates."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get("/creator/prompt-templates/list", params={"limit": limit, "offset": offset})
    templates = resp.get("templates", [])
    format_output(templates, TEMPLATE_LIST_COLUMNS, fmt)


@app.command("list-shared")
def list_shared_templates(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of templates."),
    offset: int = typer.Option(0, "--offset", help="Pagination offset."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List shared prompt templates."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get("/creator/prompt-templates/shared", params={"limit": limit, "offset": offset})
    templates = resp.get("templates", [])
    format_output(templates, TEMPLATE_LIST_COLUMNS, fmt)


@app.command("get")
def get_template(
    template_id: int = typer.Argument(..., help="Template ID."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of a prompt template."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/prompt-templates/{template_id}")
    format_output(data, TEMPLATE_LIST_COLUMNS, fmt, detail_fields=TEMPLATE_DETAIL_FIELDS)


@app.command("create")
def create_template(
    name: str = typer.Argument(..., help="Template name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description."),
    system_prompt: Optional[str] = typer.Option(None, "--system-prompt", help="System prompt text."),
    prompt_template: Optional[str] = typer.Option(None, "--prompt-template", help="Prompt template text."),
    shared: bool = typer.Option(False, "--shared", help="Share with organization."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Create a new prompt template."""
    fmt = output or get_output_format()
    body: dict = {"name": name, "is_shared": shared}
    if description is not None:
        body["description"] = description
    if system_prompt is not None:
        body["system_prompt"] = system_prompt
    if prompt_template is not None:
        body["prompt_template"] = prompt_template
    with get_client() as client:
        data = client.post("/creator/prompt-templates/create", json=body)
    print_success(f"Template created: {data.get('id', '')}")
    format_output(data, TEMPLATE_LIST_COLUMNS, fmt, detail_fields=TEMPLATE_DETAIL_FIELDS)


@app.command("update")
def update_template(
    template_id: int = typer.Argument(..., help="Template ID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description."),
    system_prompt: Optional[str] = typer.Option(None, "--system-prompt", help="New system prompt."),
    prompt_template: Optional[str] = typer.Option(None, "--prompt-template", help="New prompt template."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Update a prompt template."""
    fmt = output or get_output_format()
    body: dict = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if system_prompt is not None:
        body["system_prompt"] = system_prompt
    if prompt_template is not None:
        body["prompt_template"] = prompt_template
    if not body:
        print_error("No fields to update. Provide at least one option.")
        raise typer.Exit(1)
    with get_client() as client:
        data = client.put(f"/creator/prompt-templates/{template_id}", json=body)
    print_success("Template updated.")
    format_output(data, TEMPLATE_LIST_COLUMNS, fmt, detail_fields=TEMPLATE_DETAIL_FIELDS)


@app.command("delete")
def delete_template(
    template_id: int = typer.Argument(..., help="Template ID."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a prompt template."""
    if not confirm:
        typer.confirm(f"Delete template {template_id}?", abort=True)
    with get_client() as client:
        client.delete(f"/creator/prompt-templates/{template_id}")
    print_success(f"Template {template_id} deleted.")


@app.command("duplicate")
def duplicate_template(
    template_id: int = typer.Argument(..., help="Template ID to duplicate."),
    new_name: Optional[str] = typer.Option(None, "--new-name", help="Name for the copy."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Duplicate a prompt template."""
    fmt = output or get_output_format()
    body: dict = {}
    if new_name is not None:
        body["new_name"] = new_name
    with get_client() as client:
        data = client.post(f"/creator/prompt-templates/{template_id}/duplicate", json=body)
    print_success(f"Template duplicated: {data.get('id', '')}")
    format_output(data, TEMPLATE_LIST_COLUMNS, fmt, detail_fields=TEMPLATE_DETAIL_FIELDS)


@app.command("share")
def share_template(
    template_id: int = typer.Argument(..., help="Template ID."),
    enable: bool = typer.Option(None, "--enable/--disable", help="Enable or disable sharing."),
) -> None:
    """Enable or disable sharing for a prompt template."""
    if enable is None:
        print_error("Specify --enable or --disable.")
        raise typer.Exit(1)
    with get_client() as client:
        client.put(f"/creator/prompt-templates/{template_id}/share", json={"is_shared": enable})
    state = "enabled" if enable else "disabled"
    print_success(f"Sharing {state} for template {template_id}.")


@app.command("export")
def export_templates(
    template_ids: list[int] = typer.Argument(..., help="Template IDs to export."),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Write to file instead of stdout."),
) -> None:
    """Export prompt templates as JSON."""
    with get_client() as client:
        data = client.post("/creator/prompt-templates/export", json={"template_ids": template_ids})
    text = json.dumps(data, indent=2, default=str)
    if file:
        file.write_text(text + "\n")
        print_success(f"Exported {len(template_ids)} template(s) to {file}.")
    else:
        sys.stdout.write(text + "\n")
