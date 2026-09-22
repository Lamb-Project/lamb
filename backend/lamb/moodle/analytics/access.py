"""Course-access recency, explicitly distinct from site access or event history."""
from datetime import datetime, timezone
import time

from ..scope import MoodleScope

PAGE_SIZE = 200
MAX_USERS = 1000


def course_access(client, owner_id, course_id, *, since, until=None):
    """Return minimized student records and honest missing-field coverage.

    Last-access is a current scalar. It cannot reconstruct access in a past
    window if a later access has overwritten the value, so historical end times
    are rejected. Zero means no course access recorded, not proven non-use.
    """
    now = int(time.time())
    if type(since) is not int or not 0 <= since < now:
        raise ValueError('Use a positive past Unix timestamp for since')
    if until is not None:
        raise ValueError('Last course access cannot reconstruct historical windows')
    course_id = MoodleScope(client, owner_id).require_teacher(course_id)
    rows, seen, offset, exhausted, role_unknown = [], set(), 0, False, 0
    while offset < MAX_USERS:
        client.checkpoint()
        users = client.call('core_enrol_get_enrolled_users', courseid=course_id, options=[
            {'name':'onlyactive','value':1}, {'name':'limitfrom','value':offset},
            {'name':'limitnumber','value':PAGE_SIZE}, {'name':'sortby','value':'id'},
            {'name':'sortdirection','value':'ASC'},
            {'name':'userfields','value':'id,roles,lastcourseaccess'}])
        if not isinstance(users, list) or len(users) > PAGE_SIZE:
            raise ValueError('Invalid enrolled-user page')
        for user in users:
            identity = user.get('id')
            if type(identity) is not int or identity <= 0 or identity in seen:
                raise ValueError('Unstable or invalid course population; retry collection')
            seen.add(identity)
            if 'roles' not in user:
                role_unknown += 1
                continue
            if not any(role.get('shortname') == 'student' for role in user['roles']):
                continue
            value = user.get('lastcourseaccess')
            if type(value) is not int or not 0 <= value <= now:
                value, status = None, 'unknown'
            elif value == 0:
                status = 'no_course_access_recorded'
            elif value >= since:
                status = 'recent'
            else:
                status = 'older'
            rows.append({'user_id':identity, 'last_course_access':value, 'status':status})
        offset += len(users)
        if len(users) < PAGE_SIZE:
            exhausted = True
            break
    client.checkpoint()
    return {'schema_version':1, 'recipe':{'id':'course-access','version':1},
            'course_id':course_id, 'as_of':datetime.fromtimestamp(now, timezone.utc).isoformat(),
            'timezone':'UTC', 'window':{'since':since, 'until':now},
            'population':'Visible active enrolled users with role shortname student',
            'rows':rows, 'metrics':{status:sum(row['status'] == status for row in rows)
                for status in ('recent','older','no_course_access_recorded','unknown')},
            'coverage':{'population_exhausted':exhausted,'users_scanned':len(seen),
                        'student_rows':len(rows),'role_unknown':role_unknown,
                        'complete':exhausted and role_unknown == 0 and all(row['status'] != 'unknown' for row in rows)},
            'source':'core_enrol_get_enrolled_users.lastcourseaccess',
            'limitations':['Last course access is not last site access or a resource-opening history.',
                           'No recorded access does not prove that a learner never accessed course content.',
                           'Custom student roles require an explicit population mapping.',
                           'Recency is observed access, not engagement, reading, comprehension or study time.']}
