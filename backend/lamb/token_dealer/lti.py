"""LTI pages of an "LLM access" activity: instructor management and the student key page.

lamb-0.8: mounted as the llm_access module's router at /lamb/v1/modules/llm_access. Setup happens
in the module-chat setup app like every activity type; entry is always the LTI launch, which hands
over a short-lived signed token; these pages never trust form fields for identity.
"""
import os
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from lamb import auth as lamb_auth
from lamb.logging_config import get_logger

from . import schedule as sched
from . import wiring
from .proxy_client import ProxyError
from .service import AllocationError, KeyExists
from .settings import SettingsError

logger = get_logger(__name__, component="TOKEN_DEALER")
router = APIRouter()
templates = Jinja2Templates(directory=[os.path.abspath("lamb/templates")])

SCOPE = 'llm_access'
PREFIX = '/lamb/v1/modules/llm_access'
NOTICE_VERSION = '2026-10-11'
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def make_token(data, ttl=1800):
    return lamb_auth.create_token({**data, 'scope': SCOPE}, expires_delta=timedelta(seconds=ttl))


def read_token(token, kind):
    data = lamb_auth.decode_token(token) if token else None
    if not data or data.get('scope') != SCOPE or data.get('type') != kind:
        return None
    return data


def expired():
    return HTMLResponse('<h2>Session expired.</h2><p>Open the activity from your course again.</p>', status_code=403)


def launch_redirect(public_base, activity, roles_is_instructor, lms_user_id, email, name):
    """Called by lti_router for a link that is an LLM-access activity."""
    if roles_is_instructor:
        t = make_token({'type': 'manage', 'activity_id': activity['id'], 'lms_user_id': lms_user_id, 'email': email})
        return RedirectResponse(f'{public_base}{PREFIX}/manage?token={t}', status_code=303)
    t = make_token({'type': 'student', 'activity_id': activity['id'], 'lms_user_id': lms_user_id, 'email': email, 'name': name})
    return RedirectResponse(f'{public_base}{PREFIX}/student?token={t}', status_code=303)


def _state(a, now=None):
    now = now or datetime.now(timezone.utc)
    is_open = sched.is_open(a['schedule'], a['override'], now)
    change = sched.next_change(a['schedule'], a['override'], now)
    tz = a['schedule'].get('timezone') or 'UTC'
    from zoneinfo import ZoneInfo
    when = change.astimezone(ZoneInfo(tz)).strftime('%a %d %b %H:%M') if change else None
    return {'open': is_open, 'next_change': when, 'timezone': tz}


def _usage(activity_id, slot_minutes):
    led = wiring.ledger()
    slot_start = int(time.time()) // (slot_minutes * 60) * (slot_minutes * 60)
    return led.totals(activity_id=activity_id), led.totals(activity_id=activity_id, since=slot_start)


# ── instructor: limits and timetable (from the management page) ──
def _int(form, name):
    v = (form.get(name) or '').strip()
    return int(v) if v else None


@router.post('/configure')
async def configure(request: Request):
    form = await request.form()
    token = form.get('token', '')
    data = read_token(token, 'manage')
    if not data:
        return expired()
    svc = wiring.service()
    a = svc.store.get_activity(data['activity_id'])
    mode = form.get('mode', 'always')
    schedule = {'timezone': form.get('timezone') or 'UTC', 'mode': mode,
                'from': form.get('from') or None, 'until': form.get('until') or None}
    if mode == 'weekly':
        schedule['weekly'] = [{'days': [int(d) for d in form.getlist('days')], 'start': form.get('start'), 'end': form.get('end')}]
    try:
        svc.configure_activity(a['organization_id'], a['resource_link_id'], a['owner_email'], form.getlist('models'), schedule,
                               pool_tokens=_int(form, 'pool_tokens'), slot_tokens=_int(form, 'slot_tokens'),
                               total_tokens=_int(form, 'total_tokens'), owner_name=a['owner_name'],
                               context_id=a['context_id'], context_title=a['context_title'], activity_name=a['activity_name'])
    except (SettingsError, AllocationError, sched.ScheduleError, ValueError) as e:
        return RedirectResponse(f"manage?token={token}&error={e}", status_code=303)
    except ProxyError as e:
        logger.error(f'proxy refused activity configuration: {e}')
        return HTMLResponse('<h2>The LLM gateway is not reachable</h2><p>Nothing was changed. Try again later.</p>', status_code=503)
    return RedirectResponse(f'manage?token={token}', status_code=303)


# ── instructor: manage ─────────────────────────────────────────────────
@router.get('/manage')
async def manage_page(request: Request, token: str = ''):
    data = read_token(token, 'manage')
    if not data:
        return expired()
    svc = wiring.service()
    a = svc.store.get_activity(data['activity_id'])
    s = wiring.settings_for(a['organization_id'])
    totals, this_slot = _usage(a['id'], s.slot_minutes)
    keys = svc.store.list_keys(activity_id=a['id'], statuses=('active', 'blocked'))
    rows = [{**k, 'total': totals.get(k['id'], {}), 'slot': this_slot.get(k['id'], {})} for k in keys]
    return templates.TemplateResponse('llm_access_manage.html', {
        'request': request, 'token': token, 'a': a, 'state': _state(a), 'rows': rows, 'policy': s.policy,
        'warnings': svc.warnings(a['id']), 'endpoint': s.public_url, 'days': list(enumerate(DAYS)),
        'used': sum(v.get('tokens', 0) for v in totals.values()), 'models': s.models,
        'slot_minutes': s.slot_minutes, 'error': request.query_params.get('error')})


@router.post('/override')
async def override(request: Request):
    form = await request.form()
    data = read_token(form.get('token', ''), 'manage')
    if not data:
        return expired()
    wiring.service().set_override(data['activity_id'], form.get('override', 'auto'))
    return RedirectResponse(f"manage?token={form.get('token')}", status_code=303)


@router.post('/student-action')
async def student_action(request: Request):
    form = await request.form()
    data = read_token(form.get('token', ''), 'manage')
    if not data:
        return expired()
    svc = wiring.service()
    k = svc.store.get_key(int(form.get('key_id', 0)))
    if not k or k['activity_id'] != data['activity_id']:
        return HTMLResponse('<h2>Error</h2><p>Unknown student key.</p>', status_code=404)
    action = form.get('action')
    if action == 'block':
        svc.block_student(k['id'])
    elif action == 'unblock':
        svc.unblock_student(k['id'])
    elif action == 'revoke':
        svc.revoke_key(k['id'])
    return RedirectResponse(f"manage?token={form.get('token')}", status_code=303)


# ── student ────────────────────────────────────────────────────────────
def _student_context(request, token, data, secret=None, error=None):
    svc = wiring.service()
    a = svc.store.get_activity(data['activity_id'])
    s = wiring.settings_for(a['organization_id'])
    key = svc.store.get_current_key(a['id'], data['lms_user_id'])
    usage = None
    if key:
        totals, this_slot = _usage(a['id'], s.slot_minutes)
        usage = {'total': totals.get(key['id'], {}).get('tokens', 0), 'slot': this_slot.get(key['id'], {}).get('tokens', 0)}
    endpoint = s.public_url
    return templates.TemplateResponse('llm_access_student.html', {
        'request': request, 'token': token, 'a': a, 'state': _state(a), 'key': key, 'secret': secret, 'usage': usage,
        'endpoint': endpoint, 'anthropic_base': endpoint[:-3] if endpoint.endswith('/v1') else endpoint,
        'model': (a['models'] or [''])[0], 'notice_version': NOTICE_VERSION, 'slot_minutes': s.slot_minutes, 'error': error})


@router.get('/student')
async def student_page(request: Request, token: str = ''):
    data = read_token(token, 'student')
    if not data:
        return expired()
    return _student_context(request, token, data)


@router.post('/issue')
async def issue(request: Request):
    form = await request.form()
    token = form.get('token', '')
    data = read_token(token, 'student')
    if not data:
        return expired()
    if form.get('accept') != NOTICE_VERSION:
        return _student_context(request, token, data, error='Read and accept the notice first.')
    svc = wiring.service()
    try:
        if form.get('rotate') == '1':
            issued = svc.rotate_key(data['activity_id'], data['lms_user_id'], data.get('email'), data.get('name'), NOTICE_VERSION)
        else:
            issued = svc.issue_key(data['activity_id'], data['lms_user_id'], data.get('email'), data.get('name'), NOTICE_VERSION)
    except KeyExists:
        return _student_context(request, token, data, error='You already have a key. Replace it if you lost it.')
    except (AllocationError, SettingsError) as e:
        return _student_context(request, token, data, error=str(e))
    except ProxyError as e:
        logger.error(f'proxy refused key issuance: {e}')
        return _student_context(request, token, data, error='The LLM gateway is not reachable. Try again later.')
    return _student_context(request, token, data, secret=issued['secret'])
