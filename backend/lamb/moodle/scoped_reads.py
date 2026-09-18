"""Resolve Moodle resources through a live, verified instructor course."""
from moodle_cli.services.course import CourseService
from moodle_cli.services.forum import ForumService
from .scope import MoodleScope
from .reads import execute_read, plain

COURSE_READS=frozenset({'course.get','course.contents','calendar.course','forum.list','assign.list',
    'enrol.list-users','enrol.methods','choice.list','completion.course','completion.status',
    'content.list','feedback.list','grade.get','grade.report','grade.table','group.list',
    'group.groupings','group.user-groups','note.course','quiz.list','user.profiles'})
# Parameter, module name. IDs are activity instances, not course-module IDs.
RESOURCE_READS={
    'assign.status':('assign_id','assign'),
    'choice.results':('choice_id','choice'),
    'database.entries':('database_id','data'),
    'feedback.analysis':('feedback_id','feedback'),
    'feedback.non-respondents':('feedback_id','feedback'),
    'forum.discussions':('forum_id','forum'),
    'glossary.entries':('glossary_id','glossary'),
    'lesson.pages':('lesson_id','lesson'),
    'quiz.attempts':('quiz_id','quiz'),
    'quiz.best-grade':('quiz_id','quiz'),
    'workshop.submissions':('workshop_id','workshop'),
    'workshop.grades':('workshop_id','workshop'),
}
SCOPED_READS=COURSE_READS | set(RESOURCE_READS) | {'assign.submissions','assign.grades','forum.posts',
    'course.module','user.get','user.list','badge.user','calendar.events','quiz.review','file.list'}


def execute_scoped_read(client,key,params,*,owner_moodle_id,context):
    scope=MoodleScope(client,owner_moodle_id)
    params=dict(params)
    if key=='badge.user':
        user=params['user_id'] if params['user_id'] is not None else owner_moodle_id
        course=params['course_id']
        if user != owner_moodle_id:
            course=course or context.get('course_id')
            if not course: raise PermissionError('Select an instructor course before reading another user’s badges')
            scope.require_member(course,user)
        elif course is not None and int(course) not in scope.own_courses():
            raise PermissionError('Moodle course is outside your enrolment')
        params.update(user_id=user,course_id=course)
        return execute_read(client,key,params,owner_moodle_id=owner_moodle_id)
    if key=='calendar.events':
        requested=params['course_id']
        if requested:
            courses=[scope.require_teacher(course) for course in requested]
        else:
            courses=list(scope.own_courses())
        # An empty list must not mean all site courses to the server. The current
        # user's personal/site events are still allowed, then filtered below.
        result=execute_read(client,key,{'course_id':tuple(courses)},owner_moodle_id=owner_moodle_id)
        return [event for event in result if not event.get('courseid') or event['courseid'] in courses]
    direct=params.get('course_id') if key in COURSE_READS else None
    if isinstance(direct,(tuple,list)):
        if len(direct)>1:
            # Each course is independently checked, never a server-wide fallback.
            result=[]
            for course in direct:
                values=dict(params,course_id=(course,))
                result.extend(execute_scoped_read(client,key,values,owner_moodle_id=owner_moodle_id,context=context))
            return result
        direct=direct[0] if direct else None
    course=direct or context.get('course_id')
    if not course:
        raise PermissionError('Select an instructor course with moodle course get COURSE_ID first')
    course=scope.require_teacher(course)
    if key=='assign.list' and not params['course_id']:
        params['course_id']=(course,)
    # Store only a verified course selection. Every later command checks it again.
    context['course_id']=course
    if key=='course.get': return plain(scope.own_courses()[course])
    if params.get('user_id') is not None:
        scope.require_member(course,params['user_id'])
    for user in params.get('user_ids',()): scope.require_member(course,user)
    if key=='user.get':scope.require_member(course,params['user_id'])
    if key=='user.list':return scope.search_class(course,params['key'],params['value'])
    if key=='enrol.list-users':
        users=plain(list(scope.class_roster(course).values()))
        return [u for u in users if not params['role'] or any(r.get('shortname')==params['role'] for r in u['roles'])]
    if key in RESOURCE_READS or key in {'assign.submissions','assign.grades','forum.posts','course.module','quiz.review','file.list'}:
        contents=CourseService(client).get_contents(course)
        modules=[module for section in contents for module in section.modules]
        def owns(instance,module_type):
            return any(m.get('modname')==module_type and int(m.get('instance',0))==int(instance) for m in modules)
        if key=='quiz.review':
            proof=context.get('quiz_attempts',{}).get(str(params['attempt_id']))
            if not proof or proof['course']!=course:
                raise PermissionError('List quiz attempts for the enrolled user before reviewing this attempt')
            if not owns(proof['quiz'],'quiz'):
                raise PermissionError('Moodle quiz is outside the selected instructor course')
            scope.require_member(course,proof['user'])
            from moodle_cli.services.quiz import QuizService
            attempts=QuizService(client).get_attempts(proof['quiz'],proof['user'])
            if not any(a.id==params['attempt_id'] and a.quiz==proof['quiz'] and a.userid==proof['user'] for a in attempts):
                raise PermissionError('Moodle attempt no longer belongs to the verified quiz and user')
        elif key=='file.list':
            module=next((m for m in modules if m.get('contextid')==params['contextid']),None)
            if not module or params['component']!='mod_'+module['modname'] or params['filearea'] not in {'intro','content'}:
                raise PermissionError('File listing is limited to content or intro files in the selected course modules')
        elif key in RESOURCE_READS:
            field,kind=RESOURCE_READS[key]
            if not owns(params[field],kind):raise PermissionError('Moodle activity is outside the selected instructor course')
        elif key in {'assign.submissions','assign.grades'}:
            if not params['assignment_ids'] or not all(owns(a,'assign') for a in params['assignment_ids']):
                raise PermissionError('Moodle assignment is outside the selected instructor course')
        elif key=='course.module':
            if not any(int(m['id'])==params['cmid'] for m in modules):
                raise PermissionError('Moodle module is outside the selected instructor course')
        elif key=='forum.posts':
            forum=ForumService(client)
            found=False
            for module in modules:
                if module.get('modname')!='forum':continue
                discussions=forum.get_discussions(int(module['instance']))
                if any((d.discussion or d.id)==params['discussion_id'] for d in discussions):
                    found=True;break
            if not found:raise PermissionError('Moodle discussion is outside the selected instructor course')
    result=execute_read(client,key,params,owner_moodle_id=owner_moodle_id)
    if key=='quiz.attempts':
        user=params.get('user_id') if params.get('user_id') is not None else owner_moodle_id
        proofs=context.setdefault('quiz_attempts',{})
        for attempt in result:
            if attempt['quiz']==params['quiz_id'] and attempt['userid']==user:
                proofs[str(attempt['id'])]={'course':course,'quiz':params['quiz_id'],'user':user}
    return result
