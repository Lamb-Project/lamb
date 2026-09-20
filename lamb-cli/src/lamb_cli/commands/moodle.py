"""Deterministic tasks using the caller's LAMB-owned Moodle connection."""
import json
import shlex
from typing import Optional
import httpx
import typer
from lamb_cli.client import get_client

app = typer.Typer(no_args_is_help=True)


def run(tokens):
    # Read timeout covers the bounded server traversal. Connection/pool failures
    # still fail promptly. No workstation Moodle profile or token is inspected.
    with get_client(timeout=httpx.Timeout(120, connect=5, pool=5, write=10)) as client:
        result = client.post('/creator/moodle/tasks', json={'command': shlex.join(['moodle', *tokens])})
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def news(
    all_courses: bool = typer.Option(False, '--all-courses'),
    course: Optional[list[int]] = typer.Option(None, '--course'),
    month: Optional[str] = typer.Option(None, '--month'),
    since: Optional[str] = typer.Option(None, '--since'),
    until: Optional[str] = typer.Option(None, '--until', help='Exclusive end date.'),
    tz: str = typer.Option('UTC', '--tz'),
    max_posts: int = typer.Option(200, '--max-posts', min=1, max=200, help="Matching posts per step."),
):
    """New forum posts in verified instructor courses, with coverage and evidence."""
    tokens = ['news', '--tz', tz, '--max-posts', str(max_posts)]
    if all_courses: tokens.append('--all-courses')
    for value in course or []: tokens += ['--course', str(value)]
    for key, value in [('month', month), ('since', since), ('until', until)]:
        if value is not None: tokens += ['--' + key, value]
    run(tokens)


@app.command()
def evidence(result_id: str, offset: int = typer.Option(0, '--offset', min=0)):
    """Read a bounded evidence page. Follow next_offset until null."""
    run(['evidence', result_id, '--offset', str(offset)])


forum_app = typer.Typer(no_args_is_help=True)
forum_app.command('activity')(news)
app.add_typer(forum_app, name='forum')


@app.command('continue')
def continue_run(result_id: str):
    """Continue a saved forum check; retrying the same result is idempotent."""
    run(['continue', result_id])


@app.command()
def runs():
    """List recovery handles for recent forum checks, including interrupted ones."""
    run(['runs'])
