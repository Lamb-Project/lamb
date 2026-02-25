"""User management commands — lamb user *."""

from __future__ import annotations

import json
import os
from typing import Optional

import typer

from lamb_cli.client import get_client
from lamb_cli.config import get_output_format
from lamb_cli.output import format_output, print_error, print_success

app = typer.Typer(help="Manage users (admin).")

USER_LIST_COLUMNS = [
    ("id", "ID"),
    ("email", "Email"),
    ("name", "Name"),
    ("role", "Role"),
    ("user_type", "User Type"),
    ("enabled", "Enabled"),
]

USER_DETAIL_FIELDS = [
    ("id", "ID"),
    ("email", "Email"),
    ("name", "Name"),
    ("role", "Role"),
    ("user_type", "User Type"),
    ("enabled", "Enabled"),
    ("auth_provider", "Auth Provider"),
    ("created_at", "Created At"),
    ("lti_user_id", "LTI User ID"),
]


@app.command("list")
def list_users(
    org: Optional[str] = typer.Option(None, "--org", help="Organization slug (admin only)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """List users in the organization."""
    fmt = output or get_output_format()
    params: dict = {}
    if org:
        params["org"] = org
    with get_client() as client:
        resp = client.get("/creator/admin/org-admin/users", params=params)
    users = resp if isinstance(resp, list) else resp.get("users", resp)
    if isinstance(users, dict):
        users = [users]
    format_output(users, USER_LIST_COLUMNS, fmt)


@app.command("get")
def get_user(
    user_id: str = typer.Argument(..., help="User ID."),
    org: Optional[str] = typer.Option(None, "--org", help="Organization slug (admin only)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Get details of a user."""
    fmt = output or get_output_format()
    params: dict = {}
    if org:
        params["org"] = org
    with get_client() as client:
        resp = client.get("/creator/admin/org-admin/users", params=params)
    users = resp if isinstance(resp, list) else resp.get("users", resp)
    if isinstance(users, dict):
        users = [users]
    match = [u for u in users if str(u.get("id", "")) == user_id]
    if not match:
        print_error(f"User {user_id} not found.")
        raise typer.Exit(5)
    format_output(match[0], USER_LIST_COLUMNS, fmt, detail_fields=USER_DETAIL_FIELDS)


@app.command("create")
def create_user(
    email: str = typer.Argument(..., help="User email address."),
    name: str = typer.Argument(..., help="User display name."),
    password: str = typer.Argument(..., help="User password."),
    user_type: str = typer.Option("creator", "--user-type", "-t", help="User type: creator or end_user."),
    enabled: bool = typer.Option(True, "--enabled/--disabled", help="Enable or disable the user."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Create a new user."""
    fmt = output or get_output_format()
    body: dict = {
        "email": email,
        "name": name,
        "password": password,
        "user_type": user_type,
        "enabled": enabled,
    }
    with get_client() as client:
        data = client.post("/creator/admin/org-admin/users", json=body)
    print_success(f"User created: {data.get('email', data.get('id', ''))}")
    format_output(data, USER_LIST_COLUMNS, fmt)


@app.command("update")
def update_user(
    user_id: str = typer.Argument(..., help="User ID."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New display name."),
    enabled: Optional[bool] = typer.Option(None, "--enabled/--disabled", help="Enable or disable the user."),
) -> None:
    """Update a user."""
    body: dict = {}
    if name is not None:
        body["name"] = name
    if enabled is not None:
        body["enabled"] = enabled
    if not body:
        print_error("No fields to update. Provide at least one option.")
        raise typer.Exit(1)
    with get_client() as client:
        data = client.put(f"/creator/admin/org-admin/users/{user_id}", json=body)
    msg = data.get("message", "User updated.") if isinstance(data, dict) else "User updated."
    print_success(msg)


@app.command("delete")
def delete_user(
    user_id: str = typer.Argument(..., help="User ID."),
    org: Optional[str] = typer.Option(None, "--org", help="Organization slug (admin only)."),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a user."""
    if not confirm:
        typer.confirm(f"Delete user {user_id}?", abort=True)
    params: dict = {}
    if org:
        params["org"] = org
    with get_client() as client:
        data = client.delete(f"/creator/admin/org-admin/users/{user_id}", params=params)
    msg = data.get("message", "User deleted.") if isinstance(data, dict) else "User deleted."
    print_success(msg)


@app.command("enable")
def enable_user(
    user_id: str = typer.Argument(..., help="User ID."),
) -> None:
    """Enable a user."""
    with get_client() as client:
        data = client.put(f"/creator/admin/org-admin/users/{user_id}", json={"enabled": True})
    print_success(f"User {user_id} enabled.")


@app.command("disable")
def disable_user(
    user_id: str = typer.Argument(..., help="User ID."),
) -> None:
    """Disable a user."""
    with get_client() as client:
        data = client.put(f"/creator/admin/org-admin/users/{user_id}", json={"enabled": False})
    print_success(f"User {user_id} disabled.")


@app.command("reset-password")
def reset_password(
    user_id: str = typer.Argument(..., help="User ID."),
    new_password: str = typer.Argument(..., help="New password."),
) -> None:
    """Reset a user's password."""
    with get_client() as client:
        data = client.post(
            f"/creator/admin/org-admin/users/{user_id}/password",
            json={"new_password": new_password},
        )
    msg = data.get("message", "Password reset.") if isinstance(data, dict) else "Password reset."
    print_success(msg)


@app.command("bulk-import")
def bulk_import(
    file: str = typer.Argument(..., help="Path to JSON file with user data."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only, do not create users."),
    org: Optional[str] = typer.Option(None, "--org", help="Organization slug (admin only)."),
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Bulk import users from a JSON file.

    File format: {"version": "1.0", "users": [{"email": "...", "name": "...", ...}]}

    Use --dry-run to validate the file without creating users.
    """
    fmt = output or get_output_format()
    if not os.path.isfile(file):
        print_error(f"File not found: {file}")
        raise typer.Exit(1)

    with open(file, encoding="utf-8") as f:
        payload = json.load(f)

    params: dict = {}
    if org:
        params["org"] = org

    endpoint = "/creator/admin/org-admin/users/bulk-import/validate" if dry_run else "/creator/admin/org-admin/users/bulk-import/execute"

    with get_client() as client:
        data = client.post(endpoint, json=payload, params=params)

    if dry_run:
        print_success("Validation complete.")
    else:
        print_success("Bulk import complete.")
    format_output(data, USER_LIST_COLUMNS, fmt)
