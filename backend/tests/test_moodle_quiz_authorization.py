from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from lamb.moodle.analytics.quiz_authorization import validate_quiz_scope
from lamb.moodle.analytics.client import QUIZ_SCOPE_FUNCTION
from tests.test_moodle_analytics_client import client

SCOPE={'course_id':7,'quiz_id':2,'group_id':0}
RESPONSE={'authorized':True,'courseid':7,'quizid':2,'groupid':0}


def test_exact_scope_only_request():
    source=SimpleNamespace(call=Mock(return_value=RESPONSE))
    validate_quiz_scope(source,SCOPE)
    source.call.assert_called_once_with(QUIZ_SCOPE_FUNCTION,courseid=7,quizid=2,groupid=0)


@pytest.mark.parametrize('change',[{'quizid':3},{'groupid':1},{'courseid':8},{'authorized':1},
    {'authorized':False},{'quizid':2.0},{'attempts':[]}])
def test_response_mismatch_or_evidence_in_permission_response_denies(change):
    with pytest.raises(PermissionError):
        validate_quiz_scope(SimpleNamespace(call=lambda *a,**kw:RESPONSE|change),SCOPE)


@pytest.mark.parametrize('change',[{'quiz_id':True},{'course_id':0},{'group_id':-1},{'extra':1}])
def test_invalid_saved_scope_never_calls_source(change):
    source=SimpleNamespace(call=Mock())
    with pytest.raises(PermissionError):validate_quiz_scope(source,SCOPE|change)
    source.call.assert_not_called()


def test_transport_is_fixed_and_byte_bounded():
    with client(lambda request:httpx.Response(200,json=RESPONSE)) as source:
        validate_quiz_scope(source,SCOPE)
    for change in ({'courseid':True},{'quizid':0},{'groupid':-1},{'wstoken':'replacement'},{'sql':'query'}):
        with client(lambda request:pytest.fail('No network expected')) as source:
            with pytest.raises(ValueError):source.call(QUIZ_SCOPE_FUNCTION,**({'courseid':7,'quizid':2}|change))
    with client(lambda request:httpx.Response(200,content=b'x'*4097)) as source:
        with pytest.raises(ValueError,match='byte budget'):validate_quiz_scope(source,SCOPE)


def test_revocation_is_sanitized():
    with client(lambda request:httpx.Response(200,json={'exception':'error','errorcode':'nopermissions','message':'secret'})) as source:
        with pytest.raises(PermissionError,match='no longer available') as exc:validate_quiz_scope(source,SCOPE)
        assert 'secret' not in str(exc.value)


def test_quiz_attempt_transport_retains_raw_fields_without_global_allowlist_change():
    from lamb.moodle.analytics.client import QUIZ_ATTEMPTS_FUNCTION,MAX_EVENT_BYTES
    from moodle_cli.client.readonly import READ_ALLOWLIST
    before=set(READ_ALLOWLIST)
    payload={'attempts':[{'sumgrades':None,'preview':False,'attempt':2}],'has_more':False}
    with client(lambda request:httpx.Response(200,json=payload)) as source:
        assert source.call(QUIZ_ATTEMPTS_FUNCTION,courseid=7,quizid=2,limit=1)==payload
    assert set(READ_ALLOWLIST)==before
    for change in ({'limit':201},{'limit':0},{'limit':True},{'afterid':2},
                  {'afterid':3,'throughid':2},{'quizid':'2'},{'groupid':-1},
                  {'userid':1},{'wstoken':'replacement'},{'fields':'questiontext'}):
        with client(lambda request:pytest.fail('No network expected')) as source:
            with pytest.raises(ValueError):source.call(QUIZ_ATTEMPTS_FUNCTION,**({'courseid':7,'quizid':2}|change))
    with client(lambda request:httpx.Response(200,content=b'x'*(MAX_EVENT_BYTES+1))) as source:
        with pytest.raises(ValueError,match='byte budget'):
            source.call(QUIZ_ATTEMPTS_FUNCTION,courseid=7,quizid=2)
