"""Minimal authenticated-user role evidence for course discovery, not permission grants."""
from moodle_cli.client.exceptions import MoodleAPIError, ConnectionError as MoodleConnectionError
from .scope import CourseIdentityService


def with_my_roles(client, courses, owner_id):
    result = []
    for course in courses:
        roles = None
        try:
            profile = CourseIdentityService(client).own_course_profile(course['id'], owner_id)
            raw = profile.get('roles') if isinstance(profile, dict) else None
            if isinstance(raw, list) and all(isinstance(role, dict)
                    and isinstance(role.get('shortname'), str) and role['shortname'] for role in raw):
                roles = [{key: role[key] for key in ('id', 'shortname', 'name')
                          if key in role and isinstance(role[key], (str, int))} for role in raw]
        except (PermissionError, MoodleAPIError, MoodleConnectionError):
            # A partial role lookup must not erase otherwise available courses.
            # Never forward raw Moodle error text or profile fields into AAC.
            pass
        result.append({**course, 'my_roles': roles,
                       'my_roles_status': 'available' if roles is not None else 'unavailable'})
    return result
