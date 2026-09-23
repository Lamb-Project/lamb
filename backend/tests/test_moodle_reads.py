from urllib.parse import parse_qs
from unittest.mock import patch
import pytest
import respx
from httpx import Response
from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.client.exceptions import ReadOnlyViolation
from lamb.moodle.contract import prepare_moodle
from lamb.moodle.reads import execute_read, validate_bindings


def test_every_installed_read_has_a_real_service_binding():
    assert validate_bindings()


@respx.mock
def test_forum_read_calls_service_with_own_token_and_preserves_discussion_identity():
    route = respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200,json={'discussions':[{'id':90,'discussion':42,'name':'Question','userid':7}]}))
    spec,params = prepare_moodle('moodle forum discussions 5')
    with MoodleHTTPClient('https://moodle.test','fixture-token',readonly=True) as client:
        result = execute_read(client,spec.key,params,owner_moodle_id=7)
    body=parse_qs(route.calls[0].request.content.decode())
    assert body['wstoken']==['fixture-token']
    assert body['wsfunction']==['mod_forum_get_forum_discussions']
    assert result[0]['first_post_id']==90 and result[0]['discussion_id']==42
    assert 'id' not in result[0] and 'discussion' not in result[0]


@pytest.mark.parametrize('bad', [None, 0, -1, True, '42'])
@pytest.mark.parametrize('field', ['id', 'discussion'])
def test_discussion_result_never_guesses_missing_or_invalid_id(field,bad):
    from lamb.moodle.reads import discussion_result
    row={'id':90,'discussion':42,'name':'Question'};row[field]=bad
    with pytest.raises(ValueError,match='IDs'):discussion_result(row)


def test_discussion_result_preserves_content_without_mutating_source():
    from lamb.moodle.reads import discussion_result
    row={'id':517,'discussion':264,'name':'Question','message':'Original text','numreplies':0}
    assert discussion_result(row)=={'discussion_id':264,'first_post_id':517,'name':'Question','message':'Original text','numreplies':0}
    assert row['id']==517 and row['discussion']==264


@respx.mock
def test_service_cannot_bypass_library_readonly_chokepoint():
    from moodle_cli.services.forum import ForumService
    # Simulate an accidental write leaking through a reviewed service binding.
    with patch.object(ForumService,'get_posts',lambda self,discussion_id:self.call('mod_forum_add_discussion',forumid=1)):
        with MoodleHTTPClient('https://moodle.test','fixture-token',readonly=True) as client:
            with pytest.raises(ReadOnlyViolation):
                execute_read(client,'forum.posts',{'discussion_id':42},owner_moodle_id=7)
    assert not respx.calls


def test_reads_refuse_write_client_and_unknown_binding():
    with MoodleHTTPClient('https://moodle.test','fixture-token',readonly=False) as client:
        with pytest.raises(PermissionError):execute_read(client,'site.info',{},owner_moodle_id=7)
    with MoodleHTTPClient('https://moodle.test','fixture-token',readonly=True) as client:
        with pytest.raises(PermissionError):execute_read(client,'forum.reply',{},owner_moodle_id=7)


@respx.mock
def test_omitted_user_is_explicitly_the_connected_owner():
    route=respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200,json={}))
    spec,params=prepare_moodle('moodle assign status 8')
    with MoodleHTTPClient('https://moodle.test','fixture-token',readonly=True) as client:
        execute_read(client,spec.key,params,owner_moodle_id=70)
    body=parse_qs(route.calls[0].request.content.decode())
    assert body['userid']==['70']
    assert body['assignid']==['8']
