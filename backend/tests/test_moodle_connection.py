import json
from urllib.parse import parse_qs
import httpx
import pytest
from cryptography.fernet import Fernet
from lamb.moodle.connection import establish_connection, public_connection, MoodleConnectionError
from lamb.moodle.policy import MoodlePolicy
from lamb.moodle.secrets import TokenCipher

BASE='https://moodle.test'
INFO={'sitename':'Disposable fixture','siteurl':BASE,'username':'teacher','fullname':'Fixture Teacher','userid':7,'lang':'en','release':'4.5','version':'2024100700','functions':[]}

def connect(**kwargs):
    return establish_connection(MoodlePolicy(True,BASE),TokenCipher(Fernet.generate_key()),organization_id=1,owner_id=2,**kwargs)


def test_direct_token_verified_and_encrypted(respx_mock):
    route=respx_mock.post(BASE+'/webservice/rest/server.php').mock(return_value=httpx.Response(200,json=INFO))
    record=connect(token='fixture-secret')
    assert record['moodle_user_id']==7
    assert 'fixture-secret' not in json.dumps(record)
    assert 'token_encrypted' not in public_connection(record)
    body=parse_qs(route.calls[0].request.content.decode())
    assert body['wsfunction']==['core_webservice_get_site_info']


def test_qr_exchange_then_verify(respx_mock):
    qr=respx_mock.post(BASE+'/lib/ajax/service-nologin.php').mock(return_value=httpx.Response(200,json=[{'error':False,'data':{'token':'fixture-secret','privatetoken':'not-stored'}}]))
    respx_mock.post(BASE+'/webservice/rest/server.php').mock(return_value=httpx.Response(200,json=INFO))
    record=connect(passport='moodlemobile://https://moodle.test?qrlogin=one-use&userid=7')
    assert record['username']=='teacher'
    assert json.loads(qr.calls[0].request.content)[0]['methodname']=='tool_mobile_get_tokens_for_qr_login'
    assert 'MoodleMobile' in qr.calls[0].request.headers['user-agent']
    assert 'not-stored' not in json.dumps(record)


def test_foreign_passport_rejected_before_network(respx_mock):
    with pytest.raises(PermissionError): connect(passport='moodlemobile://https://foreign.test?qrlogin=secret&userid=7')
    assert not respx_mock.calls


@pytest.mark.parametrize('info',[{**INFO,'siteurl':'https://foreign.test'},{**INFO,'userid':8}])
def test_identity_mismatch_rejected(respx_mock,info):
    respx_mock.post(BASE+'/lib/ajax/service-nologin.php').mock(return_value=httpx.Response(200,json=[{'data':{'token':'fixture-secret'}}]))
    respx_mock.post(BASE+'/webservice/rest/server.php').mock(return_value=httpx.Response(200,json=info))
    with pytest.raises(MoodleConnectionError):connect(passport='moodlemobile://https://moodle.test?qrlogin=one-use&userid=7')


def test_exchange_failure_does_not_echo_passport_or_server_secret(respx_mock):
    respx_mock.post(BASE+'/lib/ajax/service-nologin.php').mock(return_value=httpx.Response(200,json=[{'error':True,'exception':{'message':'fixture-secret','errorcode':'invalidkey'}}]))
    with pytest.raises(MoodleConnectionError) as error:connect(passport='moodlemobile://https://moodle.test?qrlogin=one-use&userid=7')
    assert 'fixture-secret' not in str(error.value)
    assert 'one-use' not in str(error.value)
