from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from lamb.moodle.analytics.forum_authorization import validate_forum_scope
from lamb.moodle.analytics.client import FORUM_SCOPE_FUNCTION
from tests.test_moodle_analytics_client import client

SCOPE = {'course_id':7, 'forum_id':2, 'discussion_id':3, 'group_id':0}
RESPONSE = {'authorized':True, 'courseid':7, 'forumid':2, 'discussionid':3, 'groupid':0}


def test_exact_authority_without_post_collection():
    source = SimpleNamespace(call=Mock(return_value=RESPONSE))
    validate_forum_scope(source, SCOPE)
    source.call.assert_called_once_with(FORUM_SCOPE_FUNCTION, courseid=7, forumid=2, discussionid=3, groupid=0)


def test_explicit_forum_inventory_scope():
    with client(lambda request:httpx.Response(200,json=RESPONSE|{'discussionid':0})) as source:
        validate_forum_scope(source,SCOPE|{'discussion_id':0})


@pytest.mark.parametrize('change', [{'authorized':1}, {'courseid':8}, {'forumid':9},
    {'discussionid':4}, {'groupid':1}, {'discussionid':3.0}, {'posts':[]}])
def test_scope_mismatch_denied(change):
    with pytest.raises(PermissionError):
        validate_forum_scope(SimpleNamespace(call=lambda *a,**k:RESPONSE|change), SCOPE)


@pytest.mark.parametrize('change', [{'course_id':True}, {'discussion_id':-1}, {'group_id':-1}, {'extra':1}])
def test_invalid_saved_scope_never_calls(change):
    with pytest.raises(PermissionError):
        validate_forum_scope(SimpleNamespace(call=lambda *a,**k:pytest.fail('No source call expected')), SCOPE|change)


def test_transport_is_fixed_bounded_and_readonly():
    from moodle_cli.client.readonly import READ_ALLOWLIST
    before = set(READ_ALLOWLIST)
    with client(lambda request:httpx.Response(200, json=RESPONSE)) as source:
        validate_forum_scope(source, SCOPE)
    assert set(READ_ALLOWLIST) == before
    for change in ({'forumid':True}, {'discussionid':-1}, {'groupid':-1}, {'wstoken':'override'}, {'fields':'message'}):
        with client(lambda request:pytest.fail('No network expected')) as source:
            with pytest.raises(ValueError):
                source.call(FORUM_SCOPE_FUNCTION, **({'courseid':7,'forumid':2,'discussionid':3}|change))
    with client(lambda request:httpx.Response(200, content=b'x'*4097)) as source:
        with pytest.raises(ValueError, match='byte budget'):validate_forum_scope(source, SCOPE)


def test_revocation_error_does_not_leak_source_text():
    with client(lambda request:httpx.Response(200, json={'exception':'error', 'errorcode':'nopermissions', 'message':'SECRET'})) as source:
        with pytest.raises(PermissionError, match='no longer available') as error:
            validate_forum_scope(source, SCOPE)
        assert 'SECRET' not in str(error.value)


def test_forum_post_transport_is_fixed_bounded_and_readonly():
    from lamb.moodle.analytics.client import FORUM_POSTS_FUNCTION, MAX_EVENT_BYTES
    from moodle_cli.client.readonly import READ_ALLOWLIST
    before = set(READ_ALLOWLIST)
    data = {'posts':[{'id':4,'created':100}], 'timestamp_basis':'stored_creation'}
    with client(lambda request:httpx.Response(200,json=data)) as source:
        assert source.call(FORUM_POSTS_FUNCTION,courseid=7,forumid=2,discussionid=3,limit=1)==data
    assert set(READ_ALLOWLIST)==before
    for change in ({'limit':201},{'limit':True},{'afterid':2},{'afterid':4,'throughid':3},{'discussionid':0},
                   {'userid':1},{'wstoken':'override'},{'fields':'message'},{'discussionid':'3'}):
        with client(lambda request:pytest.fail('No network expected')) as source:
            with pytest.raises(ValueError):
                source.call(FORUM_POSTS_FUNCTION,**({'courseid':7,'forumid':2,'discussionid':3}|change))
    with client(lambda request:httpx.Response(200,content=b'x'*(MAX_EVENT_BYTES+1))) as source:
        with pytest.raises(ValueError,match='byte budget'):
            source.call(FORUM_POSTS_FUNCTION,courseid=7,forumid=2,discussionid=3)
