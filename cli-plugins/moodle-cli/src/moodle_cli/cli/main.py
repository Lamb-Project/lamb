"""Root CLI group and shared context."""

from __future__ import annotations

import functools
import sys
from typing import Any

import click

from moodle_cli import __version__
from moodle_cli.client.exceptions import MoodleAPIError, MoodleError
from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.config.auth import TokenStore
from moodle_cli.config.manager import ConfigManager
from moodle_cli.output.console import error_console


class MoodleContext:
    """Shared state passed through Click context."""

    def __init__(
        self,
        profile: str | None = None,
        json_output: bool = False,
        verbose: bool = False,
    ) -> None:
        self.profile_name = profile
        self.json_output = json_output
        self.verbose = verbose
        self._config_mgr = ConfigManager()
        self._token_store = TokenStore()
        self._client: MoodleHTTPClient | None = None

    @property
    def config(self) -> ConfigManager:
        return self._config_mgr

    @property
    def tokens(self) -> TokenStore:
        return self._token_store

    def get_client(self) -> MoodleHTTPClient:
        """Build an authenticated MoodleHTTPClient from the active profile."""
        if self._client is not None:
            return self._client
        name, profile = self._config_mgr.get_profile(self.profile_name)
        token = self._token_store.get(name)
        if not token:
            error_console.print(
                f"[red]No token for profile '{name}'. Run: moodle auth login[/red]"
            )
            sys.exit(1)
        self._client = MoodleHTTPClient(
            base_url=profile.url, token=token, service=profile.service
        )
        return self._client


pass_context = click.make_pass_decorator(MoodleContext, ensure=True)


def handle_errors(fn: Any) -> Any:
    """Decorator that catches MoodleError and prints friendly messages."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except MoodleAPIError as exc:
            error_console.print(f"[red]Moodle API error:[/red] {exc}")
            if exc.hint:
                error_console.print(f"[yellow]Hint:[/yellow] {exc.hint}")
            if exc.debug_info:
                error_console.print(f"[dim]Debug: {exc.debug_info}[/dim]")
            sys.exit(1)
        except MoodleError as exc:
            error_console.print(f"[red]Error:[/red] {exc}")
            sys.exit(1)

    return wrapper


@click.group()
@click.option("--profile", "-p", default=None, help="Profile name to use.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output.")
@click.version_option(version=__version__, prog_name="moodle-cli")
@click.pass_context
def cli(ctx: click.Context, profile: str | None, json_output: bool, verbose: bool) -> None:
    """moodle-cli — interact with Moodle from the terminal.

    Copyright (C) 2026 Marc Alier, Juanan Pereira — LAMB Project

    Licensed under the GNU General Public License v3.0 (GPL-3.0-or-later).
    See https://github.com/Lamb-Project/moodle-cli for source code.
    """
    ctx.ensure_object(dict)
    ctx.obj = MoodleContext(profile=profile, json_output=json_output, verbose=verbose)


# Import and register command groups (deferred to avoid circular imports)
def _register_commands() -> None:
    from moodle_cli.cli.assign import assign
    from moodle_cli.cli.auth import auth
    from moodle_cli.cli.calendar import calendar
    from moodle_cli.cli.call import call
    from moodle_cli.cli.cohort import cohort
    from moodle_cli.cli.completion import completion
    from moodle_cli.cli.course import course
    from moodle_cli.cli.enrol import enrol
    from moodle_cli.cli.file import file
    from moodle_cli.cli.forum import forum
    from moodle_cli.cli.grade import grade
    from moodle_cli.cli.message import message
    from moodle_cli.cli.quiz import quiz
    from moodle_cli.cli.role import role
    from moodle_cli.cli.site import site
    from moodle_cli.cli.user import user

    cli.add_command(auth)
    cli.add_command(site)
    cli.add_command(course)
    cli.add_command(user)
    cli.add_command(enrol)
    cli.add_command(grade)
    cli.add_command(assign)
    cli.add_command(forum)
    cli.add_command(quiz)
    cli.add_command(calendar)
    cli.add_command(message)
    cli.add_command(completion)
    cli.add_command(file)
    cli.add_command(cohort)
    cli.add_command(role)
    cli.add_command(call)


_register_commands()
