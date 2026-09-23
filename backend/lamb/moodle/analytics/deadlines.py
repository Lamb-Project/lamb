"""Observed stored assignment/quiz schedules, not effective learner deadlines."""
from datetime import datetime,timedelta,timezone as utc_timezone
from zoneinfo import ZoneInfo
from .client import DEFAULT_DATES_FUNCTION
from .authorization import validate_date_scope
from ..scope import MoodleScope
from ..forum_activity import preview


def deadline_calendar(client,owner_id,course_id,*,since,until,timezone):
    if (type(since) is not int or type(until) is not int or not 0<since<until
            or until-since>=371*86400):
        raise ValueError('Use a positive deadline window of at most 370 days')
    zone=ZoneInfo(timezone)
    if (datetime.fromtimestamp(until,zone).replace(tzinfo=None)
            -datetime.fromtimestamp(since,zone).replace(tzinfo=None))>timedelta(days=370):
        raise ValueError('Use a deadline window of at most 370 local days')
    scope=MoodleScope(client,owner_id)
    course=scope.require_teacher(course_id)
    name=preview(scope.own_courses()[course].fullname,160)[0]
    sections=client.call('core_course_get_contents',courseid=course,options=[{'name':'excludecontents','value':1}])
    if not isinstance(sections,list):raise ValueError('Deadline inventory unavailable')
    inventory={};seen=set();unsupported=set();inaccessible=0
    for section in sections:
        if not isinstance(section,dict) or not isinstance(section.get('modules'),list):
            raise ValueError('Invalid deadline section')
        for module in section['modules']:
            if not isinstance(module,dict):raise ValueError('Invalid deadline activity')
            cmid=module.get('id')
            if type(cmid) is not int or cmid<1 or cmid in seen:raise ValueError('Invalid deadline module ID')
            seen.add(cmid)
            if len(seen)>1000:raise ValueError('Deadline inventory exceeds scan limit')
            if module.get('uservisible') is False:
                inaccessible+=1;continue
            kind=module.get('modname')
            if not isinstance(kind,str):raise ValueError('Unknown activity type')
            if kind not in {'assign','quiz'}:
                unsupported.add(kind);continue
            instance=module.get('instance')
            if type(instance) is not int or instance<1:raise ValueError('Invalid deadline activity instance')
            inventory[cmid]={'cmid':cmid,'instanceid':instance,'modname':kind,'name':preview(module['name'],160)[0]}
    if len(inventory)>100:raise ValueError('Deadline collection exceeds activity limit')
    rows=[]
    date_scope={'course_id':course,'module_ids':sorted(inventory)}
    if inventory:
        data=client.call(DEFAULT_DATES_FUNCTION,courseid=course,cmids=date_scope['module_ids'])
        if (not isinstance(data,dict) or data.get('authorized') is not True or data.get('scopeonly') is not False
                or type(data.get('courseid')) is not int or data['courseid']!=course
                or not isinstance(data.get('cmids'),list)
                or any(type(value) is not int for value in data['cmids'])
                or data['cmids']!=date_scope['module_ids'] or data.get('basis')!='stored_course_defaults'
                or type(data.get('relative_dates')) is not bool or not isinstance(data.get('dates'),list)):
            raise ValueError('Default-date source scope mismatch')
        if data['relative_dates']:
            raise ValueError('Relative-date course requires learner-specific scheduling; no absolute calendar produced')
        returned=set()
        for record in data['dates']:
            if not isinstance(record,dict):raise ValueError('Invalid default-date record')
            cmid=record.get('cmid')
            if type(cmid) is not int or cmid not in inventory or cmid in returned:raise ValueError('Default-date inventory mismatch')
            returned.add(cmid);item=inventory[cmid]
            if record.get('modname')!=item['modname'] or type(record.get('instanceid')) is not int or record['instanceid']!=item['instanceid']:
                raise ValueError('Default-date activity mismatch')
            dates={key:record.get(key) for key in ('opens','due','closes')}
            if any(type(value) is not int or value<0 or value>253402214400 for value in dates.values()):
                raise ValueError('Invalid default-date timestamp')
            due=dates['due']
            rows.append({**item,**dates,'in_window':bool(due and since<=due<until),
                'date_status':'scheduled' if due else 'unset',
                'due_local':datetime.fromtimestamp(due,zone).isoformat() if due else None})
        if returned!=set(inventory):raise ValueError('Default-date source omitted activities')
        validate_date_scope(client,date_scope)
    rows.sort(key=lambda row:(row['due'] or 253402214401,row['cmid']))
    start=datetime.fromtimestamp(since,zone).date()
    end=datetime.fromtimestamp(until-1,zone).date()
    monday=start-timedelta(days=start.weekday());weeks={}
    while monday<=end:
        next_monday=monday+timedelta(days=7)
        week_since=int(datetime.combine(monday,datetime.min.time(),zone).timestamp())
        week_until=int(datetime.combine(next_monday,datetime.min.time(),zone).timestamp())
        weeks[monday.isoformat()]={'week_start':monday.isoformat(),'deadlines':0,
            'since':max(since,week_since),'until':min(until,week_until),
            'partial_week':since>week_since or until<week_until}
        monday=next_monday
    events=[]
    for row in rows:
        if row['in_window']:
            day=datetime.fromtimestamp(row['due'],zone).date()
            weeks[(day-timedelta(days=day.weekday())).isoformat()]['deadlines']+=1
        for kind in ('opens','due','closes'):
            timestamp=row[kind]
            if timestamp and since<=timestamp<until:
                # A quiz's closing time is its due time: retain one event, with
                # both meanings, rather than implying two separate deadlines.
                if kind=='closes' and timestamp==row['due']:
                    continue
                events.append({'cmid':row['cmid'],'name':row['name'],'modname':row['modname'],
                    'kind':kind,'also_closes':kind=='due' and timestamp==row['closes'],
                    'timestamp':timestamp,'local':datetime.fromtimestamp(timestamp,zone).isoformat()})
    events.sort(key=lambda event:(event['timestamp'],event['cmid'],event['kind']))
    return {'course_id':course,'course_name':name,'as_of':datetime.now(utc_timezone.utc).isoformat(),
        'schema_version':1,'recipe':{'id':'deadlines','version':1},'source':DEFAULT_DATES_FUNCTION,
        'basis':'stored_course_defaults','window':{'since':since,'until':until,'timezone':timezone},
        'rows':rows,'events':events,'weekly':list(weeks.values()),
        'date_scopes':[date_scope] if inventory else [],
        'coverage':{'complete':not inaccessible and not unsupported,'supported_activities':len(rows),
            'unsupported_activity_types':sorted(unsupported),'inaccessible_activities':inaccessible,
            'unset_dates':sum(row['date_status']=='unset' for row in rows),
            'outside_window':sum(bool(row['due']) and not row['in_window'] for row in rows)},
        'limitations':['Only stored assignment due dates and quiz closing dates are counted.',
            'Individual/group overrides and learner eligibility were not collected.',
            'Deadline counts are a workload proxy, not study hours or individual lateness.']}
