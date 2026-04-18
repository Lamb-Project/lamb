"""Generic escape hatch: call any Moodle WS function directly."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import render_json
from moodle_cli.output.console import console


@click.command()
@click.argument("function_name")
@click.option("-P", "--param", multiple=True, help="Parameter as key=value (repeatable)")
@pass_context
@handle_errors
def call(ctx: MoodleContext, function_name: str, param: tuple[str, ...]) -> None:
    """Call any Moodle web service function directly.

    Example: moodle call core_webservice_get_site_info
    Example: moodle call core_course_get_courses -P options[ids][0]=2
    """
    client = ctx.get_client()
    params = {}
    for p in param:
        if "=" not in p:
            raise click.BadParameter(f"Parameter must be key=value, got: {p}")
        key, value = p.split("=", 1)
        params[key] = value

    # Build the raw POST data (bypass flatten_params since user provides raw keys)
    data = {
        "wstoken": client.token,
        "wsfunction": function_name,
        "moodlewsrestformat": "json",
        **params,
    }

    import httpx
    resp = httpx.post(client.rest_url, data=data, timeout=30.0)
    result = resp.json()

    if isinstance(result, dict) and "exception" in result:
        from moodle_cli.client.exceptions import MoodleAPIError
        raise MoodleAPIError(
            message=result.get("message", "Unknown error"),
            error_code=result.get("errorcode"),
            debug_info=result.get("debuginfo"),
        )

    if ctx.json_output:
        render_json(result)
    else:
        # Always JSON for generic call
        render_json(result)
        count_info = ""
        if isinstance(result, list):
            count_info = f" ({len(result)} items)"
        elif isinstance(result, dict):
            count_info = f" ({len(result)} keys)"
        console.print(f"[dim]{function_name}{count_info}[/dim]")
