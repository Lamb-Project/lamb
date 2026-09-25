import asyncio
from unittest.mock import patch
import pytest
import respx
from httpx import Response
from moodle_cli.client.exceptions import ReadOnlyViolation, MoodleAPIError
from lamb.moodle.client import MoodleHTTPClient, function_names
from lamb.aac.liteshell.shell import LiteShell
from tests.test_moodle_runtime import runtime
from tests.test_moodle_store import stores


@pytest.mark.parametrize('metadata', [None, [], 'bad', [{'name':'bad message!'}], [{}]])
def test_optional_catalogue_does_not_require_reconnection(metadata):
    assert function_names(metadata) is None


def test_catalogue_retains_only_identifiers():
    assert function_names([{'name':'core_webservice_get_site_info','description':'untrusted'},
                           {'name':'core_webservice_get_site_info'}]) == ['core_webservice_get_site_info']


@respx.mock
def test_known_missing_api_does_not_make_request():
    with MoodleHTTPClient('https://moodle.test','fixture',readonly=True,
                          functions=['core_webservice_get_site_info']) as client:
        with pytest.raises(PermissionError,match='unavailable, not empty'):
            client.call('core_enrol_get_users_courses',userid=7)
    assert not respx.calls


@respx.mock
@pytest.mark.parametrize('code', ['webservicenotavailable','servicenotavailable','accessexception','nopermissions'])
def test_server_denial_is_sanitized_and_not_retried(code):
    route=respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200,
        json={'exception':'fixture','errorcode':code,'message':'SECRET upstream prose','debuginfo':'SECRET'}))
    with MoodleHTTPClient('https://moodle.test','fixture',readonly=True) as client:
        with pytest.raises(PermissionError) as error:client.call('core_enrol_get_users_courses',userid=7)
    assert 'SECRET' not in str(error.value) and 'Do not retry' in str(error.value)
    assert route.call_count==1


@respx.mock
def test_legacy_connection_reads_normally():
    respx.post('https://moodle.test/webservice/rest/server.php').mock(return_value=Response(200,json=[]))
    with MoodleHTTPClient('https://moodle.test','fixture',readonly=True) as client:
        assert client.call('core_enrol_get_users_courses',userid=7)==[]


@respx.mock
def test_catalogue_does_not_authorize_writes():
    with MoodleHTTPClient('https://moodle.test','fixture',readonly=True,functions=['mod_forum_add_discussion']) as client:
        with pytest.raises(ReadOnlyViolation):client.call('mod_forum_add_discussion',forumid=1)
    assert not respx.calls


@respx.mock
def test_shell_reports_missing_api_without_hiding_all_reads(stores):
    rt=runtime(stores)
    original=rt.store.snapshot
    def snapshot():
        snap=original();snap['record']['functions']=['core_webservice_get_site_info'];return snap
    with patch.object(rt.store,'snapshot',snapshot):
        assert 'moodle.enrol.my-courses' in rt.available()
        assert 'moodle.forum.reply' not in rt.available()
        shell=LiteShell('','','fixture@test',1,user_id=7,moodle=rt,allowed_commands=rt.available())
        result=asyncio.run(shell.execute('moodle enrol my-courses'))
        assert not result.success and 'unavailable, not empty' in result.error
    assert not respx.calls
