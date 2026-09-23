from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from lamb.moodle.analytics.forum_context import discussion_inventory, forum_context


def row(identity, **changes):
    return dict({'discussion':identity,'id':identity+10000,'groupid':-1,
                 'timestart':0,'timeend':0,'message':'PRIVATE BODY'},**changes)


def client(pages):
    return SimpleNamespace(call=Mock(side_effect=[{'warnings':[],'discussions':p} for p in pages]))


def test_paged_inventory_uses_discussion_not_root_id_and_discards_text():
    c=client([[row(i) for i in range(1,51)],[row(51)]])
    inventory=discussion_inventory(c,8,0)
    assert len(inventory)==51 and inventory[0]['discussion_id']==1
    assert inventory[0]['root_post_id']==10001 and 'PRIVATE' not in repr(inventory)
    assert [call.kwargs['page'] for call in c.call.call_args_list]==[0,1]
    assert all(call.kwargs['sortorder']==4 and call.kwargs['groupid']==0 for call in c.call.call_args_list)


@pytest.mark.parametrize('bad', [row(1,discussion=True),row(1,id=0),row(1,groupid=2),
    row(1,timestart=True),row(1,forum=9),row(1,timeend=-1)])
def test_malformed_or_foreign_inventory_rejected(bad):
    with pytest.raises(ValueError):discussion_inventory(client([[bad]]),8,1)


def test_duplicates_warnings_and_exhaustion_bounds():
    with pytest.raises(ValueError):discussion_inventory(client([[row(1),row(1)]]),8,0)
    with pytest.raises(ValueError):discussion_inventory(SimpleNamespace(call=lambda *a,**k:
        {'warnings':[{'warningcode':'denied'}],'discussions':[]}),8,0)
    with pytest.raises(ValueError):discussion_inventory(client([[row(i) for i in range(1,52)]]),8,0)
    pages=[[row(i) for i in range(start,start+50)] for start in range(1,1001,50)]
    assert len(discussion_inventory(client(pages+[[]]),8,0))==1000
    with pytest.raises(ValueError):discussion_inventory(client(pages+[[row(1001)]]),8,0)


def test_context_rechecks_forum_authority_and_stable_population():
    population={'population_exhausted':True,'role_unknown':0,'student_rows':2,'users_scanned':3}
    scope={'course_id':7,'forum_id':8,'group_id':0}
    with patch('lamb.moodle.analytics.forum_context.validate_forum_scope') as validate, \
         patch('lamb.moodle.analytics.forum_context.MoodleScope') as teacher, \
         patch('lamb.moodle.analytics.forum_context._students',return_value=({2,1},population)):
        result=forum_context(client([[row(3)]]),9,scope)
        assert result['students']==[1,2] and validate.call_count==2
        assert validate.call_args.args[1]==dict(scope,discussion_id=0)
        teacher.return_value.require_teacher.assert_called_once_with(7)
        assert result['fingerprint']==forum_context(client([[row(3)]]),9,scope)['fingerprint']
        assert result['fingerprint']!=forum_context(client([[row(4)]]),9,scope)['fingerprint']


@pytest.mark.parametrize('population', [
    {'population_exhausted':False,'role_unknown':0},
    {'population_exhausted':True,'role_unknown':1},
])
def test_unknown_population_never_reads_discussions(population):
    c=client([])
    with patch('lamb.moodle.analytics.forum_context.validate_forum_scope'), \
         patch('lamb.moodle.analytics.forum_context.MoodleScope'), \
         patch('lamb.moodle.analytics.forum_context._students',return_value=(set(),population)):
        with pytest.raises(ValueError):forum_context(c,9,{'course_id':7,'forum_id':8,'group_id':0})
    c.call.assert_not_called()
