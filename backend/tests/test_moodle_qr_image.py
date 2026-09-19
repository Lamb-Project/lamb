from io import BytesIO
from unittest.mock import patch
import pytest
import zxingcpp
from PIL import Image
from lamb.moodle.qr_image import decode_passport
from lamb.moodle.connection import MoodleConnectionError
from tests.test_moodle_router import client
from tests.test_moodle_store import stores, record

PASSPORT='moodlemobile://https://moodle.test?qrlogin=one-use-secret&userid=7'

def qr(text=PASSPORT):
    out=BytesIO()
    Image.fromarray(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode,text,width=500,height=500)).save(out,format='PNG')
    return out.getvalue()


def test_real_decoder_handles_image_and_rotated_screenshot():
    image=Image.open(BytesIO(qr())).convert('RGB')
    canvas=Image.new('RGB',(1000,900),'white');canvas.paste(image,(130,110))
    out=BytesIO();canvas.rotate(90,expand=True).save(out,format='PNG')
    assert decode_passport(out.getvalue())==PASSPORT

@pytest.mark.parametrize('text,message',[
    ('moodlemobile://https://moodle.test','site address'),
    ('https://other.test','not a Moodle'),
    ('moodlemobile://https://moodle.test?qrlogin=secret&userid=no','Invalid Moodle')])
def test_bad_qr_is_actionable_without_echoing_credentials(text,message):
    with pytest.raises(MoodleConnectionError,match=message) as error:decode_passport(qr(text))
    assert 'secret' not in str(error.value)


def test_invalid_large_and_multiple_images():
    for payload in (b'not an image',b'x'*(5*1024*1024+1)):
        with pytest.raises(MoodleConnectionError):decode_passport(payload)
    blank=BytesIO();Image.new('RGB',(100,100),'white').save(blank,format='PNG')
    with pytest.raises(MoodleConnectionError,match='No readable'):decode_passport(blank.getvalue())
    out=BytesIO();Image.new('RGB',(4000,4000),'white').save(out,format='PNG')
    with pytest.raises(MoodleConnectionError,match='too large'):decode_passport(out.getvalue())
    tile=Image.open(BytesIO(qr()));other=Image.open(BytesIO(qr(PASSPORT.replace('userid=7','userid=8'))))
    canvas=Image.new('RGB',(tile.width+other.width+100,max(tile.height,other.height)+100),'white')
    canvas.paste(tile,(10,10));canvas.paste(other,(tile.width+80,10));out=BytesIO();canvas.save(out,format='PNG')
    with pytest.raises(MoodleConnectionError,match='More than one'):decode_passport(out.getvalue())


def test_upload_reuses_private_connection_and_never_returns_passport(client):
    c,auth,store=client
    with patch('lamb.moodle.router.establish_connection',return_value=record()) as establish:
        result=c.post('/moodle/connection/qr-image',content=qr(),headers={'Content-Type':'application/octet-stream'})
    assert result.status_code==200,result.text
    assert establish.call_args.kwargs['passport']==PASSPORT
    assert 'secret' not in result.text and 'ciphertext' not in result.text
    assert store.snapshot()['record']


def test_upload_errors_and_anonymous_denial(client):
    c,auth,store=client
    with patch('lamb.moodle.router.establish_connection') as establish:
        assert c.post('/moodle/connection/qr-image',content=b'x'*(5*1024*1024+1)).status_code==413
        assert c.post('/moodle/connection/qr-image',content=b'bad').status_code==400
        establish.assert_not_called()
    c.app.dependency_overrides.clear()
    assert c.post('/moodle/connection/qr-image',content=qr()).status_code in (401,403)


def test_foreign_qr_rejected_before_exchange(client):
    c,auth,store=client
    with patch('lamb.moodle.connection.exchange_qr_login') as exchange:
        response=c.post('/moodle/connection/qr-image',content=qr(PASSPORT.replace('moodle.test','foreign.test')))
    assert response.status_code==403 and 'one-use-secret' not in response.text
    exchange.assert_not_called()


def test_image_exchange_identity_and_encryption_end_to_end(client,respx_mock):
    import httpx,json
    from tests.test_moodle_connection import INFO
    from lamb.moodle.secrets import TokenCipher
    c,auth,store=client
    exchange=respx_mock.post('https://moodle.test/lib/ajax/service-nologin.php').mock(
        return_value=httpx.Response(200,json=[{'error':False,'data':{'token':'mobile-secret'}}]))
    respx_mock.post('https://moodle.test/webservice/rest/server.php').mock(return_value=httpx.Response(200,json=INFO))
    response=c.post('/moodle/connection/qr-image',content=qr())
    assert response.status_code==200,response.text
    saved=store.snapshot()['record']
    assert TokenCipher().decrypt(saved['token_encrypted'],organization_id=1,owner_id=7,base_url='https://moodle.test')=='mobile-secret'
    assert 'mobile-secret' not in json.dumps(saved) and 'one-use-secret' not in response.text
    previous=store.snapshot()
    exchange.mock(return_value=httpx.Response(200,json=[{'error':True,'exception':{'errorcode':'invalidkey','message':'one-use-secret'}}]))
    response=c.post('/moodle/connection/qr-image',content=qr())
    assert response.status_code==400 and 'expired' in response.text and 'one-use-secret' not in response.text
    assert store.snapshot()==previous
