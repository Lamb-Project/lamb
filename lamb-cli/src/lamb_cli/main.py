"""LAMB CLI — main entry point and top-level commands."""

from __future__ import annotations

import sys
from typing import Optional

import typer

from lamb_cli import __version__
from lamb_cli.client import LambClient, get_client
from lamb_cli.commands import assistant, job, kb, model, org, user
from lamb_cli.config import clear_credentials, get_output_format, get_server_url, get_user_info, save_config, save_credentials
from lamb_cli.errors import LambCliError, exit_code_for
from lamb_cli.output import format_output, print_error, print_success

app = typer.Typer(
    name="lamb",
    help="CLI for the LAMB platform — manage assistants, knowledge bases, and more.",
    no_args_is_help=True,
)

app.add_typer(assistant.app, name="assistant")
app.add_typer(model.app, name="model")
app.add_typer(kb.app, name="kb")
app.add_typer(job.app, name="job")
app.add_typer(org.app, name="org")
app.add_typer(user.app, name="user")


@app.callback()
def main() -> None:
    """LAMB CLI."""
    if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
        sys.stderr.write(f"lamb-cli {__version__}\n")


@app.command()
def login(
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Account email."),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Account password."),
    server_url: Optional[str] = typer.Option(None, "--server-url", "-s", help="LAMB server URL."),
) -> None:
    """Log in to a LAMB server."""
    if server_url:
        config = {"server_url": server_url}
        save_config(config)

    url = get_server_url()

    if not email:
        email = typer.prompt("Email")
    if not password:
        password = typer.prompt("Password", hide_input=True)

    with LambClient(server_url=url) as client:
        resp = client.post_form("/creator/login", data={"email": email, "password": password})

    if isinstance(resp, dict) and resp.get("success"):
        data = resp.get("data", {})
        token = data.get("token", "")
        user_email = data.get("email", email)
        user_name = data.get("name", user_email)
        role = data.get("role", "")
        user_type = data.get("user_type", "")
        org_role = data.get("organization_role", "")
        save_credentials(
            token,
            user_email,
            name=user_name,
            role=role,
            user_type=user_type,
            organization_role=org_role,
        )
        role_info = f" [role: {role}]" if role else ""
        org_info = f" [org role: {org_role}]" if org_role else ""
        print_success(f"Logged in as {user_name} ({user_email}){role_info}{org_info}")
    else:
        detail = resp.get("detail", "Login failed") if isinstance(resp, dict) else "Login failed"
        print_error(str(detail))
        raise typer.Exit(4)


@app.command()
def logout() -> None:
    """Log out and clear stored credentials."""
    clear_credentials()
    print_success("Logged out.")


@app.command()
def status() -> None:
    """Check if the LAMB server is reachable."""
    with get_client(require_auth=False) as client:
        data = client.get("/status")
    if isinstance(data, dict) and data.get("status"):
        print_success(f"Server is running at {get_server_url()}")
    else:
        print_error("Server returned unexpected status.")
        raise typer.Exit(2)


@app.command()
def whoami(
    output: str = typer.Option(None, "-o", "--output", help="Output format: table, json, plain."),
) -> None:
    """Show the currently logged-in user and permission level.

    Platform admins (role=admin) can administer any organization.
    Org admins (organization_role=owner/admin) are scoped to their own org.
    """
    fmt = output or get_output_format()
    with get_client() as client:
        data = client.get("/creator/user/current")
    # Enrich with locally stored role info from login
    stored = get_user_info()
    for key in ("role", "user_type", "organization_role"):
        if key not in data and stored.get(key):
            data[key] = stored[key]
    fields = [
        ("id", "ID"),
        ("email", "Email"),
        ("name", "Name"),
        ("role", "Role"),
        ("user_type", "User Type"),
        ("organization_role", "Org Role"),
    ]
    format_output(data, fields, fmt, detail_fields=fields)


def _cli() -> None:
    """Entry point wrapper with global error handling."""
    try:
        app()
    except LambCliError as exc:
        print_error(str(exc))
        sys.exit(exit_code_for(exc))
    except KeyboardInterrupt:
        sys.exit(130)


# Allow `python -m lamb_cli.main` and the console_scripts entry point.
if __name__ == "__main__":
    _cli()
