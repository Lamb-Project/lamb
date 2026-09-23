from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest
from lamb.moodle.analytics.forum_snapshot import snapshot


def state():
    return dict(done=True,cursor=None,scope=dict(course_id=7,forum_id=8,group_id=0),
        context={'students':[10,11],'discussions':[{'discussion_id':9}]},
        threads=[{'id':9,'forum_id':8,'complete':True,'posts':[
            dict(id=1,parent_id=None,author_id=10,created=110,deleted=False,private=False),
            dict(id=2,parent_id=1,author_id=99,created=160,deleted=False,private=False)]}],
        since=100,until=150,as_of=200,language='en',tz='Europe/Madrid',
        started_at=datetime.fromtimestamp(190,timezone.utc).isoformat(),
        completed_at=datetime.fromtimestamp(200,timezone.utc).isoformat())


@pytest.mark.parametrize('language',['en','es','ca','eu'])
def test_exact_ranked_learner_rows_and_zero(language):
    s=state();s['language']=language;before=deepcopy(s)
    data=snapshot(s,'run',recipe='forum-participation')
    assert s==before
    assert [r['student_id'] for r in data['rows']]==[10,11]
    assert [r['posts'] for r in data['rows']]==[1,0]
    assert data['rows'][0]['active_local_days']==1
    assert data['metrics']['students_without_observed_public_posts']==1
    assert data['forum_scopes']==[dict(s['scope'],discussion_ids=[9])]
    assert 'author_id' not in json.dumps(data) and 'student_rows' not in data['metrics']


def test_discussion_uses_all_authors_outside_window_and_unknown_resolution():
    data=snapshot(state(),'run',recipe='forum-discussions')
    row=data['rows'][0]
    assert row['observed_public_posts_in_window']==1
    assert row['observed_public_replies_as_of']==1
    assert row['seconds_since_last_observed_public_post']==40
    assert row['resolution_status']=='unknown' and row['no_observed_public_replies'] is False
    assert 'student_id' not in json.dumps(data) and 'author_id' not in json.dumps(data)


def test_partial_thread_does_not_claim_no_replies():
    s=state();s['threads'][0]['posts']=[]
    data=snapshot(s,'run',recipe='forum-discussions')
    assert data['rows'][0]['no_observed_public_replies'] is None
    assert data['rows'][0]['status']=='partial' and not data['coverage']['complete']


@pytest.mark.parametrize('change',[{'done':False},{'cursor':{}},{'as_of':201},
    {'completed_at':'1970-01-01T00:03:20'}, {'threads':[]}])
def test_invalid_or_unfinished_state_rejected(change):
    with pytest.raises(ValueError):snapshot(state()|change,'run',recipe='forum-participation')
