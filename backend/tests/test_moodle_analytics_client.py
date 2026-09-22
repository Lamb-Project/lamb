import json
import httpx
import pytest
from urllib.parse import parse_qs
from moodle_cli.client.exceptions import ReadOnlyViolation, MoodleAPIError, ConnectionError
from moodle_cli.client.readonly import READ_ALLOWLIST
from lamb.moodle.analytics.client import AnalyticsHTTPClient, EVENT_FUNCTION, SCOPE_FUNCTION, MAX_EVENT_BYTES


def client(handler):
    c = AnalyticsHTTPClient('https://fixture.test', 'private-test-token', readonly=True)
    c._client.close()
    c._client = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_only_reviewed_extension_bypasses_upstream_allowlist():
    before = set(READ_ALLOWLIST)
    def respond(request):
        form = parse_qs(request.content.decode())
        assert form['wsfunction'] == [EVENT_FUNCTION]
        assert form['courseid'] == ['7']
        return httpx.Response(200,json={'events':[]})
    with client(respond) as c:
        assert c.call(EVENT_FUNCTION,courseid=7,since=1,until=2) == {'events':[]}
        with pytest.raises(ReadOnlyViolation):
            c.call('mod_page_view_page',pageid=1)
        with pytest.raises(ReadOnlyViolation):
            c.call('local_arbitrary_execute',command='anything')
        assert c.readonly is True
    assert set(READ_ALLOWLIST) == before


@pytest.mark.parametrize('extra', [{'wstoken':'replacement'}, {'sql':'SELECT'}, {'limit':True}, {'courseid':'7'}])
def test_parameters_cannot_override_transport_or_accept_coercion(extra):
    with client(lambda request:pytest.fail('Must reject before network')) as c:
        with pytest.raises(ValueError):
            c.call(EVENT_FUNCTION,**({'courseid':7,'since':1,'until':2} | extra))


@pytest.mark.parametrize('payload', [b'not-json', b'[]', b'x'*(MAX_EVENT_BYTES+1)])
def test_malformed_and_oversized_responses_fail_closed(payload):
    with client(lambda request:httpx.Response(200,content=payload)) as c:
        with pytest.raises(ValueError): c.call(EVENT_FUNCTION,courseid=7,since=1,until=2)


def test_plugin_errors_do_not_expose_debug_details():
    with client(lambda request:httpx.Response(200,json={'exception':'error','errorcode':'nopermissions',
                    'message':'secret-server-path','debuginfo':'private-test-token'})) as c:
        with pytest.raises(MoodleAPIError) as exc: c.call(EVENT_FUNCTION,courseid=7,since=1,until=2)
        assert 'secret-server-path' not in str(exc.value) and 'private-test-token' not in str(exc.value)


def test_standard_reads_still_use_upstream_client():
    with client(lambda request:httpx.Response(200,json={'userid':12})) as c:
        assert c.call('core_webservice_get_site_info') == {'userid':12}


def test_permission_only_extension_sends_bounded_module_ids_not_event_query():
    def respond(request):
        form=parse_qs(request.content.decode())
        assert form['wsfunction'] == [SCOPE_FUNCTION]
        assert form['cmids[0]'] == ['10'] and 'since' not in form
        return httpx.Response(200,json={'authorized':True})
    with client(respond) as c:
        assert c.call(SCOPE_FUNCTION,courseid=7,groupid=2,cmids=[10])['authorized']
    for values in ([True], [1,1], list(range(1,102)), '10'):
        with client(lambda request:pytest.fail('No network expected')) as c:
            with pytest.raises(ValueError): c.call(SCOPE_FUNCTION,courseid=7,cmids=values)
