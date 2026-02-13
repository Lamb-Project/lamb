"""Organization management commands — lamb org *."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_json, print_success

app = typer.Typer(help="Manage organizations (admin).")

ORG_LIST_COLUMNS = [
    ("id", "ID"),
    ("slug", "Slug"),
    ("name", "Name"),
    ("status", "Status"),
    ("is_system", "System"),
]

ORG_DETAIL_FIELDS = [
    ("id", "ID"),
    ("slug", "Slug"),
    ("name", "Name"),
    ("status", "Status"),
    ("is_system", "System"),
    ("created_at", "Created At"),
    ("updated_at", "Updated At"),
]

DASHBOARD_STAT_FIELDS = [
    ("org_name", "Org Name"),
    ("org_slug", "Org Slug"),
    ("org_status", "Org Status"),
    ("total_users", "Total Users"),
    ("active_users", "Active Users"),
    ("total_assistants", "Total Assistants"),
    ("total_knowledge_bases", "Total KBs"),
]


def _flatten_dashboard(data: dict) -> dict:
    """Flatten nested dashboard response into a flat dict for display."""
    flat: dict = {}
    org = data.get("organization", {})
    flat["org_name"] = org.get("name", "")
    flat["org_slug"] = org.get("slug", "")
    flat["org_status"] = org.get("status", "")

    stats = data.get("stats", {})
    flat["total_users"] = stats.get("total_users", "")
    flat["active_users"] = stats.get("active_users", "")
    flat["total_assistants"] = stats.get("total_assistants", "")
    flat["total_knowledge_bases"] = stats.get("total_knowledge_bases", "")

    settings = data.get("settings_status", {})
    flat["settings_status"] = settings

    return flat


@app.command("list")
def list_orgs(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List all organizations."""
    fmt = output or get_output_format()
    with get_client() as client:
        resp = client.get("/creator/admin/organizations")
    orgs = resp if isinstance(resp, list) else resp.get("organizations", resp)
    if isinstance(orgs, dict):
        orgs = [orgs]
    format_output(orgs, ORG_LIST_COLUMNS, fmt)


@app.command("get")
def get_org(
    slug: str = typer.Argument(..., help="Organization slug."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of an organization."""
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get(f"/creator/admin/organizations/{slug}")
    format_output(data, ORG_LIST_COLUMNS, fmt, detail_fields=ORG_DETAIL_FIELDS)


@app.command("create")
def create_org(
    name: str = typer.Argument(..., help="Organization name."),
    slug: str = typer.Option(..., "--slug", "-s", help="Organization slug (URL-safe identifier)."),
    admin_user_id: Optional[str] = typer.Option(None, "--admin-user-id", help="Assign an admin user by ID."),
    signup_enabled: Optional[bool] = typer.Option(None, "--signup-enabled/--signup-disabled", help="Enable self-signup."),
    signup_key: Optional[str] = typer.Option(None, "--signup-key", help="Signup key for self-registration."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Create a new organization."""
    fmt = output or get_output_format()
    body: dict = {"name": name, "slug": slug}
    if admin_user_id is not None:
        body["admin_user_id"] = admin_user_id
    if signup_enabled is not None:
        body["signup_enabled"] = signup_enabled
    if signup_key is not None:
        body["signup_key"] = signup_key
    with get_client() as client:
        data = client.post("/creator/admin/organizations/enhanced", json=body)
    print_success(f"Organization created: {data.get('slug', data.get('name', ''))}")
    format_output(data, ORG_LIST_COLUMNS, fmt)


@app.command("update")
def update_org(
    slug: str = typer.Argument(..., help="Organization slug."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name."),
    status: Optional[str] = typer.Option(None, "--status", help="New status (active, inactive)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Update an organization."""
    fmt = output or get_output_format()
    body: dict = {}
    if name is not None:
        body["name"] = name
    if status is not None:
        body["status"] = status
    if not body:
        print_error("No fields to update. Provide at least one option.")
        raise typer.Exit(1)
    with get_client() as client:
        data = client.put(f"/creator/admin/organizations/{slug}", json=body)
    msg = data.get("message", "Organization updated.") if isinstance(data, dict) else "Organization updated."
    print_success(msg)


@app.command("delete")
def delete_org(
    slug: str = typer.Argument(..., help="Organization slug."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete an organization."""
    if not confirm:
        typer.confirm(f"Delete organization {slug}?", abort=True)
    with get_client() as client:
        data = client.delete(f"/creator/admin/organizations/{slug}")
    msg = data.get("message", "Organization deleted.") if isinstance(data, dict) else "Organization deleted."
    print_success(msg)


@app.command("export")
def export_org(
    slug: str = typer.Argument(..., help="Organization slug."),
    output_file: Optional[Path] = typer.Option(
        None, "--output-file", "-f", help="Write export to file instead of stdout."
    ),
) -> None:
    """Export an organization as JSON."""
    with get_client() as client:
        data = client.get(f"/creator/admin/organizations/{slug}/export")
    json_str = json.dumps(data, indent=2, default=str)
    if output_file:
        output_file.write_text(json_str, encoding="utf-8")
        print_success(f"Exported to {output_file}")
    else:
        sys.stdout.write(json_str + "\n")


@app.command("set-role")
def set_role(
    slug: str = typer.Argument(..., help="Organization slug."),
    user_id: str = typer.Argument(..., help="User ID."),
    role: str = typer.Argument(..., help="Role: admin or member."),
) -> None:
    """Set a user's role within an organization."""
    if role not in ("admin", "member"):
        print_error(f"Invalid role '{role}'. Must be 'admin' or 'member'.")
        raise typer.Exit(1)
    with get_client() as client:
        data = client.put(
            f"/creator/admin/organizations/{slug}/members/{user_id}/role",
            json={"role": role},
        )
    msg = data.get("message", f"Role set to {role}.") if isinstance(data, dict) else f"Role set to {role}."
    print_success(msg)


@app.command("dashboard")
def dashboard(
    org: Optional[str] = typer.Option(None, "--org", help="Organization slug (admin only)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Show organization dashboard with statistics."""
    fmt = output or get_output_format()
    params: dict = {}
    if org:
        params["org"] = org
    with get_client() as client:
        data = client.get("/creator/org-admin/dashboard", params=params)

    if fmt == "json":
        print_json(data)
        return

    flat = _flatten_dashboard(data)
    format_output(flat, DASHBOARD_STAT_FIELDS, fmt, detail_fields=DASHBOARD_STAT_FIELDS)
