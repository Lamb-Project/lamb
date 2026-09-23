"""Task vocabulary shared by LiteShell and the authenticated CLI endpoint."""
from functools import lru_cache
import click


@lru_cache(maxsize=1)
def task_specs():
    from .contract import CommandSpec
    window = click.Command('window', params=[
        click.Option(['--since'],required=True,help='Inclusive local date YYYY-MM-DD.'),
        click.Option(['--through'],help='Inclusive last local date YYYY-MM-DD.'),
        click.Option(['--until'],help='Exclusive end local date YYYY-MM-DD; alternative to --through.'),
        click.Option(['--tz'],default='UTC',help='IANA timezone.')],
        help='Plan exact event-calendar bounds locally, preserving unsupported intervals. Does not inspect data availability or call Moodle.',
        add_help_option=False)
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
        click.Option(['--forum','forum_id'],type=click.IntRange(min=1)),
        click.Option(['--quiz','quiz_id'],type=click.IntRange(min=1)),
        click.Option(['--attempt-policy'],type=click.Choice(['first_finished','latest_finished','best_scored_finished','all_finished'])),
        click.Option(['--assignment','assignment_id'], type=click.IntRange(min=1)),
        click.Option(['--course','course_id'], required=True, type=click.IntRange(min=1)),
        click.Option(['--since'], help='Inclusive local date, YYYY-MM-DD.'),
        click.Option(['--until'], help='Exclusive local date; required for deadlines, otherwise omitted means now for view recipes.'),
        click.Option(['--through'], help='Inclusive last local date for event recipes; alternative to --until.'),
        click.Option(['--group','group_id'], type=click.IntRange(min=1)),
        click.Option(['--tz'], default='UTC'),
        click.Option(['--language'], default='en', type=click.Choice(['en','es','ca','eu'])),
    ], help='Run deterministic analytics. Completion uses a recoverable first step: follow continue_command until a chart_id is returned. Does not modify Moodle.', add_help_option=False)
    analytics_capabilities = click.Command('capabilities', params=[
        click.Option(['--course','course_id'],required=True,type=click.IntRange(min=1))],
        help='Inspect implemented recipe source requirements and advertised functions; field support remains unknown until read.', add_help_option=False)
    analytics_result = click.Command('result', params=[click.Argument(['chart_id']),
        click.Option(['--offset'],default=0,type=click.IntRange(min=0))],
        help='Read a bounded page from a saved analytics snapshot, with fresh permission checks and no recollection.', add_help_option=False)
    analytics_start = click.Command('start', params=[click.Argument(['recipe'],type=click.Choice(['activity-completion','quiz-overview','forum-participation','forum-discussions'])),
        click.Option(['--forum','forum_id'],type=click.IntRange(min=1)),
        click.Option(['--since']),click.Option(['--until']),click.Option(['--through']),
        click.Option(['--quiz','quiz_id'],type=click.IntRange(min=1)),
        click.Option(['--attempt-policy'],type=click.Choice(['first_finished','latest_finished','best_scored_finished','all_finished'])),
        click.Option(['--group','group_id'],type=click.IntRange(min=1)),
        click.Option(['--course','course_id'],required=True,type=click.IntRange(min=1)),
        click.Option(['--tz'],default='UTC'),click.Option(['--language'],default='en',type=click.Choice(['en','es','ca','eu']))],
        help='Create a recoverable completion, quiz or forum run. Forum requires --forum, --since and --until (exclusive) or --through (inclusive). Quiz requires --quiz and --attempt-policy. Follow continue_command; no chart exists yet.',add_help_option=False)
    analytics_continue = click.Command('continue',params=[click.Argument(['run_id']),
        click.Option(['--step'],required=True,type=click.IntRange(min=0))],
        help='Advance one bounded analytics step. Retry the exact command after interruption or a lost response.',add_help_option=False)
    analytics_runs = click.Command('runs',help='List authorized private completion, quiz and forum recovery handles; no learner IDs are returned.',add_help_option=False)
    return {key: CommandSpec(key, parser.help, 'auto', parser)
            for key, parser in [('analytics.window',window), ('news', news), ('evidence', evidence), ('continue', continuation), ('runs', runs), ('chart.submissions', chart), ('chart.list', chart_list), ('chart.read', chart_read), ('analytics.run', analytics_run), ('analytics.capabilities', analytics_capabilities), ('analytics.result', analytics_result), ('analytics.start',analytics_start), ('analytics.continue',analytics_continue), ('analytics.runs',analytics_runs)]}


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
    if key == 'analytics.window':
        from .analytics.window import plan_window
        plan_window(**params)
    if key in {'chart.read','analytics.result'}:
        from uuid import UUID
        try: params['chart_id'] = str(UUID(params['chart_id']))
        except (ValueError, TypeError): raise ValueError('Use a saved chart_id') from None
    if key == 'analytics.continue':
        from uuid import UUID
        try:params['run_id']=str(UUID(params['run_id']))
        except (ValueError,TypeError):raise ValueError('Use an analytics run_id') from None
    if key in {'analytics.run','analytics.start'}:
        if params['recipe'] in {'forum-participation','forum-discussions'}:
            from .analytics.forum_window import parse_window
            if params.get('forum_id') is None:
                raise ValueError('Forum analytics requires --forum')
            if any(params.get(field) is not None for field in ('quiz_id','attempt_policy','assignment_id')):
                raise ValueError('Quiz and assignment options do not apply to forum analytics')
            params['since'],params['until']=parse_window(params.get('since'),params.get('until'),
                                                       params.pop('through',None),params['tz'])
            params['group_id']=params.get('group_id') or 0
            return spec,params
        if params.get('forum_id') is not None:
            raise ValueError('--forum applies only to forum analytics')
        if key=='analytics.start' and any(params.get(field) is not None for field in ('since','until','through')):
            raise ValueError('Date options apply only to forum analytics start')
        if params['recipe'] == 'quiz-overview':
            if params.get('quiz_id') is None or params.get('attempt_policy') is None:
                raise ValueError('Quiz overview requires --quiz and --attempt-policy')
        elif params.get('quiz_id') is not None or params.get('attempt_policy') is not None:
            raise ValueError('--quiz and --attempt-policy apply only to quiz-overview')
        if key == 'analytics.start' and params['recipe'] != 'quiz-overview' and params.get('group_id') is not None:
            raise ValueError('--group is not supported for completion collection')
    if key in {'chart.submissions','analytics.run','analytics.start'}:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try: ZoneInfo(params['tz'])
        except (ValueError, ZoneInfoNotFoundError): raise ValueError('Use an IANA timezone') from None
    if key == 'analytics.run':
        from datetime import date
        from .analytics.window import EVENT_RECIPES, plan_window, require_event_window
        through = params.pop('through', None)
        if through is not None:
            if params['recipe'] not in EVENT_RECIPES:
                raise ValueError('--through applies only to recorded-event recipes')
            plan = plan_window(params['since'],until=params['until'],through=through,tz=params['tz'])
            params['until'] = plan['until']
        if params['recipe'] == 'grade-distribution':
            if params['assignment_id'] is None:
                raise ValueError('Grade distribution requires --assignment ID')
        elif params['assignment_id'] is not None:
            raise ValueError('--assignment applies only to grade-distribution')
        if params['recipe'] in {'deadlines','course-access','resource-reach','view-trends','view-heatmap','view-distribution','active-day-distribution'}:
            try: date.fromisoformat(params['since'])
            except (ValueError, TypeError): raise ValueError('This recipe requires --since YYYY-MM-DD') from None
        elif params['since'] is not None:
            raise ValueError('--since does not apply to this recipe')
        if params['recipe'] == 'deadlines':
            try: end = date.fromisoformat(params['until'])
            except (ValueError, TypeError): raise ValueError('Deadlines requires --until YYYY-MM-DD') from None
            if not 0 < (end-date.fromisoformat(params['since'])).days <= 370:
                raise ValueError('Use a deadline window of 1 to 370 local days')
            if params['group_id'] is not None:
                raise ValueError('Deadlines shows stored course defaults; --group does not apply')
        elif params['recipe'] in {'resource-reach','view-trends','view-heatmap','view-distribution','active-day-distribution'}:
            if params['until'] is not None:
                try: end = date.fromisoformat(params['until'])
                except (ValueError, TypeError): raise ValueError('Use --until YYYY-MM-DD') from None
                if end <= date.fromisoformat(params['since']): raise ValueError('--until must follow --since')
                require_event_window(params['since'], params['until'], params['tz'])
        elif params['recipe'] == 'quiz-overview':
            if params['until'] is not None:
                raise ValueError('--until does not apply to quiz-overview')
        elif params['until'] is not None or params['group_id'] is not None:
            raise ValueError('--until and --group apply only to resource reach and recorded-view recipes')
    if key in {'analytics.run','analytics.start'} and params['recipe'] == 'quiz-overview':
        params['group_id'] = params.get('group_id') or 0
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
