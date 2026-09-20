"""Task vocabulary shared by LiteShell and the authenticated CLI endpoint."""
from functools import lru_cache
import click


@lru_cache(maxsize=1)
def task_specs():
    from .contract import CommandSpec
    news = click.Command('news', params=[
        click.Option(['--all-courses'], is_flag=True),
        click.Option(['--course', 'course_ids'], multiple=True, type=click.IntRange(min=1)),
        click.Option(['--month'], help='Explicit YYYY-MM, new posts only.'),
        click.Option(['--since'], help='Inclusive YYYY-MM-DD.'),
        click.Option(['--until'], help='Exclusive YYYY-MM-DD; required with --since.'),
        click.Option(['--tz'], default='UTC', help='IANA timezone; default UTC is reported.'),
        click.Option(['--max-posts'], default=200, type=click.IntRange(1, 200), help='Matching posts per bounded step, not a total-result limit.'),
    ], help='Check new forum posts across independently verified instructor courses. Returns coverage and a private evidence handle.', add_help_option=False)
    evidence = click.Command('evidence', params=[click.Argument(['result_id']),
        click.Option(['--offset'], default=0, type=click.IntRange(min=0)),
    ], help='Read the next bounded page of an immutable Moodle task result. Follow next_offset until null.', add_help_option=False)
    continuation = click.Command('continue', params=[click.Argument(['result_id'])],
        help='Continue a paused forum run from its result_id. Repeating the same handle returns the same next result.', add_help_option=False)
    runs = click.Command('runs', help='List private recent forum-run recovery handles after Stop or a lost response.', add_help_option=False)
    return {key: CommandSpec(key, parser.help, 'auto', parser)
            for key, parser in [('news', news), ('evidence', evidence), ('continue', continuation), ('runs', runs)]}


def parse_task(tokens):
    if not tokens or tokens[0] != 'moodle':
        return None
    # Descriptive spelling is an alias, not a second implementation.
    if tokens[:3] == ['moodle', 'forum', 'activity']:
        key, tail = 'news', tokens[3:]
    elif len(tokens) >= 2 and tokens[1] in task_specs():
        key, tail = tokens[1], tokens[2:]
    else:
        return None
    spec = task_specs()[key]
    params = spec.parse(tail)
    if key == 'news':
        from .forum_activity import validate_request
        validate_request(params)
    elif key in {'evidence', 'continue'}:
        from uuid import UUID
        try:
            params['result_id'] = str(UUID(params['result_id']))
        except (ValueError, TypeError):
            raise ValueError('Use the result_id returned by moodle news') from None
    return spec, params
