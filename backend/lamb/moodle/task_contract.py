"""Task vocabulary shared by LiteShell and the authenticated CLI endpoint."""
from functools import lru_cache
import click


@lru_cache(maxsize=1)
def task_specs():
    from .contract import CommandSpec
    news = click.Command('news', params=[
        click.Option(['--all-courses'], is_flag=True),
        click.Option(['--course', 'course_ids'], multiple=True, type=click.IntRange(min=1), help='Repeat in ONE call for several selected courses: --course 12 --course 34.'),
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
    chart = click.Command('submissions', params=[
        click.Option(['--course', 'course_id'], required=True, type=click.IntRange(min=1)),
        click.Option(['--tz'], default='UTC'),
        click.Option(['--language'], default='en', type=click.Choice(['en', 'es', 'ca', 'eu'])),
    ], help='Pilot: chart current assignment submissions against course deadlines. Read-only; at most 20 assignments. Team/offline assignments are excluded explicitly.', add_help_option=False)
    chart_list = click.Command('list', params=[
        click.Option(['--offset'], default=0, type=click.IntRange(min=0)),
    ], help='List a bounded page of your authorized saved charts, newest first. Follow next_offset. Does not refresh Moodle data.', add_help_option=False)
    chart_read = click.Command('read', params=[click.Argument(['chart_id'])],
        help='Read exact figures, date and limitations from an authorized saved chart. Does not refresh it.', add_help_option=False)
    from .analytics.recipes import RECIPES
    analytics_run = click.Command('run', params=[
        click.Argument(['recipe'], type=click.Choice(list(RECIPES))),
        click.Option(['--course','course_id'], required=True, type=click.IntRange(min=1)),
        click.Option(['--since'], help='Course-access recency boundary, YYYY-MM-DD.'),
        click.Option(['--tz'], default='UTC'),
        click.Option(['--language'], default='en', type=click.Choice(['en','es','ca','eu'])),
    ], help='Run a deterministic analytics recipe and save its aggregate evidence. Does not modify Moodle.', add_help_option=False)
    analytics_capabilities = click.Command('capabilities', params=[
        click.Option(['--course','course_id'],required=True,type=click.IntRange(min=1))],
        help='Inspect implemented recipe source requirements and advertised functions; field support remains unknown until read.', add_help_option=False)
    analytics_result = click.Command('result', params=[click.Argument(['chart_id']),
        click.Option(['--offset'],default=0,type=click.IntRange(min=0))],
        help='Read a bounded page from a saved analytics snapshot, with fresh permission checks and no recollection.', add_help_option=False)
    return {key: CommandSpec(key, parser.help, 'auto', parser)
            for key, parser in [('news', news), ('evidence', evidence), ('continue', continuation), ('runs', runs), ('chart.submissions', chart), ('chart.list', chart_list), ('chart.read', chart_read), ('analytics.run', analytics_run), ('analytics.capabilities', analytics_capabilities), ('analytics.result', analytics_result)]}


def parse_task(tokens):
    if not tokens or tokens[0] != 'moodle':
        return None
    # Descriptive spelling is an alias, not a second implementation.
    if len(tokens) >= 3 and tokens[1] in {'chart','analytics'} and tokens[1] + '.' + tokens[2] in task_specs():
        key, tail = tokens[1] + '.' + tokens[2], tokens[3:]
    elif tokens[:3] == ['moodle', 'forum', 'activity']:
        key, tail = 'news', tokens[3:]
    elif len(tokens) >= 2 and tokens[1] in task_specs():
        key, tail = tokens[1], tokens[2:]
    else:
        return None
    spec = task_specs()[key]
    params = spec.parse(tail)
    if key in {'chart.read','analytics.result'}:
        from uuid import UUID
        try: params['chart_id'] = str(UUID(params['chart_id']))
        except (ValueError, TypeError): raise ValueError('Use a saved chart_id') from None
    if key in {'chart.submissions','analytics.run'}:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try: ZoneInfo(params['tz'])
        except (ValueError, ZoneInfoNotFoundError): raise ValueError('Use an IANA timezone') from None
    if key == 'analytics.run':
        from datetime import date
        if params['recipe'] == 'course-access':
            try: date.fromisoformat(params['since'])
            except (ValueError, TypeError): raise ValueError('Course access requires --since YYYY-MM-DD') from None
        elif params['since'] is not None:
            raise ValueError('--since applies only to course-access')
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
