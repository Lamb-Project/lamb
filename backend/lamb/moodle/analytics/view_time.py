"""Private aggregation of authorized recorded views, not general engagement.

Callers must establish source permission, population and event coverage first.
Learner IDs are used only for distinct counts and never projected. This module
does not authorize reads, fetch events, persist cursors or infer learning.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KINDS = ('course_view', 'resource_view', 'chapter_view')
MAX_WINDOW_SECONDS = 90 * 86400
MAX_STUDENTS = 1000
MAX_EVENTS = 20000


def _bucket():
    return {'viewers':set(), 'counts':dict.fromkeys(KINDS, 0)}


def _public(bucket):
    return {'unique_student_viewers':len(bucket['viewers']),
            'recorded_views':sum(bucket['counts'].values()), **bucket['counts']}


class ViewTimeBuckets:
    def __init__(self, students, *, since, until, timezone):
        if any(type(value) is not int for value in (since, until)) or not 0 <= since < until or until-since > MAX_WINDOW_SECONDS:
            raise ValueError('Invalid bounded view window')
        self.zone = ZoneInfo(timezone)
        identities = list(students)
        if len(identities)>MAX_STUDENTS or any(type(value) is not int or value<1 for value in identities) or len(set(identities))!=len(identities):
            raise ValueError('Invalid view population')
        self.students = set(identities)
        self.since, self.until = since, until
        self.last_id = self.scanned = self.excluded = 0
        first = datetime.fromtimestamp(since, self.zone).date()
        last = datetime.fromtimestamp(until-1, self.zone).date()
        self.days = {}
        self.weeks = {}
        current = first
        while current <= last:
            self.days[current.isoformat()] = _bucket()
            monday=(current-timedelta(days=current.weekday())).isoformat()
            self.weeks.setdefault(monday,_bucket())
            current += timedelta(days=1)
        self.hours = {(day,hour):_bucket() for day in range(7) for hour in range(24)}
        self.total = _bucket()

    def add(self, *, event_id, student_id, timestamp, kind):
        if any(type(value) is not int for value in (event_id, student_id, timestamp)) or event_id <= self.last_id or student_id < 1:
            raise ValueError('Invalid or replayed view event')
        if not self.since <= timestamp < self.until or kind not in KINDS:
            raise ValueError('View event outside the declared scope')
        if self.scanned >= MAX_EVENTS:
            raise ValueError('View event budget exceeded')
        local = datetime.fromtimestamp(timestamp, self.zone)
        self.last_id = event_id
        self.scanned += 1
        if student_id not in self.students:
            self.excluded += 1
            return
        monday=(local.date()-timedelta(days=local.weekday())).isoformat()
        for bucket in (self.total, self.days[local.date().isoformat()], self.weeks[monday], self.hours[(local.weekday(),local.hour)]):
            bucket['viewers'].add(student_id)
            bucket['counts'][kind] += 1

    def snapshot(self, *, collection_complete):
        if type(collection_complete) is not bool:
            raise ValueError('Explicit collection coverage is required')
        return {'timezone':self.zone.key,'window':{'since':self.since,'until':self.until},
            'population_students':len(self.students),'event_kinds':list(KINDS),
            'totals':_public(self.total),
            'daily':[{'date':day,**_public(bucket)} for day,bucket in self.days.items()],
            'weekly':[{'week_start':day,**_public(bucket)} for day,bucket in self.weeks.items()],
            'weekday_hour':[{'weekday':day,'hour':hour,**_public(bucket)} for (day,hour),bucket in self.hours.items()],
            'coverage':{'collection_complete':collection_complete,'history_complete':False,
                'events_scanned':self.scanned,'excluded_actor_events':self.excluded},
            'limitations':[
                'Only the declared recorded view types are counted, not all course activity.',
                'Views do not establish reading, study time, engagement or learning.',
                'Distinct viewers across buckets overlap; never sum them to obtain distinct course viewers.',
                'Weekday numbering is Monday=0. Repeated local hours during clock changes share a cell.',
                'Heatmap cells are raw counts, not rates; exposure periods and clock changes can differ.',
                'Zero means no matching event in collected evidence, not proven non-use. Partial boundary days remain partial.',
                'Current active enrolment membership is not historical membership; retained logs may be incomplete.']}
