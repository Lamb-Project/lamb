"""Local, fail-closed command discovery from validated token capabilities.

Function exposure is not course authorization. Execution retains live scope checks.
No command probing, token decryption or Moodle requests belong in this module.
"""
from copy import deepcopy
import re

import click

IDENTITY = {'core_enrol_get_users_courses', 'core_user_get_course_user_profiles'}
CONTENTS = {'core_course_get_contents'}
ROSTER = {'core_enrol_get_enrolled_users'}

# Reviewed execution bindings, including LAMB overrides of moodle-cli commands.
FUNCTIONS = {
    'site.info': 'core_webservice_get_site_info',
    'site.functions': 'core_webservice_get_site_info',
    'user.me': 'core_webservice_get_site_info',
    'course.list': 'core_enrol_get_users_courses',
    'course.search': 'core_enrol_get_users_courses',
    'enrol.my-courses': 'core_enrol_get_users_courses',
    'course.get': '',
    'course.contents': 'core_course_get_contents',
    'course.module': 'core_course_get_course_module',
    'course.categories': 'core_course_get_categories',
    'course.timeline': 'core_course_get_enrolled_courses_by_timeline_classification',
    'enrol.list-users': 'core_enrol_get_enrolled_users',
    'enrol.methods': 'core_enrol_get_course_enrolment_methods',
    'assign.list': 'mod_assign_get_assignments',
    'assign.status': 'mod_assign_get_submission_status',
    'assign.submissions': 'mod_assign_get_submissions',
    'assign.grades': 'mod_assign_get_grades',
    'assign.grade': 'mod_assign_save_grade mod_assign_get_submission_status mod_assign_get_assignments',
    'badge.user': 'core_badges_get_user_badges',
    'calendar.course': 'core_calendar_get_action_events_by_course',
    'calendar.events': 'core_calendar_get_calendar_events core_enrol_get_users_courses',
    'calendar.upcoming': 'core_calendar_get_action_events_by_timesort',
    'choice.list': 'mod_choice_get_choices_by_courses',
    'choice.results': 'mod_choice_get_choice_results',
    'cohort.list': 'core_cohort_get_cohorts',
    'completion.course': 'core_completion_get_course_completion_status',
    'completion.status': 'core_completion_get_activities_completion_status',
    'content.types': '',
    'database.entries': 'mod_data_get_entries',
    'feedback.analysis': 'mod_feedback_get_analysis',
    'feedback.list': 'mod_feedback_get_feedbacks_by_courses',
    'feedback.non-respondents': 'mod_feedback_get_non_respondents',
    'forum.list': 'mod_forum_get_forums_by_courses',
    'forum.discussions': 'mod_forum_get_forum_discussions',
    'forum.posts': 'mod_forum_get_forum_discussions mod_forum_get_discussion_posts',
    'forum.post': 'mod_forum_add_discussion',
    'forum.reply': 'mod_forum_add_discussion_post mod_forum_get_forum_discussions mod_forum_get_discussion_posts',
    'glossary.entries': 'mod_glossary_get_entries_by_letter',
    'grade.get': 'gradereport_user_get_grade_items',
    'grade.report': 'gradereport_user_get_grade_items',
    'grade.table': 'gradereport_user_get_grades_table',
    'grade.overview': 'gradereport_overview_get_course_grades',
    'group.list': 'core_group_get_course_groups',
    'group.groupings': 'core_group_get_course_groupings',
    'group.user-groups': 'core_group_get_course_user_groups',
    'lesson.pages': 'mod_lesson_get_pages',
    'message.list': 'core_message_get_messages',
    'message.conversations': 'core_message_get_conversations',
    'message.unread': 'core_message_get_unread_conversations_count',
    'note.course': 'core_notes_get_course_notes',
    'quiz.list': 'mod_quiz_get_quizzes_by_courses',
    'quiz.attempts': 'mod_quiz_get_user_attempts',
    'quiz.best-grade': 'mod_quiz_get_user_best_grade',
    'quiz.review': 'mod_quiz_get_attempt_review mod_quiz_get_user_attempts',
    'user.get': 'core_user_get_users_by_field core_enrol_get_enrolled_users',
    'user.list': 'core_enrol_get_enrolled_users',
    'user.profiles': 'core_user_get_course_user_profiles core_enrol_get_enrolled_users',
    'file.list': 'core_files_get_files',
    'wiki.pages': 'mod_wiki_get_subwiki_pages',
    'wiki.page': 'mod_wiki_get_subwiki_pages mod_wiki_get_page_contents',
    'workshop.grades': 'mod_workshop_get_grades_report',
    'workshop.submissions': 'mod_workshop_get_submissions',
}


def validated_functions(rows):
    """Keep only bounded function identifiers, never upstream prose."""
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('Invalid Moodle function catalogue')
    names = set()
    for row in rows:
        name = row.get('name') if isinstance(row, dict) else None
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,199}', name):
            raise ValueError('Invalid Moodle function identifier')
        names.add(name)
    return sorted(names)


def function_snapshot(record):
    names = record.get('functions')
    if not isinstance(names, list):
        return None
    try:
        return set(validated_functions([{'name': name} for name in names]))
    except ValueError:
        return None


def requirements():
    from .scoped_reads import SCOPED_READS, RESOURCE_READS
    from .document_contract import document_specs
    result = {key: set(value.split()) for key, value in FUNCTIONS.items()}
    for key in SCOPED_READS | {'forum.post', 'forum.reply', 'assign.grade'}:
        if key in result:
            result[key] |= IDENTITY
    for key in set(RESOURCE_READS) | {'assign.submissions','assign.grades','forum.posts',
            'course.module','quiz.review','file.list','wiki.page','forum.post','forum.reply','assign.grade'}:
        result[key] |= CONTENTS
    for key in {'assign.status','quiz.attempts','quiz.best-grade','quiz.review','assign.grade'}:
        result[key] |= ROSTER
    for key in document_specs():
        result[key] = IDENTITY | CONTENTS
    result['import.list'] = set()
    result['import.file'] |= {'core_files_get_files'}
    forum = IDENTITY | {'mod_forum_get_forums_by_courses','mod_forum_get_forum_discussions',
                        'mod_forum_get_discussion_posts'}
    result.update({key: forum for key in ('news','continue')})
    result.update({key: IDENTITY for key in ('evidence','runs','chart.list','chart.read',
        'analytics.result','analytics.runs','cache.show')})
    result['analytics.capabilities'] = IDENTITY | {'core_webservice_get_site_info'}
    result['chart.submissions'] = IDENTITY | {'mod_assign_get_assignments','mod_assign_get_submission_status'}
    return result


def available_recipes(names):
    from .analytics.recipes import RECIPES
    return [key for key, spec in RECIPES.items() if IDENTITY | set(spec['functions']) <= names]


def content_choices(names):
    from moodle_cli.services.content import CONTENT_FUNCTIONS
    return [kind for kind, (function, _) in CONTENT_FUNCTIONS.items()
            if IDENTITY | (CONTENTS if kind in {'page','book'} else {function}) <= names]


def sync_choices(names):
    sections = {'course': set(), 'enrolment': ROSTER,
        'forums': {'mod_forum_get_forums_by_courses','mod_forum_get_forum_discussions'},
        'assignments': {'mod_assign_get_assignments','mod_assign_get_submissions'},
        'calendar': {'core_calendar_get_action_events_by_course'}}
    return [key for key, functions in sections.items() if IDENTITY | functions <= names]


def filter_keys(keys, record):
    names = function_snapshot(record)
    if names is None:
        return set()
    required = requirements()
    result = {key for key in keys if key in required and required[key] <= names}
    recipes = available_recipes(names)
    if recipes:
        result |= set(keys) & {'analytics.run'}
    if 'activity-completion' in recipes:
        result |= set(keys) & {'analytics.start', 'analytics.continue'}
    if content_choices(names):
        result |= set(keys) & {'content.list'}
    if sync_choices(names):
        result |= set(keys) & {'sync'}
    return result


def check_parameters(key, params, record):
    names = function_snapshot(record) or set()
    if key in {'analytics.run','analytics.start'} and params['recipe'] not in available_recipes(names):
        raise PermissionError('This analytics recipe is unavailable for the validated token')
    if key == 'content.list' and params['module_type'] not in content_choices(names):
        raise PermissionError('This content type is unavailable for the validated token')
    if key == 'sync':
        sections = sync_choices(names)
        if (params.get('section') not in sections if params.get('section') else len(sections) != 5):
            raise PermissionError('Select an available --section from moodle sync --help')


def help_result(keys, record, path):
    from .contract import all_specs
    names = function_snapshot(record)
    notice = ('Command availability reflects LAMB policy and the last validated token function list. '
              'Course/resource access is checked at execution; writes still require confirmation.')
    if names is None:
        return {'commands': [], 'notice': 'Reconnect on the Moodle page to validate token capabilities. '
                'No saved function catalogue is available; this is not a course permission denial.'}
    selected = {key: spec for key, spec in all_specs().items() if key in keys}
    if path and path not in selected and not any(key.startswith(path + '.') for key in selected):
        raise PermissionError('Command or group unavailable under LAMB policy and validated token capabilities')
    if path in selected:
        spec = deepcopy(selected[path])
        # CommandSpec is frozen; its copied Click parser remains independently mutable.
        for param in spec.parser.params:
            choices = None
            if path in {'analytics.run','analytics.start'} and param.name == 'recipe':
                choices = available_recipes(names) if path == 'analytics.run' else ['activity-completion']
            elif path == 'content.list' and param.name == 'module_type':
                choices = content_choices(names)
            elif path == 'sync' and param.name == 'section':
                choices = sync_choices(names)
            if choices is not None:
                param.type = click.Choice(choices)
        return {'command': 'moodle ' + path.replace('.', ' '), 'help': spec.reference(), 'notice': notice}
    prefix = path + '.' if path else ''
    if not path:
        entries = {}
        for key, spec in sorted(selected.items()):
            group = key.split('.')[0]
            entries.setdefault(group, {'command': 'moodle ' + group,
                'help_command': 'moodle ' + group + ' --help'})
            if '.' not in key:
                entries[group]['description'] = spec.description
        return {'commands': list(entries.values()), 'notice': notice}
    return {'commands': [{'command': 'moodle ' + key.replace('.', ' '), 'description': spec.description,
                           'confirmation_required': spec.policy == 'ask'}
                          for key, spec in sorted(selected.items()) if key.startswith(prefix)], 'notice': notice}
