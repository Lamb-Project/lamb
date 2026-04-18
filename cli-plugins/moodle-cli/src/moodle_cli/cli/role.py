"""Role commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console
from moodle_cli.services.role import RoleService


@click.group()
def role() -> None:
    """Role management."""


@role.command()
@click.option("--role-id", required=True, type=int, help="Role ID")
@click.option("--user-id", required=True, type=int, help="User ID")
@click.option("--context-id", required=True, type=int, help="Context ID")
@pass_context
@handle_errors
def assign(ctx: MoodleContext, role_id: int, user_id: int, context_id: int) -> None:
    """Assign a role to a user in a context."""
    svc = RoleService(ctx.get_client())
    svc.assign_role(role_id, user_id, context_id)
    console.print(f"[green]Assigned role {role_id} to user {user_id} in context {context_id}.[/green]")


@role.command()
@click.option("--role-id", required=True, type=int, help="Role ID")
@click.option("--user-id", required=True, type=int, help="User ID")
@click.option("--context-id", required=True, type=int, help="Context ID")
@pass_context
@handle_errors
def unassign(ctx: MoodleContext, role_id: int, user_id: int, context_id: int) -> None:
    """Unassign a role from a user in a context."""
    svc = RoleService(ctx.get_client())
    svc.unassign_role(role_id, user_id, context_id)
    console.print(f"[green]Unassigned role {role_id} from user {user_id} in context {context_id}.[/green]")
