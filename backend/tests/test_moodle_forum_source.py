from copy import deepcopy
import pytest
from lamb.moodle.analytics.forum_source import normalize_discussion
from lamb.moodle.analytics.forum_participation import summarize_forums


def response():
    return {'courseid':3, 'forumid':4, 'warnings':[], 'posts':[
        {'id':10, 'discussionid':5, 'hasparent':False, 'parentid':None,
         'isdeleted':False, 'isprivatereply':False, 'capabilities':{'view':True},
         'author':{'id':1, 'fullname':'PRIVATE NAME'}, 'timecreated':100,
         'timemodified':200, 'message':'PRIVATE TEXT', 'subject':'PRIVATE TITLE'}]}


def normalize(data, **discussion):
    return normalize_discussion(data, course_id=3, forum_id=4,
        discussion=dict(id=5, timestart=0, timeend=0, **discussion))


def test_source_minimization_preserves_creation_not_modification():
    data = response(); before = deepcopy(data)
    result = normalize(data)
    assert data == before and 'PRIVATE' not in repr(result)
    assert result['posts'][0]['created'] == 100
    assert result['complete'] and result['timestamp_basis'] == 'stored_creation_untimed_discussion'
    reduced = summarize_forums([result], [1], since=100, until=150, as_of=250,
                              timezone='UTC', inventory_complete=True)
    assert reduced['student_public_posts_in_window'] == 1


def test_timed_source_is_not_mislabelled_creation():
    with pytest.raises(ValueError, match='raw-creation'):
        normalize_discussion(response(), course_id=3, forum_id=4,
                             discussion={'id':5, 'timestart':99, 'timeend':0})


@pytest.mark.parametrize('flag', ['hidden', 'deleted'])
def test_hidden_and_deleted_fields_are_never_counted(flag):
    data = response()
    data['posts'][0]['capabilities']['view'] = flag != 'hidden'
    data['posts'][0]['isdeleted'] = flag == 'deleted'
    result = normalize(data)
    assert result['posts'][0]['author_id'] is None and result['posts'][0]['created'] is None
    reduced = summarize_forums([result], [1], since=100, until=150, as_of=250,
                              timezone='UTC', inventory_complete=True)
    assert reduced['student_public_posts_in_window'] == 0
    assert reduced['discussion_rows'][0]['no_observed_public_replies'] is None


def test_warnings_force_partial_coverage():
    data = response(); data['warnings'] = [{'warningcode':'fixture'}]
    assert normalize(data)['complete'] is False


@pytest.mark.parametrize('mutation', [
    lambda r:r.update(courseid=True), lambda r:r.update(forumid=9),
    lambda r:r.pop('warnings'), lambda r:r['posts'].append(deepcopy(r['posts'][0])),
    lambda r:r['posts'][0].update(discussionid=6),
    lambda r:r['posts'][0].update(hasparent=True),
    lambda r:r['posts'][0].update(parentid=9),
    lambda r:r['posts'][0].update(isprivatereply=1),
    lambda r:r['posts'][0].update(author={'id':True}),
    lambda r:r['posts'][0].update(capabilities={}),
    lambda r:r['posts'][0].update(capabilities=None),
    lambda r:r['posts'][0].update(author=None),
    lambda r:r['posts'].append(None),
])
def test_mismatched_or_ambiguous_source_rejected(mutation):
    data = response(); mutation(data)
    with pytest.raises(ValueError): normalize(data)
