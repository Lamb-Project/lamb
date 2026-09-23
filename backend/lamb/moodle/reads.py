"""Direct service adapters. The owning session must apply privacy scope first.

This module is intentionally not exposed to LiteShell until that gate is wired.
All requests still pass through MoodleHTTPClient's read-only allowlist.
"""
from importlib import import_module
from pydantic import BaseModel
from .contract import command_specs

# Explicit reviewed service bindings; the shell syntax comes from contract.py.
# A library upgrade adding a read command fails the coverage check until reviewed.
BINDINGS = {
    'assign.grades': ('assign','AssignService','get_grades','assignment_ids'),
    'assign.list': ('assign','AssignService','list_assignments','course_id'),
    'assign.status': ('assign','AssignService','get_submission_status','assign_id user_id'),
    'assign.submissions': ('assign','AssignService','get_submissions','assignment_ids'),
    'badge.user': ('badge','BadgeService','user_badges','user_id course_id'),
    'calendar.course': ('calendar','CalendarService','get_course_events','course_id'),
    'calendar.events': ('calendar','CalendarService','get_events','course_id'),
    'calendar.upcoming': ('calendar','CalendarService','get_upcoming','limit'),
    'choice.list': ('choice','ChoiceService','list_choices','course_id'),
    'choice.results': ('choice','ChoiceService','get_results','choice_id'),
    'cohort.list': ('cohort','CohortService','list_cohorts',''),
    'completion.course': ('completion','CompletionService','get_course_status','course_id user_id'),
    'completion.status': ('completion','CompletionService','get_status','course_id user_id'),
    'content.list': ('content','ContentService','list_activities','module_type course_id'),
    'course.categories': ('course','CourseService','get_categories',''),
    'course.contents': ('course','CourseService','get_contents','course_id'),
    'course.get': ('course','CourseService','get_course','course_id'),
    'course.list': ('course','CourseService','list_courses',''),
    'course.module': ('course','CourseService','get_module','cmid'),
    'course.search': ('course','CourseService','search_courses','query'),
    'course.timeline': ('course','CourseService','get_timeline','classification'),
    'database.entries': ('activity_content','DatabaseService','entries','database_id'),
    'enrol.list-users': ('enrol','EnrolService','list_enrolled_users','course_id'),
    'enrol.methods': ('enrol','EnrolService','get_enrolment_methods','course_id'),
    'feedback.analysis': ('feedback','FeedbackService','get_analysis','feedback_id'),
    'feedback.list': ('feedback','FeedbackService','list_feedbacks','course_id'),
    'feedback.non-respondents': ('feedback','FeedbackService','non_respondents','feedback_id'),
    'forum.discussions': ('forum','ForumService','get_discussions','forum_id'),
    'forum.list': ('forum','ForumService','list_forums','course_id'),
    'forum.posts': ('forum','ForumService','get_posts','discussion_id'),
    'glossary.entries': ('activity_content','GlossaryService','entries','glossary_id'),
    'grade.get': ('grade','GradeService','get_grades','course_id user_id'),
    'grade.overview': ('grade','GradeService','get_overview',''),
    'grade.report': ('grade','GradeService','get_report','course_id user_id'),
    'grade.table': ('grade','GradeService','get_grades_table','course_id user_id'),
    'group.groupings': ('group','GroupService','list_groupings','course_id'),
    'group.list': ('group','GroupService','list_groups','course_id'),
    'group.user-groups': ('group','GroupService','user_groups','course_id user_id'),
    'lesson.pages': ('activity_content','LessonService','pages','lesson_id'),
    'note.course': ('note','NoteService','course_notes','course_id'),
    'quiz.attempts': ('quiz','QuizService','get_attempts','quiz_id user_id'),
    'quiz.best-grade': ('quiz','QuizService','best_grade','quiz_id user_id'),
    'quiz.list': ('quiz','QuizService','list_quizzes','course_id'),
    'quiz.review': ('quiz','QuizService','attempt_review','attempt_id'),
    'site.functions': ('site','SiteService','get_functions',''),
    'site.info': ('site','SiteService','get_site_info',''),
    'user.get': ('user','UserService','get_user','user_id'),
    'user.list': ('user','UserService','list_users','key value'),
    'user.me': ('user','UserService','get_me',''),
    'user.profiles': ('user','UserService','course_profiles','course_id user_ids'),
    'wiki.page': ('activity_content','WikiService','page_contents','page_id'),
    'workshop.grades': ('activity_content','WorkshopService','grades_report','workshop_id'),
    'workshop.submissions': ('activity_content','WorkshopService','submissions','workshop_id'),
}
SPECIAL_READS = {'file.list','wiki.pages','content.types','enrol.my-courses','message.list','message.conversations','message.unread'}


def service_class(module, name):
    return getattr(import_module('moodle_cli.services.' + module), name)


def validate_bindings():
    import inspect
    reads = {k for k,spec in command_specs().items() if spec.policy == 'auto'}
    if reads != set(BINDINGS) | SPECIAL_READS:
        raise RuntimeError('Moodle service binding coverage differs from installed read map')
    for key, (module, name, method, arguments) in BINDINGS.items():
        signature = inspect.signature(getattr(service_class(module,name),method))
        signature.bind(None, *[None for _ in arguments.split()])
    return True


def plain(value):
    if isinstance(value, BaseModel): return value.model_dump(mode='json')
    if isinstance(value, (tuple,list)): return [plain(v) for v in value]
    if isinstance(value, dict): return {k:plain(v) for k,v in value.items()}
    return value


def discussion_result(item):
    """Moodle's bare id is the first post, NOT the discussion to read."""
    discussion_id, first_post_id = item.get('discussion'), item.get('id')
    if any(type(value) is not int or value <= 0 for value in (discussion_id, first_post_id)):
        raise ValueError('Moodle discussion result lacks valid discussion and first-post IDs')
    return {'discussion_id': discussion_id, 'first_post_id': first_post_id,
            **{key: value for key, value in item.items() if key not in {'id', 'discussion', 'discussion_id', 'first_post_id'}}}


def execute_read(client, key, params, *, owner_moodle_id):
    if client.readonly is not True:
        raise PermissionError('Moodle read commands require a read-only client')
    if key not in BINDINGS and key not in SPECIAL_READS:
        raise PermissionError('No reviewed Moodle read service for this command')
    params = dict(params)
    # Never let an omitted user select a server-dependent class-wide default.
    if 'user_id' in params and params['user_id'] is None:
        params['user_id'] = owner_moodle_id
    if key == 'file.list':
        from .documents import FileInventoryService
        return FileInventoryService(client).files(params)
    if key == 'wiki.pages':
        from .wiki import WikiPagesService
        return WikiPagesService(client).pages(params['wiki_id'])
    if key == 'content.types':
        from moodle_cli.services.content import CONTENT_TYPES
        return list(CONTENT_TYPES)
    if key == 'enrol.my-courses':
        return plain(service_class('enrol','EnrolService')(client).get_my_courses(userid=owner_moodle_id))
    if key.startswith('message.'):
        service = service_class('message','MessageService')(client)
        if key == 'message.list': return plain(service.get_messages(owner_moodle_id,user_id_from=params['from_user']))
        if key == 'message.conversations': return plain(service.get_conversations(owner_moodle_id))
        return {'unread_conversations':service.unread_count(owner_moodle_id)}
    module, name, method, arguments = BINDINGS[key]
    values = [list(params[arg]) if isinstance(params[arg],tuple) else params[arg] for arg in arguments.split()]
    if key in {'assign.list','calendar.events'} and not values[0]: values[0] = None
    result = plain(getattr(service_class(module,name)(client),method)(*values))
    if key == 'forum.discussions':
        result = [discussion_result(item) for item in result]
    if key == 'site.functions':
        if params['search']: result = [f for f in result if params['search'].lower() in f['name'].lower()]
        if params['component']: result = [f for f in result if f['name'].startswith(params['component'])]
    if key == 'enrol.list-users' and params['role']:
        result = [u for u in result if any(r.get('shortname') == params['role'] for r in u.get('roles',[]))]
    return result
