"""Bounded resource reach from recorded views, never inferred reading activity."""
from datetime import datetime, timezone
import time

from .client import EVENT_FUNCTION
from ..scope import MoodleScope
from ..forum_activity import preview

RESOURCE_TYPES = frozenset({'resource', 'page', 'url', 'folder', 'book'})
VIEW_EVENTS = {f'\\mod_{kind}\\event\\course_module_viewed' for kind in RESOURCE_TYPES}
CHAPTER_EVENT = '\\mod_book\\event\\chapter_viewed'
COURSE_EVENT = '\\core\\event\\course_viewed'
MAX_EVENT_PAGES = 20
MAX_RESOURCES = 100
PAGE_SIZE = 200
MAX_USERS = 1000


def _check_scope(page, request):
    expected = {'schema_version':1,'courseid':request['courseid'],'groupid':request['groupid'],
                'since':request['since'],'until':request['until'],'source':'logstore_standard'}
    if not isinstance(page,dict) or any(type(page.get(k)) is not type(v) or page.get(k) != v for k,v in expected.items()):
        raise ValueError('Event source scope mismatch')


def _students(client, course, group):
    students, seen, unknown, exhausted = set(), set(), 0, False
    for offset in range(0, MAX_USERS, PAGE_SIZE):
        users = client.call('core_enrol_get_enrolled_users', courseid=course, options=[
            {'name':'onlyactive','value':1}, {'name':'groupid','value':group},
            {'name':'limitfrom','value':offset}, {'name':'limitnumber','value':PAGE_SIZE},
            {'name':'sortby','value':'id'}, {'name':'sortdirection','value':'ASC'},
            {'name':'userfields','value':'id,roles'}])
        if not isinstance(users, list) or len(users) > PAGE_SIZE:
            raise ValueError('Invalid event population page')
        for user in users:
            identity, roles = user.get('id'), user.get('roles')
            if type(identity) is not int or identity < 1 or identity in seen:
                raise ValueError('Unstable event population')
            seen.add(identity)
            if not isinstance(roles, list) or any(not isinstance(role, dict) for role in roles):
                unknown += 1
            elif any(role.get('shortname') == 'student' for role in roles):
                students.add(identity)
        if len(users) < PAGE_SIZE:
            exhausted = True
            break
    return students, {'student_rows':len(students), 'users_scanned':len(seen),
                      'role_unknown':unknown, 'population_exhausted':exhausted}


def resource_reach(client, owner_id, course_id, *, since, until, group_id=0, view_timezone=None, window_timezone='UTC'):
    now = int(time.time())
    if any(type(v) is not int for v in (since, until, group_id)) or not 0 <= since < until <= now or group_id < 0:
        raise ValueError('Use a past event window and a nonnegative group ID')
    from .window import require_event_timestamps
    require_event_timestamps(since,until,window_timezone)
    scope = MoodleScope(client, owner_id)
    course = scope.require_teacher(course_id)
    request = {'courseid':course,'since':since,'until':until,'groupid':group_id,'limit':PAGE_SIZE}
    # Check event/log/group permission before requesting the analytical population.
    page = client.call(EVENT_FUNCTION, **request, afterid=0, throughid=0)
    _check_scope(page, request)
    students, population = _students(client, course, group_id)
    time_buckets = None
    if view_timezone is not None:
        from .view_time import ViewTimeBuckets
        time_buckets = ViewTimeBuckets(students,since=since,until=until,timezone=view_timezone)
    sections = client.call('core_course_get_contents', courseid=course,
                           options=[{'name':'excludecontents','value':1}])
    if not isinstance(sections, list):
        raise ValueError('Resource inventory unavailable')
    inventory = {}
    for section in sections:
        for module in section.get('modules', []):
            if module.get('modname') not in RESOURCE_TYPES or module.get('uservisible') is False:
                continue
            identity = module.get('id')
            if type(identity) is not int or identity < 1 or identity in inventory:
                raise ValueError('Invalid resource inventory')
            inventory[identity] = {'cmid':identity, 'name':preview(module['name'],160)[0],
                                   'module_type':module['modname']}
    selected = dict(sorted(inventory.items())[:MAX_RESOURCES])
    viewers = {key:set() for key in selected}
    counts = {key:0 for key in selected}
    chapters = {key:0 for key in selected}
    cursor, watermark, scanned, excluded, unmapped, omitted, exhausted = 0, None, 0, 0, 0, 0, False
    for index in range(MAX_EVENT_PAGES):
        if index:
            page = client.call(EVENT_FUNCTION, **request, afterid=cursor, throughid=watermark)
        _check_scope(page, request)
        upper, next_id, more = page.get('throughid'), page.get('next_afterid'), page.get('has_more')
        if type(upper) is not int or type(next_id) is not int or type(more) is not bool or not 0 <= cursor <= next_id <= upper:
            raise ValueError('Invalid event cursor')
        if watermark is not None and upper != watermark:
            raise ValueError('Event watermark changed')
        watermark = upper
        events = page.get('events')
        if not isinstance(events,list) or len(events) > PAGE_SIZE or (more and next_id == cursor):
            raise ValueError('Invalid event page')
        last = cursor
        for event in events:
            identity, actor, cmid, stamp = (event.get(k) for k in ('id','userid','cmid','timecreated'))
            name = event.get('eventname')
            if any(type(v) is not int for v in (identity, actor, cmid, stamp)) or not last < identity <= next_id or actor < 1 or cmid < 0 or not since <= stamp < until:
                raise ValueError('Invalid event evidence')
            if name not in VIEW_EVENTS | {CHAPTER_EVENT, COURSE_EVENT} or (name == COURSE_EVENT) != (cmid == 0):
                raise ValueError('Unexpected event type')
            last = identity
            scanned += 1
            if actor not in students:
                excluded += 1
            elif cmid:
                if cmid not in selected:
                    unmapped += 1
                else:
                    expected_event = f"\\mod_{selected[cmid]['module_type']}\\event\\course_module_viewed"
                    if name != expected_event and not (name == CHAPTER_EVENT and selected[cmid]['module_type'] == 'book'):
                        raise ValueError('Resource type does not match the event')
                    viewers[cmid].add(actor)
                    if name == CHAPTER_EVENT:
                        chapters[cmid] += 1
                    else:
                        counts[cmid] += 1
            if time_buckets is not None and (cmid == 0 or cmid in selected):
                time_buckets.add(event_id=identity,student_id=actor,timestamp=stamp,
                    kind='course_view' if name==COURSE_EVENT else 'chapter_view' if name==CHAPTER_EVENT else 'resource_view')
        inaccessible = page.get('omitted_inaccessible_modules')
        if type(inaccessible) is not int or inaccessible < 0:
            raise ValueError('Invalid event coverage')
        omitted += inaccessible
        cursor = next_id
        if not more:
            exhausted = True
            break
    client.checkpoint()
    rows = [{**item,'unique_student_viewers':len(viewers[key]),'recorded_module_views':counts[key],
             'recorded_chapter_views':chapters[key], 'population_students':len(students)} for key,item in selected.items()]
    complete = exhausted and population['population_exhausted'] and not population['role_unknown'] and len(inventory) <= MAX_RESOURCES and not omitted and not unmapped
    result = {'schema_version':1,'recipe':{'id':'resource-reach','version':1},'course_id':course,
            'course_name':preview(scope.own_courses()[course].fullname,160)[0],
            'group_id':group_id,'as_of':datetime.now(timezone.utc).isoformat(),'timezone':'UTC',
            'window':{'since':since,'until':until},'rows':rows,
            'coverage':{**population,'complete':False,'collection_complete':complete,'history_complete':False,
                        'events_exhausted':exhausted,'events_scanned':scanned,'excluded_actor_events':excluded,
                        'unmapped_resource_events':unmapped,'omitted_inaccessible_module_events':omitted,
                        'resources_found':len(inventory),'resources_omitted_by_limit':max(0,len(inventory)-MAX_RESOURCES)},
            'source':EVENT_FUNCTION,'watermark':watermark,
            'metrics':{'recorded_module_views':sum(counts.values()),'recorded_chapter_views':sum(chapters.values())},
            'limitations':['Recorded views are not proof of reading, comprehension or study time.',
                           'Population uses current active enrolments with role shortname student, not historical enrolments.',
                           'Group membership and module visibility are current, not historical.',
                           'Log retention and availability do not establish a complete history; zero means no matching recorded event in the retrieved evidence.',
                           'Unique viewers include chapter views; module and chapter event counts are reported separately.',
                           'Collection is bounded; capped or omitted evidence does not support course-wide conclusions.']}
    if time_buckets is not None:
        result['view_time'] = time_buckets.snapshot(collection_complete=complete)
    return result


def view_activity(client, owner_id, course_id, *, since, until, timezone, group_id=0):
    """Private source collector for view trends/heatmaps, not all activity.

    Shares resource inventory, permissions, source validation and coverage.
    No public recipe is registered until presentation and AAC acceptance exist.
    """
    evidence=resource_reach(client,owner_id,course_id,since=since,until=until,window_timezone=timezone,
        group_id=group_id,view_timezone=timezone)
    return {key:evidence[key] for key in ('course_id','course_name','group_id','as_of','source','watermark','coverage')} | {
        'module_ids':[row['cmid'] for row in evidence['rows']],
        'view_time':evidence['view_time']}
