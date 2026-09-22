from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.events import resource_reach
from lamb.moodle.analytics.client import EVENT_FUNCTION


def event(identity, actor=1, cmid=10, name='\\mod_page\\event\\course_module_viewed'):
    return {'id':identity,'userid':actor,'cmid':cmid,'eventname':name,'timecreated':150}


def page(events, **extra):
    return {'schema_version':1,'courseid':7,'groupid':0,'since':100,'until':200,
            'source':'logstore_standard','throughid':9,'next_afterid':9,'has_more':False,
            'events':events,'omitted_inaccessible_modules':0,**extra}


class Client:
    readonly = True
    def __init__(self, pages): self.pages=iter(pages); self.calls=[]
    def checkpoint(self): pass
    def call(self, function, **params):
        self.calls.append((function,params))
        if function == EVENT_FUNCTION: return next(self.pages)
        if function == 'core_enrol_get_enrolled_users':
            return [{'id':1,'roles':[{'shortname':'student'}]},
                    {'id':2,'roles':[{'shortname':'student'}]},
                    {'id':3,'roles':[{'shortname':'editingteacher'}]}]
        if function == 'core_course_get_contents':
            return [{'modules':[{'id':10,'modname':'page','name':'Reading'},
                                {'id':11,'modname':'book','name':'Book'}]}]
        raise AssertionError(function)


def collect(client, **kwargs):
    with patch('lamb.moodle.analytics.events.MoodleScope') as scope:
        scope.return_value.require_teacher.return_value=7
        scope.return_value.own_courses.return_value={7:SimpleNamespace(fullname='Synthetic')}
        return resource_reach(client,12,7,since=100,until=200,**kwargs)


def test_unique_students_are_not_event_counts_or_teachers_and_no_ids_retained():
    result = collect(Client([page([event(1),event(2),event(3,2),event(4,3),
        event(5,1,11,'\\mod_book\\event\\chapter_viewed')])]))
    assert result['rows'][0]['unique_student_viewers'] == 2
    assert result['rows'][0]['recorded_module_views'] == 3
    assert result['rows'][1]['recorded_chapter_views'] == 1
    assert result['rows'][1]['recorded_module_views'] == 0
    assert result['coverage']['excluded_actor_events'] == 1
    assert result['coverage']['collection_complete'] and not result['coverage']['complete']
    assert result['coverage']['history_complete'] is False
    assert 'userid' not in str(result) and 'user_id' not in str(result)


def test_pagination_keeps_upper_watermark_and_empty_resources_are_observed_zero():
    client = Client([page([event(1)],has_more=True,next_afterid=1),page([event(2,2)])])
    result = collect(client)
    assert result['rows'][0]['unique_student_viewers'] == 2
    assert result['rows'][1]['unique_student_viewers'] == 0
    assert client.calls[-1][1]['afterid'] == 1 and client.calls[-1][1]['throughid'] == 9


@pytest.mark.parametrize('bad', [
    page([],courseid=8),page([],has_more=True,next_afterid=0),page([event(1),event(1)]),
    page([event(1)],next_afterid=0),page([event(1,name='arbitrary')]),
    page([event(1,cmid=0)]),page([],omitted_inaccessible_modules=-1),
    page([],schema_version=True),page([event(1,cmid=11)]),
])
def test_invalid_pages_do_not_become_zero_evidence(bad):
    with pytest.raises(ValueError): collect(Client([bad]))


def test_changed_watermark_is_rejected():
    with pytest.raises(ValueError,match='watermark'):
        collect(Client([page([event(1)],has_more=True,next_afterid=1),page([],throughid=10)]))


def test_caps_and_missing_resources_are_not_complete(monkeypatch):
    monkeypatch.setattr('lamb.moodle.analytics.events.MAX_EVENT_PAGES',1)
    result=collect(Client([page([event(1,cmid=99)],has_more=True,next_afterid=1)]))
    assert not result['coverage']['events_exhausted']
    assert not result['coverage']['collection_complete']
    assert result['coverage']['unmapped_resource_events'] == 1


def test_scope_and_cancellation_errors_are_not_swallowed():
    client=Client([])
    with patch('lamb.moodle.analytics.events.MoodleScope') as scope:
        scope.return_value.require_teacher.side_effect=PermissionError('denied')
        with pytest.raises(PermissionError):resource_reach(client,12,7,since=100,until=200)
    assert client.calls == []


def test_bad_source_scope_stops_before_population_collection():
    client=Client([page([],groupid=99)])
    with pytest.raises(ValueError): collect(client)
    assert [function for function,params in client.calls] == [EVENT_FUNCTION]


def test_revocation_mid_pagination_is_not_returned_as_partial_success():
    client=Client([page([event(1)],has_more=True,next_afterid=1)])
    original=client.call
    def revoked(function,**params):
        if function == EVENT_FUNCTION and params['afterid']:
            raise PermissionError('revoked')
        return original(function,**params)
    client.call=revoked
    with pytest.raises(PermissionError): collect(client)
