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
    course: Optional[list[int]] = typer.Option(None, '--course', help='Repeat for several courses in one run.'),
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


def document_run(tokens, session, confirm=None):
    with get_client(timeout=httpx.Timeout(180, connect=5, pool=5, write=10)) as client:
        result = client.post('/creator/moodle/documents/commands', json={
            'session': session, 'command': shlex.join(['moodle', *tokens]), 'confirm': confirm})
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


documents_app = typer.Typer(no_args_is_help=True)
app.add_typer(documents_app, name='documents')


@documents_app.command('start')
def documents_start():
    """Start an owned document session; pass its ID to listing/import commands."""
    with get_client() as client:
        result = client.post('/creator/moodle/documents/sessions')
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


for _kind in ('page', 'book'):
    def make_listing(kind):
        def listing(course_id: int, session: str = typer.Option(..., '--session')):
            document_run([kind, 'list', str(course_id)], session)
        return listing
    group = typer.Typer(no_args_is_help=True)
    group.command('list')(make_listing(_kind))
    app.add_typer(group, name=_kind)


course_app = typer.Typer(no_args_is_help=True)
app.add_typer(course_app, name='course')


@course_app.command('get')
def document_course(course_id: int, session: str = typer.Option(..., '--session')):
    """Select a verified instructor course before listing its files."""
    document_run(['course', 'get', str(course_id)], session)


file_app = typer.Typer(no_args_is_help=True)
app.add_typer(file_app, name='file')


@file_app.command('list')
def document_files(contextid: int, component: str = typer.Option(..., '--component'),
                   filearea: str = typer.Option('content', '--filearea'),
                   session: str = typer.Option(..., '--session')):
    document_run(['file', 'list', str(contextid), '--component', component, '--filearea', filearea], session)


import_app = typer.Typer(no_args_is_help=True)
app.add_typer(import_app, name='import')


for _kind in ('file', 'page', 'book'):
    def make_import(kind):
        def import_source(source_ref: str, kb_id: Optional[int] = typer.Argument(None),
                          to: Optional[str] = typer.Option(None, '--to'),
                          single_file: bool = typer.Option(False, '--single-file'),
                          session: str = typer.Option(..., '--session'),
                          confirm: Optional[str] = typer.Option(None, '--confirm', help='Review ID returned by the server.')):
            tokens = ['import', kind, source_ref]
            if to: tokens += ['--to', to]
            if kb_id is not None: tokens += [str(kb_id)]
            if single_file: tokens += ['--single-file']
            document_run(tokens, session, confirm)
        return import_source
    import_app.command(_kind)(make_import(_kind))


@import_app.command('list')
def imports_list(session: str = typer.Option(..., '--session')):
    document_run(['import', 'list'], session)


@import_app.command('check')
def import_check(import_id: str, session: str = typer.Option(..., '--session'),
                 verify_content: bool = typer.Option(False, '--verify-content')):
    tokens = ['import', 'check', import_id]
    if verify_content: tokens += ['--verify-content']
    document_run(tokens, session)


@import_app.command('refresh')
def import_refresh(import_id: str, session: str = typer.Option(..., '--session'),
                   confirm: Optional[str] = typer.Option(None, '--confirm')):
    document_run(['import', 'refresh', import_id], session, confirm)


@import_app.command('finish')
def import_finish(import_id: str, session: str = typer.Option(..., '--session'),
                  confirm: Optional[str] = typer.Option(None, '--confirm')):
    document_run(['import', 'finish', import_id], session, confirm)
