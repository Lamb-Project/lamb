"""Model-facing evidence notes selected from moodle-cli's canonical glossary.

moodle-cli owns every definition. This adapter only chooses term IDs for LAMB
commands and renders them compactly. Notes are keyed by the harness-owned
command identity, never taken from result data, so a source cannot forge them.
"""
from moodle_cli.glossary import TERMS, terms_for_command

BASE = ('response_scope', 'missing_value')
FORUM_WINDOW = ('forum_identity', 'forum_post', 'date_window', 'timestamp')
SUBMISSION_CHART = ('assignment_status', 'submission_modified', 'assignment_due', 'snapshot')

# Cached sections hold the same service records as these upstream commands.
CACHE_SECTIONS = {
    'course': ('enrol.my-courses',),
    'forums': ('forum.list', 'forum.discussions'),
    'assignments': ('assign.list', 'assign.submissions'),
    'enrolment': ('enrol.list-users',),
    'calendar': ('calendar.course',),
}

# LAMB outputs with no upstream command of their own. Aggregates get only terms
# that describe them; raw-field definitions are not borrowed for derived numbers.
LAMB_TERMS = {
    'sync': ('snapshot',),  # Returns sync times and deltas, not section records.
    'news': FORUM_WINDOW,
    'evidence': FORUM_WINDOW,  # Pages of news task results.
    'continue': FORUM_WINDOW,
    'chart.submissions': SUBMISSION_CHART,
    'chart.read': SUBMISSION_CHART,
    'chart.list': ('snapshot',),
    'page.list': ('module_identity', 'resource_listing'),
    'book.list': ('module_identity', 'resource_listing'),
    'folder.list': ('module_identity', 'resource_listing', 'file'),
    'folder.inspect': ('resource_listing', 'file'),
}

# Deliberately uncovered: recovery handles and LAMB ingestion state describe
# LAMB's own operations, not Moodle evidence.
UNCOVERED = frozenset({'runs', 'folder.status', 'folder.finish', 'import.folder', 'import.file',
                       'import.page', 'import.book', 'import.finish', 'import.list', 'import.check',
                       'import.refresh'})


def glossary_key(command_key, kwargs=None):
    """Harness-owned selector for a Moodle command, or None for anything else."""
    if not isinstance(command_key, str) or not command_key.startswith('moodle.'):
        return None
    key = command_key.removeprefix('moodle.')
    if key == 'cache.show':
        section = (kwargs or {}).get('section')
        return f'cache.show:{section}' if section in CACHE_SECTIONS else None
    return key


def term_ids(key):
    if not isinstance(key, str) or key in UNCOVERED:
        return ()
    if key.startswith('cache.show:'):
        commands = CACHE_SECTIONS.get(key.removeprefix('cache.show:'), ())
        ids = [term for command in commands for term in terms_for_command(command)]
        return tuple(dict.fromkeys((*ids, 'snapshot'))) if ids else ()
    if key in LAMB_TERMS:
        return tuple(dict.fromkeys((*BASE, *LAMB_TERMS[key])))
    return tuple(terms_for_command(key))


def field_notes(key):
    """One compact note per applicable term: definition, then its limitation."""
    return {term: f"{TERMS[term]['definition']} Limit: {TERMS[term]['limitation']}"
            for term in term_ids(key) if term in TERMS}
