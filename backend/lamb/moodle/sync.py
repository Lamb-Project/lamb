"""Refresh derived course data using only the owning instructor's read client."""
from moodle_cli.services.course import CourseService
from moodle_cli.services.forum import ForumService
from moodle_cli.services.assign import AssignService
from moodle_cli.services.calendar import CalendarService
from .cache import SECTIONS, now, section_delta
from .reads import plain
from .scope import MoodleScope


def sync_course(client, cache, course_id, section=None):
    if section is not None and section not in SECTIONS:
        raise ValueError('Select a supported Moodle cache section')
    scope=MoodleScope(client,cache.source['moodle_user_id'])
    course_id=scope.require_teacher(course_id)
    started=now()
    selected=[section] if section else sorted(SECTIONS)
    data={}
    for name in selected:
        if name=='course':
            data[name]=plain(CourseService(client).get_course(course_id))
        elif name=='forums':
            service=ForumService(client)
            forums=plain(service.list_forums(course_id))
            for forum in forums:
                forum['discussions']=plain(service.get_discussions(forum['id']))
            data[name]=forums
        elif name=='assignments':
            service=AssignService(client)
            assignments=plain(service.list_assignments([course_id]))
            for assignment in assignments:
                assignment['submissions']=plain(service.get_submissions([assignment['id']]))
            data[name]=assignments
        elif name=='enrolment':
            data[name]=plain(list(scope.class_roster(course_id).values()))
        elif name=='calendar':
            data[name]=plain(CalendarService(client).get_course_events(course_id))
    # No partial cache mutation if a service above fails. The snapshot timestamp
    # is the start of observation, not a claim all remote reads were simultaneous.
    state=cache.update(course_id,data,synced_at=started)
    return {'course_id':course_id,'source':cache.source,'sections':{
        name:{'synced_at':state['sections'][name]['synced_at'],
              'delta':section_delta(name,state['sections'][name])} for name in selected}}
