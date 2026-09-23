from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock,patch
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from lamb.moodle.analytics.deadlines import deadline_calendar
from lamb.moodle.analytics.client import DEFAULT_DATES_FUNCTION

SINCE=int(datetime(2026,10,25,tzinfo=ZoneInfo('Europe/Madrid')).timestamp())
UNTIL=int(datetime(2026,10,27,tzinfo=ZoneInfo('Europe/Madrid')).timestamp())
RECORDS=[{'cmid':10+i,'instanceid':20+i,'modname':'assign','opens':0,'closes':0,'due':due}
    for i,due in enumerate([SINCE,SINCE+9000,SINCE+12600,UNTIL,0])]


def collect(records=None,**overrides):
    data={'authorized':True,'scopeonly':False,'courseid':7,'cmids':[10,11,12,13,14],
        'basis':'stored_course_defaults','relative_dates':False,'dates':deepcopy(RECORDS if records is None else records),**overrides}
    def call(fn,**params):
        if fn==DEFAULT_DATES_FUNCTION:return data
        return [{'modules':[{'id':r['cmid'],'instance':r['instanceid'],'modname':r['modname'],'name':'Fixture'} for r in RECORDS]}]
    with patch('lamb.moodle.analytics.deadlines.MoodleScope') as scope, \
         patch('lamb.moodle.analytics.deadlines.validate_date_scope') as authorize:
        scope.return_value.require_teacher.return_value=7
        scope.return_value.own_courses.return_value={7:SimpleNamespace(fullname='Course')}
        result=deadline_calendar(SimpleNamespace(call=call),3,7,since=SINCE,until=UNTIL,timezone='Europe/Madrid')
        authorize.assert_called_once()
        return result


def test_calendar_keeps_dst_fold_exclusive_end_and_unset_distinct():
    result=collect()
    assert sum(row['deadlines'] for row in result['weekly'])==3
    assert result['coverage']['unset_dates']==1 and result['coverage']['outside_window']==1
    assert result['rows'][1]['due_local']=='2026-10-25T02:30:00+02:00'
    assert result['rows'][2]['due_local']=='2026-10-25T02:30:00+01:00'
    assert result['rows'][-1]['due_local'] is None
    assert result['date_scopes']==[{'course_id':7,'module_ids':[10,11,12,13,14]}]


@pytest.mark.parametrize('overrides',[{'relative_dates':True},{'authorized':1},{'scopeonly':True},
    {'basis':'effective_dates'},{'courseid':8},{'cmids':[10]}])
def test_unverified_scope_or_relative_calendar_fails(overrides):
    with pytest.raises(ValueError):collect(**overrides)


@pytest.mark.parametrize('mutation',['duplicate','missing','foreign','invalid_date','wrong_instance'])
def test_inventory_and_date_validation(mutation):
    rows=deepcopy(RECORDS)
    if mutation=='duplicate':rows.append(rows[0])
    if mutation=='missing':rows.pop()
    if mutation=='foreign':rows[0]['cmid']=99
    if mutation=='invalid_date':rows[0]['due']=True
    if mutation=='wrong_instance':rows[0]['instanceid']=99
    with pytest.raises(ValueError):collect(rows)


def test_timeline_preserves_open_due_cutoff_but_deduplicates_coincident_close():
    records=deepcopy(RECORDS)
    records[0].update(opens=SINCE+60,closes=SINCE+120)
    records[1]['closes']=records[1]['due']
    result=collect(records)
    assert [(e['cmid'],e['kind']) for e in result['events']]==[
        (10,'due'),(10,'opens'),(10,'closes'),(11,'due'),(12,'due')]
    assert result['events'][3]['also_closes'] is True
    assert all(SINCE<=e['timestamp']<UNTIL for e in result['events'])
    assert sum(w['deadlines'] for w in result['weekly'])==3


def test_week_intervals_clip_to_requested_range_across_dst():
    weeks=collect()['weekly']
    assert len(weeks)==2
    assert weeks[0]['since']==SINCE and weeks[-1]['until']==UNTIL
    assert weeks[0]['until']==weeks[1]['since']
    assert weeks[0]['until']-weeks[0]['since']==25*3600
    assert all(w['partial_week'] for w in weeks)
    assert [w['deadlines'] for w in weeks]==[3,0]


@pytest.mark.parametrize('cmids',[[10.0,11,12,13,14],None,'10,11,12,13,14'])
def test_source_module_ids_are_strict_integers(cmids):
    with pytest.raises(ValueError):collect(cmids=cmids)


@pytest.mark.parametrize('since,until',[(True,UNTIL),(SINCE,False),(0,UNTIL),
    (SINCE,SINCE),(UNTIL,SINCE),(SINCE,SINCE+371*86400)])
def test_invalid_window_fails_before_source_access(since,until):
    client=SimpleNamespace(call=Mock())
    with patch('lamb.moodle.analytics.deadlines.MoodleScope') as scope, pytest.raises(ValueError):
        deadline_calendar(client,3,7,since=since,until=until,timezone='Europe/Madrid')
    scope.assert_not_called()
    client.call.assert_not_called()


@pytest.mark.parametrize('modules,expected',[
    ([],{'complete':True,'unsupported_activity_types':[],'inaccessible_activities':0}),
    ([{'id':1,'modname':'forum'}],
     {'complete':False,'unsupported_activity_types':['forum'],'inaccessible_activities':0}),
    ([{'id':1,'uservisible':False}],
     {'complete':False,'unsupported_activity_types':[],'inaccessible_activities':1}),
])
def test_empty_supported_inventory_is_not_fabricated_as_complete(modules,expected):
    client=SimpleNamespace(call=Mock(return_value=[{'modules':modules}]))
    with patch('lamb.moodle.analytics.deadlines.MoodleScope') as scope:
        scope.return_value.require_teacher.return_value=7
        scope.return_value.own_courses.return_value={7:SimpleNamespace(fullname='Course')}
        result=deadline_calendar(client,3,7,since=SINCE,until=UNTIL,timezone='Europe/Madrid')
    assert result['rows']==result['events']==result['date_scopes']==[]
    assert all(result['coverage'][key]==value for key,value in expected.items())
    assert sum(week['deadlines'] for week in result['weekly'])==0
    client.call.assert_called_once_with('core_course_get_contents',courseid=7,
        options=[{'name':'excludecontents','value':1}])


def test_permissions_revoked_during_collection_prevent_returning_evidence():
    data={'authorized':True,'scopeonly':False,'courseid':7,'cmids':[10],
        'basis':'stored_course_defaults','relative_dates':False,'dates':[deepcopy(RECORDS[0])]}
    client=SimpleNamespace(call=Mock(side_effect=[
        [{'modules':[{'id':10,'instance':20,'modname':'assign','name':'Fixture'}]}],data]))
    with patch('lamb.moodle.analytics.deadlines.MoodleScope') as scope, \
         patch('lamb.moodle.analytics.deadlines.validate_date_scope',side_effect=PermissionError('revoked')):
        scope.return_value.require_teacher.return_value=7
        scope.return_value.own_courses.return_value={7:SimpleNamespace(fullname='Course')}
        with pytest.raises(PermissionError,match='revoked'):
            deadline_calendar(client,3,7,since=SINCE,until=UNTIL,timezone='Europe/Madrid')
