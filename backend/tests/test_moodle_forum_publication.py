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


@pytest.mark.parametrize('recipe',['forum-participation','forum-discussions'])
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
