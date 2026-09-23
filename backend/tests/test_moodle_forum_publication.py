from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from lamb.moodle.analytics.forum_run import publish
from lamb.moodle.charts import ChartStore
from lamb.moodle.analytics.recipes import result_page
from tests.test_moodle_forum_snapshot import state
from tests.test_moodle_forum_checkpoints import store


def setup(tmp_path, data=None):
    s=store(tmp_path);record=s.create(data or state())
    binding={k:s.binding[k] for k in ('base_url','moodle_user_id','generation')}
    rt=SimpleNamespace(cache_root=tmp_path,store=SimpleNamespace(organization_id=1,owner_id=2),
        result_binding=lambda:binding,validate_result_binding=Mock())
    return s,record['id'],rt,SimpleNamespace(checkpoint=lambda:None)


def test_two_immutable_publications_and_retry(tmp_path):
    s,identity,rt,c=setup(tmp_path)
    first=publish(s,rt,c,identity,recipe='forum-participation')
    second=publish(s,rt,c,identity,recipe='forum-discussions')
    assert first['chart_id']!=second['chart_id']
    assert publish(s,rt,c,identity,recipe='forum-participation')==first
    assert len(list(ChartStore(rt).root.glob('*.json')))==2
    assert all(call.args[0]['forum_scopes']==[dict(state()['scope'],discussion_ids=[9])]
               for call in rt.validate_result_binding.call_args_list)


def test_failed_save_resumes_reserved_identity(tmp_path):
    s,identity,rt,c=setup(tmp_path)
    with patch.object(ChartStore,'save',side_effect=OSError('interrupted')):
        with pytest.raises(OSError):publish(s,rt,c,identity,recipe='forum-discussions')
    reservation=s.read(identity)['state']['publications']['forum-discussions']['id']
    assert publish(s,rt,c,identity,recipe='forum-discussions')['chart_id']==reservation


def test_revoke_and_cross_owner_prevent_publication(tmp_path):
    s,identity,rt,c=setup(tmp_path)
    rt.validate_result_binding.side_effect=PermissionError('revoked')
    with pytest.raises(PermissionError):publish(s,rt,c,identity,recipe='forum-participation')
    assert 'publications' not in s.read(identity)['state']
    rt.store.owner_id=99
    with pytest.raises(PermissionError,match='another connection'):
        publish(s,rt,c,identity,recipe='forum-participation')


@pytest.mark.parametrize('recipe',['forum-participation','forum-discussions','forum-network'])
def test_maximum_tables_fit_and_page_without_loss(tmp_path,recipe):
    data=state(); data['context']['students']=list(range(1000,2000))
    data['context']['discussions']=[{'discussion_id':i} for i in range(1,1001)]
    data['threads']=[{'id':i,'forum_id':8,'complete':True,'posts':[
        dict(id=i,parent_id=None,author_id=999+i,created=110,deleted=False,private=False)]}
        for i in range(1,1001)]
    s,identity,rt,c=setup(tmp_path,data)
    result=publish(s,rt,c,identity,recipe=recipe)
    saved=ChartStore(rt).read(result['chart_id'])
    assert len(saved['rows'])==1000
    received=[];offset=0
    while offset is not None:
        page=result_page(result['chart_id'],saved,offset)
        received.extend(page['rows']);offset=page['next_offset']
    assert received==saved['rows']


def test_network_save_retry_scope_revocation_and_read_semantics(tmp_path):
    s,identity,rt,c=setup(tmp_path)
    with patch.object(ChartStore,'save',side_effect=OSError('interrupted')):
        with pytest.raises(OSError):publish(s,rt,c,identity,recipe='forum-network')
    reservation=s.read(identity)['state']['publications']['forum-network']['id']
    result=publish(s,rt,c,identity,recipe='forum-network')
    assert result['chart_id']==reservation
    assert publish(s,rt,c,identity,recipe='forum-network')==result
    saved=ChartStore(rt).read(reservation)
    assert saved['forum_scopes']==[dict(state()['scope'],discussion_ids=[9])]
    assert saved['window_start_local']=='1970-01-01T01:01:40+01:00'
    assert 'reply relationships' in saved['forum_exclusion_basis']
    assert 'immediate parent' in saved['forum_reply_basis']
    rt.validate_result_binding.side_effect=PermissionError('revoked')
    with pytest.raises(PermissionError):ChartStore(rt).read(reservation)
    with pytest.raises(PermissionError):publish(s,rt,c,identity,recipe='forum-network')


def test_dense_small_network_fits_without_losing_edges(tmp_path):
    data=state();data['context']['students']=list(range(1,51))
    data['context']['discussions']=[];data['threads']=[]
    pid=0
    for target in range(1,51):
        pid+=1;root=pid
        posts=[dict(id=root,parent_id=None,author_id=target,created=110,deleted=False,private=False)]
        for source in range(1,51):
            if source==target:continue
            pid+=1
            posts.append(dict(id=pid,parent_id=root,author_id=source,created=120,deleted=False,private=False))
        data['context']['discussions'].append({'discussion_id':target})
        data['threads'].append(dict(id=target,forum_id=8,complete=True,posts=posts))
    s,identity,rt,c=setup(tmp_path,data)
    result=publish(s,rt,c,identity,recipe='forum-network')
    saved=ChartStore(rt).read(result['chart_id'])
    assert len(saved['network']['edges'])==2450
    assert saved['metrics']['peer_replies']==2450
    assert all((r['in_degree'],r['out_degree'],r['unique_peers'])==(49,49,49) for r in saved['rows'])
