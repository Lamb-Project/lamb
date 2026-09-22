"""Deterministic tasks using the caller's LAMB-owned Moodle connection."""
import json
import shlex
from typing import Optional
import httpx
import typer
from lamb_cli.client import get_client

app = typer.Typer(no_args_is_help=True)
analytics_app = typer.Typer(help='Deterministic saved analytics recipes', no_args_is_help=True)
app.add_typer(analytics_app, name='analytics')


@analytics_app.command('capabilities')
def analytics_capabilities(course: int = typer.Option(...,'--course',min=1)):
    run(['analytics','capabilities','--course',str(course)])


@analytics_app.command('run')
def analytics_run(recipe: str, course: int = typer.Option(...,'--course',min=1),
                  since: Optional[str] = typer.Option(None,'--since'),
                  until: Optional[str] = typer.Option(None,'--until'),
                  group: Optional[int] = typer.Option(None,'--group',min=1),
                  tz: str = typer.Option('UTC','--tz'), language: str = typer.Option('en','--language')):
    tokens = ['analytics','run',recipe,'--course',str(course),'--tz',tz,'--language',language]
    if since is not None: tokens += ['--since',since]
    if until is not None: tokens += ['--until',until]
    if group is not None: tokens += ['--group',str(group)]
    run(tokens)


@analytics_app.command('result')
def analytics_result(result_id: str, offset: int = typer.Option(0,'--offset',min=0)):
    run(['analytics','result',result_id,'--offset',str(offset)])


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


document_groups = {}
for _kind in ('page', 'book', 'folder'):
    def make_listing(kind):
        def listing(course_id: int, session: str = typer.Option(..., '--session')):
            document_run([kind, 'list', str(course_id)], session)
        return listing
    group = typer.Typer(no_args_is_help=True)
    group.command('list')(make_listing(_kind))
    app.add_typer(group, name=_kind)
    document_groups[_kind] = group


course_app = typer.Typer(no_args_is_help=True)
app.add_typer(course_app, name='course')


@course_app.command('get')
def document_course(course_id: int, session: str = typer.Option(..., '--session')):
    """Select a verified instructor course before listing its files."""
    document_run(['course', 'get', str(course_id)], session)


@course_app.command('contents')
def document_contents(course_id: int, session: str = typer.Option(..., '--session')):
    """Inspect course modules and their file context IDs."""
    document_run(['course', 'contents', str(course_id)], session)


file_app = typer.Typer(no_args_is_help=True)
app.add_typer(file_app, name='file')


@file_app.command('list')
def document_files(contextid: int, component: str = typer.Option(..., '--component'),
                   filearea: str = typer.Option('content', '--filearea'),
                   filepath: str = typer.Option('/', '--filepath'),
                   itemid: int = typer.Option(0, '--itemid'),
                   session: str = typer.Option(..., '--session')):
    document_run(['file', 'list', str(contextid), '--component', component, '--filearea', filearea,
                  '--filepath', filepath, '--itemid', str(itemid)], session)


import_app = typer.Typer(no_args_is_help=True)
app.add_typer(import_app, name='import')


def folder_selection(kind, source_ref, path, exclude):
    tokens = [*kind, source_ref, '--path', path]
    for value in exclude: tokens += ['--exclude', value]
    return tokens


def ingestion_options(chunk_size, chunk_overlap, splitter_type):
    tokens = []
    for name, value in [('chunk-size', chunk_size), ('chunk-overlap', chunk_overlap), ('splitter-type', splitter_type)]:
        if value is not None: tokens += ['--' + name, str(value)]
    return tokens


@document_groups['folder'].command('inspect')
def inspect_folder(source_ref: str, session: str = typer.Option(..., '--session'),
                   path: str = typer.Option('/', '--path'), exclude: list[str] = typer.Option([], '--exclude')):
    """Preview a recursive folder selection without downloading file contents."""
    document_run(folder_selection(['folder', 'inspect'], source_ref, path, exclude), session)


@import_app.command('folder')
def import_folder(source_ref: str, kb_id: Optional[int] = typer.Argument(None), to: Optional[str] = typer.Option(None, '--to'),
                  new_kb: Optional[str] = typer.Option(None, '--new-kb'), description: Optional[str] = typer.Option(None, '--description'),
                  session: str = typer.Option(..., '--session'), path: str = typer.Option('/', '--path'),
                  chunk_size: Optional[int] = typer.Option(None, '--chunk-size', min=1),
                  chunk_overlap: Optional[int] = typer.Option(None, '--chunk-overlap', min=0),
                  splitter_type: Optional[str] = typer.Option(None, '--splitter-type'),
                  exclude: list[str] = typer.Option([], '--exclude'), confirm: Optional[str] = typer.Option(None, '--confirm')):
    """Review and import a folder tree to one KB. Confirm the returned review ID once."""
    destination = []
    if to is not None: destination += ['--to', to]
    if kb_id is not None: destination += [str(kb_id)]
    if new_kb is not None: destination += ['--new-kb', new_kb]
    if description is not None: destination += ['--description', description]
    document_run(folder_selection(['import', 'folder'], source_ref, path, exclude) + destination
                 + ingestion_options(chunk_size, chunk_overlap, splitter_type), session, confirm)


@document_groups['folder'].command('status')
def folder_status(batch_id: str, session: str = typer.Option(..., '--session')):
    document_run(['folder', 'status', batch_id], session)


@document_groups['folder'].command('finish')
def folder_finish(batch_id: str, session: str = typer.Option(..., '--session'), confirm: Optional[str] = typer.Option(None, '--confirm')):
    document_run(['folder', 'finish', batch_id], session, confirm)


for _kind in ('file', 'page', 'book'):
    def make_import(kind):
        def import_source(source_ref: str, kb_id: Optional[int] = typer.Argument(None),
                          to: Optional[str] = typer.Option(None, '--to'),
                          single_file: bool = typer.Option(False, '--single-file'),
                          chunk_size: Optional[int] = typer.Option(None, '--chunk-size', min=1),
                          chunk_overlap: Optional[int] = typer.Option(None, '--chunk-overlap', min=0),
                          splitter_type: Optional[str] = typer.Option(None, '--splitter-type'),
                          session: str = typer.Option(..., '--session'),
                          confirm: Optional[str] = typer.Option(None, '--confirm', help='Review ID returned by the server.')):
            tokens = ['import', kind, source_ref]
            if to: tokens += ['--to', to]
            if kb_id is not None: tokens += [str(kb_id)]
            if single_file: tokens += ['--single-file']
            document_run(tokens + ingestion_options(chunk_size, chunk_overlap, splitter_type), session, confirm)
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
                   chunk_size: Optional[int] = typer.Option(None, '--chunk-size', min=1),
                   chunk_overlap: Optional[int] = typer.Option(None, '--chunk-overlap', min=0),
                   splitter_type: Optional[str] = typer.Option(None, '--splitter-type'),
                   confirm: Optional[str] = typer.Option(None, '--confirm')):
    document_run(['import', 'refresh', import_id] + ingestion_options(chunk_size, chunk_overlap, splitter_type), session, confirm)


@import_app.command('finish')
def import_finish(import_id: str, session: str = typer.Option(..., '--session'),
                  confirm: Optional[str] = typer.Option(None, '--confirm')):
    document_run(['import', 'finish', import_id], session, confirm)


chart_app = typer.Typer(help='Read-only chart pilot', no_args_is_help=True)
app.add_typer(chart_app, name='chart')

@chart_app.command('list')
def chart_list(offset: int = typer.Option(0, '--offset', min=0)):
    """List your authorized saved charts without collecting new data."""
    run(['chart', 'list', '--offset', str(offset)])

@chart_app.command('read')
def chart_read(chart_id: str):
    """Read the exact saved figures and timestamp of a chart."""
    run(['chart', 'read', chart_id])

@chart_app.command('submissions')
def chart_submissions(course: int = typer.Option(..., '--course', min=1),
                      tz: str = typer.Option('UTC', '--tz'),
                      language: str = typer.Option('en', '--language')):
    """Save a private assignment-submission chart and return its figures/handle."""
    run(['chart', 'submissions', '--course', str(course), '--tz', tz, '--language', language])
