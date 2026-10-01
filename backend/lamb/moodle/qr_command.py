"""Prepare local credential exchange commands; never redeem or persist the QR."""
import json
import re
import shlex
from urllib.parse import parse_qs, urlsplit, urlunsplit
from .connection import MoodleConnectionError

PARSER = """import json,re,sys
try:
    response=json.load(sys.stdin)
    if not isinstance(response,list) or len(response)!=1 or not isinstance(response[0],dict):
        raise ValueError()
    item=response[0]
    if item.get("error"):
        error=item.get("exception") or {}
        code=error.get("errorcode") if isinstance(error,dict) else None
        messages={
            "invalidkey":"QR expired or already used. Generate a fresh QR and try again.",
            "ipmismatch":"Moodle rejected the network address. Use the network that generated the QR.",
            "apprequired":"Moodle rejected the app identification header.",
            "qrcodedisabled":"Moodle QR login is disabled.",
        }
        print(messages.get(code,"Moodle rejected the QR exchange. No token copied."),file=sys.stderr)
        sys.exit(1)
    data=item.get("data")
    token=data.get("token") if isinstance(data,dict) else None
    if not isinstance(token,str) or not re.fullmatch(r"[A-Za-z0-9]{16,256}",token):
        raise ValueError()
except (ValueError,TypeError,KeyError):
    print("Unexpected Moodle response. No token copied.",file=sys.stderr)
    sys.exit(1)
sys.stdout.write(token)
"""


def prepare_command(passport, policy, platform):
    if platform not in {'macos', 'linux', 'windows'}:
        raise MoodleConnectionError('Choose macOS, Linux or Windows.')
    try:
        if len(passport) > 8192 or not passport.startswith('moodlemobile://'):
            raise ValueError()
        url = urlsplit(passport[len('moodlemobile://'):])
        if url.username is not None or url.password is not None or url.fragment:
            raise ValueError()
        site = urlunsplit((url.scheme, url.netloc, url.path, '', ''))
        policy.require_connection_url(site)
        # Never send a credential over plaintext to a remote installation.
        if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in {'localhost', '127.0.0.1', '::1'}):
            raise MoodleConnectionError('Local command login requires HTTPS for this Moodle site.')
        params = parse_qs(url.query, keep_blank_values=True)
        key, user = params['qrlogin'], params['userid']
        if (len(key) != 1 or len(user) != 1 or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', key[0])
                or not re.fullmatch(r'[0-9]{1,20}', user[0]) or int(user[0]) < 1):
            raise ValueError()
    except (ValueError, KeyError) as exc:
        if isinstance(exc, MoodleConnectionError):
            raise
        raise MoodleConnectionError('Invalid Moodle login QR. Generate a fresh QR.') from None
    payload = json.dumps([{'index': 0, 'methodname': 'tool_mobile_get_tokens_for_qr_login',
                           'args': {'qrloginkey': key[0], 'userid': int(user[0])}}], separators=(',', ':'))
    endpoint = policy.base_url + '/lib/ajax/service-nologin.php?info=tool_mobile_get_tokens_for_qr_login'
    script = windows_command(endpoint, payload, url.scheme) if platform == 'windows' else posix_command(endpoint, payload, url.scheme, platform)
    return {'platform': platform, 'command': script, 'base_url': policy.base_url}


def posix_command(endpoint, payload, protocol, platform):
    clipboard = "command -v pbcopy >/dev/null 2>&1 || { echo 'Missing pbcopy.' >&2; exit 1; }; clipboard=pbcopy" if platform == 'macos' else """if command -v wl-copy >/dev/null 2>&1 && [ -n "${WAYLAND_DISPLAY:-}" ]; then clipboard=wl-copy
elif command -v xclip >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then clipboard='xclip -selection clipboard'
elif command -v xsel >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then clipboard='xsel --clipboard --input'
else echo 'Install wl-clipboard (Wayland) or xclip/xsel (X11) and run in your desktop terminal.' >&2; exit 1; fi"""
    return f'''sh <<'LAMB_LOCAL_LOGIN'
set -eu
for needed in curl python3; do
  command -v "$needed" >/dev/null 2>&1 || {{ echo "Missing $needed. Install it before trying again." >&2; exit 1; }}
done
{clipboard}
response=$(curl --silent --show-error --fail --max-time 30 --proto '={protocol}' \
  -H 'Content-Type: application/json' -H 'User-Agent: MoodleMobile 4.5.0' \
  --data-binary @- {shlex.quote(endpoint)} <<'LAMB_QR_PAYLOAD'
{payload}
LAMB_QR_PAYLOAD
) || {{ echo 'Network or HTTP error. No token copied.' >&2; exit 1; }}
token=$(printf '%s' "$response" | python3 -c {shlex.quote(PARSER)}) || exit 1
printf '%s' "$token" | $clipboard || {{ echo 'Could not copy the token.' >&2; exit 1; }}
unset token response
echo 'Moodle token copied. Paste it into LAMB.'
LAMB_LOCAL_LOGIN
'''


def windows_command(endpoint, payload, protocol):
    # PowerShell literal strings escape apostrophes by doubling, never with backslashes.
    endpoint = endpoint.replace("'", "''")
    payload = payload.replace("'", "''")
    return f'''& {{
  $ErrorActionPreference = 'Stop'
  $failure = 'Connection failed. Check curl, your clipboard and network; generate a fresh QR if needed.'
  try {{
    Get-Command curl.exe, Set-Clipboard -ErrorAction Stop | Out-Null
    $response = '{payload}' | & curl.exe --silent --show-error --fail --max-time 30 --proto '={protocol}' -H 'Content-Type: application/json' -H 'User-Agent: MoodleMobile 4.5.0' --data-binary '@-' '{endpoint}'
    if ($LASTEXITCODE -ne 0) {{ throw 'Network or HTTP error. No token copied.' }}
    $raw = ($response -join "`n").Trim()
    if (-not $raw.StartsWith('[')) {{ throw 'Unexpected Moodle response. No token copied.' }}
    $items = @(ConvertFrom-Json -InputObject $raw)
    if ($items.Count -ne 1) {{ throw 'Unexpected Moodle response. No token copied.' }}
    if ($items[0].error) {{
      switch ($items[0].exception.errorcode) {{
        'ipmismatch' {{ $failure = 'Use the network that generated the QR.'; throw 'QR rejected' }}
        'invalidkey' {{ $failure = 'QR expired or used. Generate a fresh QR.'; throw 'QR rejected' }}
        'apprequired' {{ $failure = 'Moodle rejected the app identification header.'; throw 'QR rejected' }}
        'qrcodedisabled' {{ $failure = 'Moodle QR login is disabled.'; throw 'QR rejected' }}
        default {{ $failure = 'Moodle rejected the QR. No token copied.'; throw 'QR rejected' }}
      }}
    }}
    $token = $items[0].data.token
    if ($token -isnot [string] -or $token -cnotmatch '^[A-Za-z0-9]{{16,256}}$') {{ throw 'Invalid token response. No token copied.' }}
    Set-Clipboard -Value $token
    Write-Host 'Moodle token copied. Paste it into LAMB.'
  }} catch {{
    Write-Host $failure
  }} finally {{ $token = $null; $response = $null; $items = $null; $raw = $null }}
}}
'''
