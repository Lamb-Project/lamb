"""Bounded document tasks shared by AAC and lamb-cli."""
from functools import lru_cache
import click

IMPORT_KEYS = frozenset({'import.file', 'import.page', 'import.book', 'import.refresh', 'import.folder'})


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
    add('import.folder', selection() + [click.Option(['--to'], type=click.Choice(['kb']), required=True),
        click.Argument(['kb_id'], type=click.IntRange(min=1))],
        'Review a bounded recursive folder import into an owned KB; one approval covers the exact file set.', 'ask')
    add('folder.status', [click.Argument(['batch_id'])], 'Report each file in your approved folder batch; status inspection never starts uploads.')
    add('folder.finish', [click.Argument(['batch_id'])], 'Resume the exact approved folder batch after rechecking scope and sources; never duplicate completed uploads.', 'ask')
    for kind in ('file', 'page', 'book'):
        add('import.' + kind, [click.Argument(['source_ref']), click.Option(['--to'], type=click.Choice(['kb'])),
            click.Argument(['kb_id'], required=False, type=click.IntRange(min=1)), click.Option(['--single-file'], is_flag=True)],
            'Review and import a listed ' + kind + ' into an owned KB or single-file grounding.', 'ask')
    add('import.finish', [click.Argument(['import_id'])], 'Finish a previously approved ingestion/replacement after its KB job completes; never downloads or starts another upload.', 'ask')
    add('import.list', [], 'List your imported Moodle documents, destinations and provenance.')
    add('import.check', [click.Argument(['import_id']), click.Option(['--verify-content'], is_flag=True)],
        'Compare source metadata without downloading files; --verify-content explicitly downloads and hashes the source.')
    add('import.refresh', [click.Argument(['import_id'])],
        'Review and replace an imported document from its verified source. Previous content is retained until the replacement succeeds.', 'ask')
    return specs


def parse_document(tokens):
    if len(tokens) < 3: return None
    key = '.'.join(tokens[1:3])
    spec = document_specs().get(key)
    if not spec: return None
    params = spec.parse(tokens[3:])
    if key in IMPORT_KEYS - {'import.refresh', 'import.folder'}:
        if not ((params['single_file'] and params['to'] is None and params['kb_id'] is None) or
                (not params['single_file'] and params['to'] == 'kb' and params['kb_id'] is not None)):
            raise ValueError('Choose --single-file or --to kb ID')
    return spec, params
