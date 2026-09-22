from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.moodle.analytics.completion import activity_completion


class Client:
    def __init__(self):
        self.modules=[{'id':10,'name':'Task','completion':2,'uservisible':True},
                      {'id':11,'name':'No tracking','completion':0}]
        self.records=[{'cmid':10,'tracking':2,'state':state,'istrackeduser':True,'isoverallcomplete':state in (1,2),'overrideby':99 if state==3 else None}
                      for state in range(4)]
        self.calls=[]
    def checkpoint(self): pass
    def call(self,name,**params):
        self.calls.append((name,params))
        if name=='core_course_get_contents':return [{'modules':self.modules}]
        record=self.records[params['userid']-1]
        return {'statuses':[] if record is None else [record],'warnings':[]}


def collect(client,students=None):
    with patch('lamb.moodle.analytics.completion.MoodleScope') as scope, \
         patch('lamb.moodle.analytics.completion._students',return_value=(set(range(1,5)) if students is None else students,
             {'population_exhausted':True,'role_unknown':0,'student_rows':4})):
        scope.return_value.require_teacher.return_value=7
        scope.return_value.own_courses.return_value={7:SimpleNamespace(fullname='Course')}
        return activity_completion(client,12,7)


def test_four_states_and_overrides_are_distinct_without_retained_identities():
    c=Client(); result=collect(c); row=result['rows'][0]
    assert [row[s] for s in ('incomplete','complete','complete_pass','complete_fail')]==[1,1,1,1]
    assert row['overridden']==1 and row['unknown']==row['untracked']==0
    assert row['overall_complete']==2
    assert result['coverage']['tracking_disabled_modules']==1 and result['coverage']['complete']
    assert 'userid' not in str(result) and '99' not in str(result)
    assert len(c.calls)==5


def test_absent_untracked_and_invalid_states_are_not_incomplete():
    c=Client(); c.records[0]=None; c.records[1]['istrackeduser']=False
    c.records[2]['state']=True; c.records[3].pop('overrideby')
    result=collect(c); row=result['rows'][0]
    assert row['unknown']==2 and row['untracked']==1 and row['incomplete']==0
    assert row['complete_fail']==1 and row['override_unknown']==1
    assert not result['coverage']['complete']


def test_changed_tracking_and_population_limit_fail_without_partial_result():
    c=Client(); c.records[1]['tracking']=1
    with pytest.raises(ValueError,match='changed'):collect(c)
    c=Client()
    with pytest.raises(ValueError,match='student limit'):collect(c,set(range(1,102)))
    assert not c.calls


def test_source_permission_denial_propagates():
    c=Client(); original=c.call
    def call(name,**params):
        if name.startswith('core_completion'):raise PermissionError('Group denied')
        return original(name,**params)
    c.call=call
    with pytest.raises(PermissionError):collect(c)


def test_empty_population_has_zero_observations_not_unknown_students():
    result=collect(Client(),set())
    assert result['rows'][0]['population_students']==0
    assert result['rows'][0]['incomplete']==0


def test_overall_completion_is_not_inferred_from_state():
    c=Client(); c.records[3]['isoverallcomplete']=True
    row=collect(c)['rows'][0]
    assert row['complete_fail']==1 and row['overall_complete']==3
    c.records[3].pop('isoverallcomplete')
    row=collect(c)['rows'][0]
    assert row['complete_fail']==1 and row['overall_unknown']==1


def test_inventory_drift_and_duplicate_disabled_ids_fail():
    c=Client(); c.records[2]['cmid']=999
    with pytest.raises(ValueError,match='out-of-scope'):collect(c)
    c=Client(); c.modules.append(dict(c.modules[1]))
    with pytest.raises(ValueError,match='module ID'):collect(c)
