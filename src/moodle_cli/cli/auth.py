"""Auth commands: login, logout, status, profiles."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.config.manager import Profile
from moodle_cli.output import console, render_json, render_table


@click.group()
def auth() -> None:
    """Authenticate with a Moodle instance."""


@auth.command()
@click.option("--url", required=True, prompt=True, help="Moodle site URL (e.g. https://moodle.example.com)")
@click.option("--username", required=True, prompt=True, help="Moodle username")
@click.option("--password", default=None, help="Moodle password")
@click.option("--token", default=None, help="Pre-existing token (for SSO/CAS sites)")
@click.option("--profile-name", "--name", default="default", help="Profile name to save as")
@click.option("--service", default="moodle_mobile_app", help="Web service name")
@pass_context
@handle_errors
def login(
    ctx: MoodleContext,
    url: str,
    username: str,
    password: str | None,
    token: str | None,
    profile_name: str,
    service: str,
) -> None:
    """Login to a Moodle instance and save credentials.

    For SSO/CAS sites, use --token to provide a pre-existing token
    instead of username/password authentication.
    """
    url = url.rstrip("/")

    if token:
        console.print(f"Storing token for [bold]{url}[/bold]...")
    else:
        if not password:
            password = click.prompt("Password", hide_input=True)
        console.print(f"Authenticating to [bold]{url}[/bold]...")
        token = MoodleHTTPClient.authenticate(url, username, password, service)

    profile = Profile(url=url, username=username, service=service)
    ctx.config.set_profile(profile_name, profile)
    ctx.tokens.store(profile_name, token)

    console.print(f"[green]Logged in as {username} (profile: {profile_name})[/green]")


@auth.command()
@click.option("--profile-name", "--name", default=None, help="Profile to logout from")
@pass_context
@handle_errors
def logout(ctx: MoodleContext, profile_name: str | None) -> None:
    """Remove stored token for a profile."""
    name, _ = ctx.config.get_profile(profile_name)
    ctx.tokens.delete(name)
    console.print(f"[green]Logged out from profile '{name}'.[/green]")


@auth.command()
@click.option("--profile-name", "--name", default=None, help="Profile to check")
@pass_context
@handle_errors
def status(ctx: MoodleContext, profile_name: str | None) -> None:
    """Show authentication status for a profile."""
    name, profile = ctx.config.get_profile(profile_name)
    token = ctx.tokens.get(name)
    if ctx.json_output:
        render_json({
            "profile": name,
            "url": profile.url,
            "username": profile.username,
            "authenticated": token is not None,
        })
    else:
        status_text = "[green]authenticated[/green]" if token else "[red]not authenticated[/red]"
        console.print(f"Profile: [bold]{name}[/bold]")
        console.print(f"URL:     {profile.url}")
        console.print(f"User:    {profile.username}")
        console.print(f"Status:  {status_text}")


@auth.command()
@pass_context
@handle_errors
def profiles(ctx: MoodleContext) -> None:
    """List all saved profiles."""
    profile_list = ctx.config.list_profiles()
    if ctx.json_output:
        render_json([
            {"name": name, "url": p.url, "username": p.username, "default": is_default}
            for name, p, is_default in profile_list
        ])
    else:
        if not profile_list:
            console.print("[dim]No profiles configured. Run: moodle auth login[/dim]")
            return
        rows = []
        for name, p, is_default in profile_list:
            rows.append({
                "Name": f"{'* ' if is_default else ''}{name}",
                "URL": p.url,
                "Username": p.username,
            })
        render_table(rows, title="Profiles")
