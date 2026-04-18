"""User commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.user import UserService


@click.group()
def user() -> None:
    """User management."""


@user.command()
@pass_context
@handle_errors
def me(ctx: MoodleContext) -> None:
    """Show current user information."""
    svc = UserService(ctx.get_client())
    u = svc.get_me()
    if ctx.json_output:
        render_json(u.model_dump())
    else:
        console.print(f"[bold]{u.fullname}[/bold]")
        console.print(f"ID:       {u.id}")
        console.print(f"Username: {u.username}")


@user.command("list")
@click.option("--key", default="email", help="Search key (email, username, etc.)")
@click.option("--value", default="%%", help="Search value (use %% for wildcard)")
@pass_context
@handle_errors
def list_users(ctx: MoodleContext, key: str, value: str) -> None:
    """List/search users."""
    svc = UserService(ctx.get_client())
    users = svc.list_users(key, value)
    if ctx.json_output:
        render_json([u.model_dump() for u in users])
    else:
        rows = [{"ID": u.id, "Username": u.username, "Full Name": u.fullname, "Email": u.email} for u in users]
        render_table(rows, title=f"Users ({len(rows)})")


@user.command()
@click.argument("user_id", type=int)
@pass_context
@handle_errors
def get(ctx: MoodleContext, user_id: int) -> None:
    """Get user details by ID."""
    svc = UserService(ctx.get_client())
    u = svc.get_user(user_id)
    if ctx.json_output:
        render_json(u.model_dump())
    else:
        console.print(f"[bold]{u.fullname}[/bold]")
        console.print(f"ID:       {u.id}")
        console.print(f"Username: {u.username}")
        console.print(f"Email:    {u.email}")


@user.command()
@click.option("--username", required=True)
@click.option("--firstname", required=True)
@click.option("--lastname", required=True)
@click.option("--email", required=True)
@click.option("--password", required=True, prompt=True, hide_input=True)
@pass_context
@handle_errors
def create(ctx: MoodleContext, username: str, firstname: str, lastname: str, email: str, password: str) -> None:
    """Create a new user."""
    svc = UserService(ctx.get_client())
    u = svc.create_user(username, firstname, lastname, email, password)
    if ctx.json_output:
        render_json(u.model_dump())
    else:
        console.print(f"[green]Created user '{u.username}' (ID: {u.id})[/green]")


@user.command()
@click.argument("user_id", type=int)
@click.option("--firstname", default=None)
@click.option("--lastname", default=None)
@click.option("--email", default=None)
@pass_context
@handle_errors
def update(ctx: MoodleContext, user_id: int, firstname: str | None, lastname: str | None, email: str | None) -> None:
    """Update a user."""
    svc = UserService(ctx.get_client())
    kwargs = {}
    if firstname is not None:
        kwargs["firstname"] = firstname
    if lastname is not None:
        kwargs["lastname"] = lastname
    if email is not None:
        kwargs["email"] = email
    svc.update_user(user_id, **kwargs)
    console.print(f"[green]Updated user {user_id}.[/green]")


@user.command()
@click.argument("user_ids", type=int, nargs=-1, required=True)
@click.confirmation_option(prompt="Are you sure you want to delete these users?")
@pass_context
@handle_errors
def delete(ctx: MoodleContext, user_ids: tuple[int, ...]) -> None:
    """Delete users by ID."""
    svc = UserService(ctx.get_client())
    svc.delete_users(list(user_ids))
    console.print(f"[green]Deleted {len(user_ids)} user(s).[/green]")
