"""Verified instructor and enrolment scope, obtained with read-only services.

Never infer a role from a model statement, display name, or a stored scenario.
The proof is refreshed by creating this object for each command execution.
"""
from moodle_cli.services.base import BaseService
from moodle_cli.services.enrol import EnrolService

INSTRUCTOR_ROLES = frozenset({'editingteacher', 'teacher', 'manager'})


class CourseIdentityService(BaseService):
    def own_course_profile(self, course_id, owner_id):
        # UserService.course_profiles drops roles from its typed User model.
        # Preserve only the owning user's role evidence; never fetch a class roster
        # merely to decide whether the caller may read that roster.
        rows = self.call('core_user_get_course_user_profiles',
                         userlist=[{'userid': owner_id, 'courseid': course_id}])
        return next((row for row in rows if int(row.get('id', 0)) == owner_id), None)


class MoodleScope:
    def __init__(self, client, owner_id):
        if client.readonly is not True:
            raise PermissionError('Moodle privacy checks require a read-only client')
        self.client = client
        self.owner_id = int(owner_id)
        if self.owner_id < 1:
            raise PermissionError('Verified Moodle identity required')
        self._courses = None
        self._teacher = set()
        self._rosters = {}

    def own_courses(self):
        if self._courses is None:
            self._courses = {course.id: course for course in
                             EnrolService(self.client).get_my_courses(userid=self.owner_id)}
        return self._courses

    def require_teacher(self, course_id):
        course_id = int(course_id)
        if course_id not in self.own_courses():
            raise PermissionError('Moodle course is outside your enrolment')
        if course_id not in self._teacher:
            profile = CourseIdentityService(self.client).own_course_profile(course_id, self.owner_id)
            roles = profile.get('roles', []) if profile else []
            if not any(role.get('shortname') in INSTRUCTOR_ROLES for role in roles):
                raise PermissionError('Class-wide Moodle reads require a verified instructor role in this course')
            self._teacher.add(course_id)
        return course_id

    def class_roster(self, course_id):
        course_id = self.require_teacher(course_id)
        if course_id not in self._rosters:
            self._rosters[course_id] = {user.id: user for user in
                                       EnrolService(self.client).list_enrolled_users(course_id)}
        return self._rosters[course_id]

    def require_member(self, course_id, user_id):
        user_id = int(user_id)
        # Even one's own course-linked read must refer to an enrolled course.
        if int(course_id) not in self.own_courses():
            raise PermissionError('Moodle course is outside your enrolment')
        if user_id == self.owner_id:
            return user_id
        if user_id not in self.class_roster(course_id):
            raise PermissionError('Moodle user is outside this course enrolment')
        return user_id

    def search_class(self, course_id, key, value):
        if key not in {'id','username','email','firstname','lastname','fullname'}:
            raise ValueError('Unsupported class user search field')
        # Search the authorized roster, never the site-wide user directory.
        needle = str(value).casefold()
        return [user.model_dump(mode='json') for user in self.class_roster(course_id).values()
                if needle in str(getattr(user, key, '')).casefold()]
