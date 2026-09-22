import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from lamb.moodle.charts import submission_snapshot, ChartStore, render_svg
from lamb.moodle.contract import prepare_moodle
from lamb.moodle.forum_activity import TaskCancelled


class Client:
    readonly = True
    def __init__(self, assignments=None, summary=None):
        self.assignments = assignments or [{'id': 9, 'name': '<script>Private</script>Assignment', 'teamsubmission': 0,
            'duedate': int(time.time())+86400, 'allowsubmissionsfromdate': 0}]
        self.summary = summary or {'participantcount': 6, 'submissionssubmittedcount': 3, 'submissionsenabled': True}
        self.calls=[]
    def checkpoint(self): pass
    def call(self, function, **kwargs):
        self.calls.append((function, kwargs))
        if function == 'mod_assign_get_assignments':
            return {'courses':[{'id': 2, 'fullname':'Synthetic', 'assignments':self.assignments}]}
        return {'gradingsummary':self.summary, 'lastattempt':{'private_body':'DO_NOT_RETAIN'}}


def snapshot(client=None, **kwargs):
    with patch('lamb.moodle.charts.MoodleScope') as scope:
        scope.return_value.require_teacher.return_value=2
        return submission_snapshot(client or Client(), 7, 2, **kwargs)


def test_counts_use_moodle_eligible_participants_and_no_personal_data():
    client=Client();data=snapshot(client)
    assert data['rows'][0]['outstanding']==3
    assert data['coverage']['complete']
    assert 'DO_NOT_RETAIN' not in json.dumps(data) and '<script>' not in json.dumps(data)
    assert client.calls[-1][1]=={'assignid':9,'userid':7,'groupid':0}


@pytest.mark.parametrize('due,opens,expected', [(100,0,'deadline_passed'),(0,0,'no_deadline'),(9999999999,0,'open'),(9999999999,9999999998,'not_open')])
def test_deadline_labels_are_course_defaults(due,opens,expected):
    c=Client();c.assignments[0].update(duedate=due,allowsubmissionsfromdate=opens)
    assert snapshot(c)['rows'][0]['deadline_status']==expected


@pytest.mark.parametrize('summary', [{'participantcount':1,'submissionssubmittedcount':2,'submissionsenabled':True},
 {'participantcount':6,'submissionssubmittedcount':-1,'submissionsenabled':True},
 {'participantcount':6,'submissionssubmittedcount':0,'submissionsenabled':False},
 {'participantcount':6,'submissionssubmittedcount':True,'submissionsenabled':True}])
def test_unavailable_counts_are_not_zero(summary):
    data=snapshot(Client(summary=summary))
    assert not data['coverage']['complete']
    assert data['rows'][0]['submitted'] is None


def test_team_and_cap_are_explicit():
    c=Client();c.assignments=[dict(c.assignments[0],id=i,teamsubmission=i==0) for i in range(23)]
    data=snapshot(c)
    assert len(data['rows'])==20 and data['coverage']['omitted_by_limit']==3
    assert data['rows'][0]['submitted'] is None


def test_cancel_never_publishes_partial_success():
    c=Client();c.checkpoint=lambda: (_ for _ in ()).throw(TaskCancelled())
    with pytest.raises(TaskCancelled): snapshot(c)


def test_chart_contract_is_auto_and_strict():
    spec, params=prepare_moodle('moodle chart submissions --course 2 --tz Europe/Madrid --language es')
    assert spec.policy=='auto' and spec.key=='chart.submissions' and params['course_id']==2
    for command in ('moodle chart submissions --course 0', 'moodle chart submissions --course 2 --tz nonsense',
                    'moodle chart arbitrary --url https://example.org'):
        with pytest.raises(ValueError):prepare_moodle(command)


def runtime(tmp_path,owner=1):
    return SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=owner),
                           validate_result_binding=lambda binding,key:None)


def test_saved_chart_is_immutable_private_and_owner_bound(tmp_path):
    store=ChartStore(runtime(tmp_path));data=snapshot();id=store.save(data,{'course_id':2})
    data['rows'][0]['submitted']=999
    assert store.read(id)['rows'][0]['submitted']==3
    with pytest.raises(PermissionError): ChartStore(runtime(tmp_path,2)).read(id)
    with pytest.raises(PermissionError):store.read('../'+id)
    assert (store.root/(id+'.json')).stat().st_mode & 0o777 == 0o600
    store.runtime.validate_result_binding=lambda *_: (_ for _ in ()).throw(PermissionError())
    with pytest.raises(PermissionError):store.read(id)


def test_real_svg_render_is_bounded_no_external_resources():
    svg=render_svg(snapshot())
    assert '<svg' in svg and '<script' not in svg and 'href=' not in svg
    assert 'Submitted' in svg and 'Outstanding' in svg


def test_chart_survives_session_reload_without_full_tool_payload():
    from lamb.aac.session_guidance import browser_session
    result=browser_session({'conversation':[], 'tool_audit':[{'success':True,'artifacts':[{'type':'chart','id':'id','title':'Title'}]}]})
    assert result['charts'][0]['id']=='id' and 'tool_audit' not in result


def test_empty_course_has_complete_zero_coverage_without_invented_rows():
    client = Client()
    client.assignments = []
    data = snapshot(client)
    assert data['rows'] == []
    assert data['coverage'] == {'complete': True, 'assignments_found': 0,
                                'assignments_read': 0, 'omitted_by_limit': 0}
    assert len(client.calls) == 1


def test_all_submitted_and_no_participants_are_valid_counts():
    for n in (0, 6):
        data = snapshot(Client(summary={'participantcount': n,
            'submissionssubmittedcount': n, 'submissionsenabled': True}))
        assert data['rows'][0]['outstanding'] == 0
        assert data['coverage']['complete']


def test_structured_exclusions_and_unknown_extensions():
    client = Client()
    client.assignments[0]['teamsubmission'] = 1
    assert snapshot(client)['rows'][0]['reason_code'] == 'team'
    client.assignments[0]['teamsubmission'] = 0
    client.summary['submissionsenabled'] = False
    assert snapshot(client)['rows'][0]['reason_code'] == 'offline'
    client.summary['submissionsenabled'] = True
    client.summary['submissionssubmittedcount'] = 8
    assert snapshot(client)['rows'][0]['reason_code'] == 'counts'


def test_refresh_retains_original_snapshot_and_explicit_interpretation(tmp_path):
    from lamb.moodle.charts import chart_task
    rt = runtime(tmp_path)
    rt.result_binding = lambda: {'owner_id': 1}
    client = Client()
    with patch('lamb.moodle.charts.MoodleScope') as scope:
        scope.return_value.require_teacher.return_value = 2
        first = chart_task(rt, client, 7, {'course_id': 2})
        client.summary['submissionssubmittedcount'] = 6
        second = chart_task(rt, client, 7, {'course_id': 2})
    assert first['chart_id'] != second['chart_id']
    assert ChartStore(rt).read(first['chart_id'])['rows'][0]['submitted'] == 3
    assert ChartStore(rt).read(second['chart_id'])['rows'][0]['submitted'] == 6
    assert first['interpretation']['individual_extensions'] == 'not_checked'
    assert first['interpretation']['individual_lateness'] == 'unknown'
    assert first['interpretation']['student_identities'] == 'not_collected'


def test_changed_permission_withholds_whole_snapshot():
    client = Client()
    original = client.call
    def call(function, **kwargs):
        if function == 'mod_assign_get_submission_status':
            raise PermissionError('Course access revoked')
        return original(function, **kwargs)
    client.call = call
    with pytest.raises(PermissionError):
        snapshot(client)


def test_warning_in_summary_is_missing_not_zero():
    client = Client()
    original = client.call
    def call(function, **kwargs):
        data = original(function, **kwargs)
        if function == 'mod_assign_get_submission_status':
            data['warnings'] = [{'message': 'incomplete'}]
        return data
    client.call = call
    data = snapshot(client)
    assert data['rows'][0]['reason_code'] == 'summary'
    assert data['rows'][0]['submitted'] is None
    assert not data['coverage']['complete']
