"""Bounded document tasks shared by AAC and lamb-cli."""
from functools import lru_cache
import click
from .ingestion import options, configuration

IMPORT_KEYS = frozenset({'import.file', 'import.page', 'import.book', 'import.refresh', 'import.folder', 'import.course'})


@lru_cache(maxsize=1)
def document_specs():
    from .contract import CommandSpec
    specs = {}
    def add(key, params, description, policy='auto'):
        parser = click.Command(key, params=params, help=description, add_help_option=False)
        specs[key] = CommandSpec(key, description, policy, parser)
    for kind in ('page', 'book', 'folder'):
        add(kind + '.list', [click.Argument(['course_id'], type=click.IntRange(min=1))],
            'List Moodle ' + kind + ' metadata and session-bound import references. No document bodies.')
    def selection():
        return [click.Argument(['source_ref']), click.Option(['--path'], default='/'),
                click.Option(['--exclude'], multiple=True)]
    add('folder.inspect', selection(), 'Scan a Moodle Folder recursively; report supported and excluded paths without downloading bodies.')
    add('import.folder', selection() + [click.Option(['--to'], type=click.Choice(['kb'])),
        click.Argument(['kb_id'], required=False, type=click.IntRange(min=1)),
        click.Option(['--new-kb']), click.Option(['--description'])] + options(),
        'Review a bounded recursive folder import into an owned KB; one approval covers the exact file set.', 'ask')
    add('import.course', [click.Argument(['course_id'], type=click.IntRange(min=1)),
        click.Option(['--module'], multiple=True, required=True, type=click.IntRange(min=1)),
        click.Option(['--to'], type=click.Choice(['kb'])), click.Argument(['kb_id'], required=False, type=click.IntRange(min=1)),
        click.Option(['--new-kb']), click.Option(['--description'])] + options(),
        'Review one batch import of documents chosen across a course (course-module ids from the course inventory: '
        'Resource files, Folder files, Pages, Books) into an owned or new KB; one approval covers the exact set.', 'ask')
    add('folder.status', [click.Argument(['batch_id'])], 'Report each file in your approved folder or course batch; status inspection never starts uploads.')

    add('folder.finish', [click.Argument(['batch_id'])], 'Resume the exact approved folder or course batch after rechecking scope and sources; never duplicate completed uploads.', 'ask')
    for kind in ('file', 'page', 'book'):
        add('import.' + kind, [click.Argument(['source_ref']), click.Option(['--to'], type=click.Choice(['kb'])),
            click.Argument(['kb_id'], required=False, type=click.IntRange(min=1)), click.Option(['--single-file'], is_flag=True)] + options(),
            'Review and import a listed ' + kind + ' into an owned KB or single-file grounding.', 'ask')
    # Reading (#525): a helper model reads; the text stays in a private 24-hour snapshot.
    add('file.read', [click.Argument(['source_ref'])],
        'Read a listed file (FILE_ID from moodle file list) without importing it: a helper model returns an overview '
        '(summary, outline with passage ids and pages, key terms) and a READ_ID for follow-ups. No knowledge base, no approval.')
    for kind in ('page', 'book'):
        add(kind + '.read', [click.Argument(['source_ref'])],
            'Read a listed Moodle ' + kind + ' (SOURCE_REF from moodle ' + kind + ' list) without importing it; same overview and READ_ID.')
    def part():
        return [click.Argument(['read_id']), click.Option(['--passages']), click.Option(['--pages'])]
    add('read.summary', part() + [click.Option(['--section']), click.Option(['--focus'])],
        'Extended summary by the helper model of part of a read document (--passages p3-p9, --pages 2-4 or --section TITLE; '
        'whole document if omitted), with passage citations. --focus narrows what it attends to.')
    add('read.ask', [click.Argument(['read_id']), click.Argument(['question'])],
        'Ask the helper model one question about a read document; the answer cites passages and quotes exact wording when asked.')
    add('read.verbatim', part() + [click.Option(['--find']), click.Option(['--offset'], type=click.IntRange(min=0), default=0)],
        'Exact text of selected passages (--passages, --pages or --find TEXT), paged with --offset. Untrusted source text.')
    add('import.finish', [click.Argument(['import_id'])], 'Finish a previously approved ingestion/replacement after its KB job completes; never downloads or starts another upload.', 'ask')
    add('import.list', [], 'List your imported Moodle documents, destinations and provenance.')
    add('import.check', [click.Argument(['import_id']), click.Option(['--verify-content'], is_flag=True)],
        'Compare source metadata without downloading files; --verify-content explicitly downloads and hashes the source.')
    add('import.refresh', [click.Argument(['import_id'])] + options(),
        'Review and replace an imported document from its verified source. Previous content is retained until the replacement succeeds.', 'ask')
    return specs


def parse_document(tokens):
    if len(tokens) < 3: return None
    key = '.'.join(tokens[1:3])
    spec = document_specs().get(key)
    if not spec: return None
    params = spec.parse(tokens[3:])
    if key in {'import.folder', 'import.course'}:
        new = params.get('new_kb')
        existing = params.get('to') == 'kb' and params.get('kb_id') is not None
        if not ((new and new.strip() and len(new) <= 200 and params.get('to') is None and params.get('kb_id') is None)
                or (existing and new is None and params.get('description') is None)):
            raise ValueError('Choose --to kb ID or --new-kb NAME [--description TEXT]')
        if params.get('description') and len(params['description']) > 4000:
            raise ValueError('Knowledge base description is limited to 4000 characters')
    if key in IMPORT_KEYS - {'import.refresh', 'import.folder', 'import.course'}:
        if not ((params['single_file'] and params['to'] is None and params['kb_id'] is None) or
                (not params['single_file'] and params['to'] == 'kb' and params['kb_id'] is not None)):
            raise ValueError('Choose --single-file or --to kb ID')
    if key in IMPORT_KEYS and key != 'import.refresh':
        configuration(params, single_file=params.get('single_file', False))
    # Omitted options stay absent so old pending reviews/batches remain comparable.
    params = {k: v for k, v in params.items() if v is not None or k not in {'chunk_size', 'chunk_overlap', 'splitter_type', 'new_kb', 'description'}}
    return spec, params
