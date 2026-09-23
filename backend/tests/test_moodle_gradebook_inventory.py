from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock,patch
import pytest
from lamb.moodle.analytics.gradebook_inventory import inventory_page

ITEM=dict(gradeitemid=3,name='Essay',itemtype='mod',itemmodule='assign',iteminstance=99,
    itemnumber=0,gradetype=1,needsupdate=0)
PAGE=dict(schema_version=1,courseid=7,groupid=0,throughid=9,next_afterid=3,has_more=True,
    items=[ITEM],collected_at=100,source='stored_grade_items',atomic_snapshot=False)

def run(page,**kwargs):
    client=SimpleNamespace(call=Mock(return_value=page))
    with patch('lamb.moodle.analytics.gradebook_inventory.MoodleScope') as scope, \
            patch('lamb.moodle.analytics.gradebook_inventory.validate_gradebook_scope') as authorize:
        value=inventory_page(client,1,7,**kwargs)
        scope.return_value.require_teacher.assert_called_once_with(7)
        return value,authorize.call_args_list

def test_valid_page_exact_item_scope_and_continuation():
    value,calls=run(deepcopy(PAGE))
    assert value['items']==[ITEM]
    assert calls[0].args[1]==dict(course_id=7,grade_item_id=3,group_id=0)
    assert value['next_command']=='moodle analytics assessments --course 7 --group 0 --after-id 3 --through-id 9 --limit 100'

def test_empty_authorized_page_still_continues():
    value,calls=run(PAGE|{'items':[]})
    assert value['next_command'] and not calls
    value,calls=run(PAGE|{'items':[],'has_more':False,'next_afterid':9})
    assert value['next_command'] is None

@pytest.mark.parametrize('change',[{'schema_version':True},{'courseid':8},{'groupid':1},
    {'throughid':2},{'next_afterid':0},{'has_more':1},{'source':'report'},
    {'atomic_snapshot':True},{'collected_at':0},{'items':{}},{'extra':'secret'}])
def test_invalid_pages_rejected(change):
    with pytest.raises(ValueError):run(PAGE|change)

@pytest.mark.parametrize('change',[{'gradeitemid':True},{'gradeitemid':4},{'name':'x'*161},
    {'itemtype':'course'},{'itemtype':[]},{'itemmodule':None},{'iteminstance':0},{'gradetype':True},
    {'needsupdate':None},{'itemnumber':-1},{'userid':1},{'itemmodule':'bad/module'}])
def test_invalid_items_rejected_before_authorization(change):
    with patch('lamb.moodle.analytics.gradebook_inventory.MoodleScope'), \
            patch('lamb.moodle.analytics.gradebook_inventory.validate_gradebook_scope') as authorize:
        with pytest.raises(ValueError):inventory_page(SimpleNamespace(call=lambda *a,**k:PAGE|{'items':[ITEM|change]}),1,7)
        authorize.assert_not_called()

def test_duplicates_and_changed_upper_rejected():
    with pytest.raises(ValueError):run(PAGE|{'items':[ITEM,ITEM]})
    with pytest.raises(ValueError):run(PAGE,through_id=10)

@pytest.mark.parametrize('kwargs',[{'limit':101},{'limit':False},{'group_id':-1},{'after_id':1}])
def test_invalid_request_never_contacts_source(kwargs):
    client=SimpleNamespace(call=Mock())
    with pytest.raises(ValueError):inventory_page(client,1,7,**kwargs)
    client.call.assert_not_called()
