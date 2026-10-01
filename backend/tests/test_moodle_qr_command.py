import json
import os
from pathlib import Path
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import pytest
from lamb.moodle.qr_command import prepare_command
from lamb.moodle.policy import MoodlePolicy
from lamb.moodle.connection import MoodleConnectionError
from tests.test_moodle_router import client
from tests.test_moodle_store import stores
from tests.test_moodle_qr_image import qr, PASSPORT


@pytest.mark.parametrize('platform', ['macos', 'linux', 'windows'])
def test_preparation_does_not_exchange_or_persist(client, platform):
    c, _, store = client
    before = store.snapshot()
    with patch('lamb.moodle.connection.exchange_qr_login') as exchange:
        response = c.post('/moodle/connection/qr-command?platform=' + platform, content=qr())
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.json()['platform'] == platform
    assert 'one-use-secret' in response.json()['command']
    exchange.assert_not_called()
    assert store.snapshot() == before


def test_preparation_rejects_foreign_disabled_anonymous_and_bad_images(client):
    c, _, store = client
    assert c.post('/moodle/connection/qr-command', content=qr(PASSPORT.replace('moodle.test', 'foreign.test'))).status_code == 403
    assert c.post('/moodle/connection/qr-command', content=b'bad').status_code == 400
    assert c.post('/moodle/connection/qr-command', content=b'x' * (5 * 1024 * 1024 + 1)).status_code == 413
    assert c.post('/moodle/connection/qr-command?platform=bad', content=qr()).status_code == 400
    store.configure({'enabled': False})
    assert c.post('/moodle/connection/qr-command', content=qr()).status_code == 403
    c.app.dependency_overrides.clear()
    assert c.post('/moodle/connection/qr-command', content=qr()).status_code in (401, 403)


@pytest.mark.parametrize('tail', ['qrlogin=x%0ALAMB_LOCAL_LOGIN&userid=7', 'qrlogin=$(touch%20/tmp/unsafe)&userid=7', 'qrlogin=x&qrlogin=y&userid=7', 'qrlogin=x&userid=-1', 'qrlogin=x&userid=7#fragment'])
def test_untrusted_qr_cannot_inject_shell(tail):
    with pytest.raises(MoodleConnectionError):
        prepare_command('moodlemobile://https://moodle.test?' + tail, MoodlePolicy(True, 'https://moodle.test'), 'macos')


@pytest.mark.parametrize('platform,clipboard', [('macos', 'pbcopy'), ('linux', 'wl-copy'), ('linux', 'xclip'), ('linux', 'xsel'), ('windows', 'powershell')])
@pytest.mark.parametrize('reply,success', [
    ([{'error': False, 'data': {'token': 'a' * 32}}], True),
    ([{'error': True, 'exception': {'errorcode': 'ipmismatch', 'message': 'SECRET'}}], False),
    ([{'error': True, 'exception': {'errorcode': 'invalidkey'}}], False),
    ([{'data': {'token': 'bad\ncommand'}}], False),
    ({'token': 'a' * 32}, False),
])
def test_generated_script_real_curl_and_clipboard_failure_preservation(tmp_path, platform, clipboard, reply, success):
    pwsh = os.environ.get('MOODLE_TEST_PWSH')
    if platform == 'windows' and not pwsh:
        pytest.skip('Set MOODLE_TEST_PWSH to test the generated PowerShell command')
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append((self.path, self.headers, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(reply).encode())
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        site = f'http://127.0.0.1:{server.server_port}'
        command = prepare_command(f'moodlemobile://{site}?qrlogin=synthetic&userid=7', MoodlePolicy(True, site), platform)['command']
        clip = tmp_path / 'clipboard'; clip.write_text('previous')
        binary = tmp_path / clipboard
        binary.write_text('#!/bin/sh\ncat > "$TEST_CLIPBOARD"\n'); binary.chmod(0o700)
        env = {**os.environ, 'PATH': str(tmp_path) + ':/usr/bin:/bin', 'TEST_CLIPBOARD': str(clip), 'DISPLAY': ':fixture', 'WAYLAND_DISPLAY': 'fixture' if clipboard == 'wl-copy' else ''}
        shell = ['/bin/sh']
        if platform == 'windows':
            (tmp_path / 'curl.exe').symlink_to('/usr/bin/curl')
            command = 'function Set-Clipboard { param([string]$Value) [System.IO.File]::WriteAllText($env:TEST_CLIPBOARD, $Value) }\n' + command
            script = tmp_path / 'test.ps1'; script.write_text(command)
            shell = [pwsh, '-NoProfile', '-NonInteractive', '-File', str(script)]
        result = subprocess.run(shell, input=command if platform != 'windows' else None, text=True, capture_output=True, env=env, timeout=15)
        if platform != 'windows':
            assert (result.returncode == 0) == success, result.stderr
        assert ('Moodle token copied' in result.stdout) == success, result.stderr
        assert clip.read_text() == ('a' * 32 if success else 'previous')
        assert 'a' * 32 not in result.stdout + result.stderr
        assert 'SECRET' not in result.stdout + result.stderr
        assert len(calls) == 1
        path, headers, payload = calls[0]
        assert path.startswith('/lib/ajax/service-nologin.php?info=')
        assert 'MoodleMobile' in headers['User-Agent']
        assert payload[0]['args'] == {'qrloginkey': 'synthetic', 'userid': 7}
    finally:
        server.shutdown(); server.server_close(); worker.join()
