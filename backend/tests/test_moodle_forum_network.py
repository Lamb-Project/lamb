from copy import deepcopy

import pytest

from lamb.moodle.analytics.forum_network import summarize_network


def post(i, author, parent=None, created=110, **extra):
    return dict(id=i, author_id=author, parent_id=parent, created=created,
                private=False, deleted=False, **extra)


def run(posts, students=(1,2,3), **kw):
    opts=dict(since=100, until=200, as_of=300, timezone='UTC', inventory_complete=True)
    opts.update(kw)
    return summarize_network([dict(id=1,forum_id=1,complete=True,posts=posts)],students,**opts)


def test_direction_unique_peers_weight_and_boundary():
    posts=[post(1,1,created=50),post(2,2,1),post(3,2,1),post(4,1,2,created=120),
           post(5,3,1,created=200),post(6,2,2),post(7,9,1),post(8,1,7,created=120)]
    original=deepcopy(posts)
    result=run(posts)
    assert posts==original
    assert result['edges']==[
        dict(source_student_id=1,target_student_id=2,replies=1),
        dict(source_student_id=2,target_student_id=1,replies=2)]
    assert result['peer_replies']==3 and result['directed_edges']==2
    a,b,c=result['student_rows']
    assert (a['in_degree'],a['out_degree'],a['unique_peers'],a['incoming_replies'],a['outgoing_replies'])==(1,1,1,2,1)
    assert (b['incoming_replies'],b['outgoing_replies'])==(1,2)
    assert c['no_observed_peer_interaction'] is True
    assert result['coverage']['excluded_reply_relationships']=={'self_reply':1,'outside_current_student_population':2}


@pytest.mark.parametrize('kind',['private','deleted','redacted','missing','future'])
def test_unavailable_parent_never_fabricates_edge_or_isolation(kind):
    parent=post(1,1,created=50)
    if kind in ('private','deleted'):parent[kind]=True
    if kind=='redacted':parent['author_id']=None
    if kind=='future':parent['created']=150
    result=run(([parent] if kind!='missing' else [])+[post(2,2,1)])
    assert result['edges']==[] and not result['coverage']['complete']
    assert all(r['no_observed_peer_interaction'] is None for r in result['student_rows'])


def test_partial_inventory_and_text_not_projected():
    result=run([post(1,1,message='SECRET'),post(2,2,1,subject='SECRET')],inventory_complete=False)
    assert result['peer_replies']==1 and not result['coverage']['complete']
    assert 'SECRET' not in str(result)
    assert all(r['no_observed_peer_interaction'] is None for r in result['student_rows'])


def test_large_star_has_exact_degrees_and_zero_rows():
    result=run([post(1,1)]+[post(i,i,1) for i in range(2,401)],students=list(range(1,501)))
    assert result['directed_edges']==399 and result['peer_replies']==399
    root=result['student_rows'][0]
    assert (root['in_degree'],root['out_degree'],root['unique_peers'])==(399,0,399)
    assert sum(r['no_observed_peer_interaction'] for r in result['student_rows'])==100


@pytest.mark.parametrize('posts',[
    [post(1,1),post(1,2)],
    [post(1,1,2),post(2,2,1)],
    [post(1,1,created=301)],
])
def test_invalid_source_rejected(posts):
    with pytest.raises(ValueError):run(posts)
