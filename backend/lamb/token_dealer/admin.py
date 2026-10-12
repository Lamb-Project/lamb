"""Organization settings and usage overview of token-dealer, for the org-admin screen.

Two layers (Marc, 2026-10-11): the organization admin owns the policy (on/off, pool and/or
per-student allowances, the default teacher allowance and its exceptions, models, slot length,
timetable zone); the system admin owns the implementation (which proxy, its admin key, the public
URL students paste into their tools). Organization admins never see the proxy admin key.
"""
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .settings import POLICIES, SettingsError, from_org_config

POLICY_FIELDS = ('enabled', 'policy', 'teacher_allowance_tokens', 'teacher_allowances', 'models',
                 'slot_minutes', 'timezone')
INFRA_FIELDS = ('proxy_url', 'public_url', 'proxy_admin_key')


def settings_view(config, is_system_admin, env=os.environ):
    """What the org-admin screen shows. Infrastructure is visible to the system admin only; the
    admin key is never returned, only whether one is set."""
    raw = (config or {}).get('token_dealer') or {}
    s = from_org_config(config, env)
    view = {
        'enabled': s.enabled,
        'policy': s.policy,
        'teacher_allowance_tokens': s.teacher_allowance_tokens,
        'teacher_allowances': dict(s.teacher_allowances),
        'models': list(s.models),
        'slot_minutes': s.slot_minutes,
        'timezone': s.timezone,
        'public_url': s.public_url,
        'proxy_configured': bool(s.proxy_url and s.proxy_admin_key),
        'can_edit_infrastructure': bool(is_system_admin),
    }
    if is_system_admin:
        view['proxy_url'] = s.proxy_url
        view['proxy_admin_key_set'] = bool(s.proxy_admin_key)
        view['infrastructure_from_environment'] = {
            'proxy_url': not raw.get('proxy_url') and bool(env.get('TOKEN_DEALER_PROXY_URL')),
            'public_url': not raw.get('public_url') and bool(env.get('TOKEN_DEALER_PUBLIC_URL')),
            'proxy_admin_key': not raw.get('proxy_admin_key') and bool(env.get('TOKEN_DEALER_PROXY_ADMIN_KEY')),
        }
    return view


def _tokens(name, v, allow_none=True):
    if v is None or v == '':
        if allow_none:
            return None
        raise SettingsError(f'{name} is required')
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise SettingsError(f'{name} must be a whole number of tokens') from None
    if n < 0:
        raise SettingsError(f'{name} cannot be negative')
    return n


def apply_update(config, body, is_system_admin, env=os.environ):
    """Return a new organization config with body applied to config['token_dealer'].
    Raises PermissionError for infrastructure fields from an org admin, SettingsError otherwise."""
    if not isinstance(body, dict):
        raise SettingsError('settings must be an object')
    unknown = set(body) - set(POLICY_FIELDS) - set(INFRA_FIELDS)
    if unknown:
        raise SettingsError(f'unknown fields: {", ".join(sorted(unknown))}')
    infra = [k for k in INFRA_FIELDS if k in body]
    if infra and not is_system_admin:
        raise PermissionError('only the system administrator sets the proxy connection')
    current = dict((config or {}).get('token_dealer') or {})
    new = dict(current)
    if 'enabled' in body:
        new['enabled'] = bool(body['enabled'])
    if 'policy' in body:
        if body['policy'] not in POLICIES:
            raise SettingsError(f'policy must be one of {", ".join(POLICIES)}')
        new['policy'] = body['policy']
    if 'teacher_allowance_tokens' in body:
        new['teacher_allowance_tokens'] = _tokens('the default teacher allowance', body['teacher_allowance_tokens'])
    if 'teacher_allowances' in body:
        raw = body['teacher_allowances'] or {}
        if not isinstance(raw, dict):
            raise SettingsError('teacher exceptions must map an email to a number of tokens')
        allowances = {}
        for email, v in raw.items():
            email = str(email).strip().lower()
            if '@' not in email:
                raise SettingsError(f'"{email}" is not an email address')
            allowances[email] = _tokens(f'the allowance of {email}', v, allow_none=False)
        new['teacher_allowances'] = allowances
    if 'models' in body:
        models = body['models'] or []
        if not isinstance(models, list) or not all(isinstance(m, str) and m.strip() for m in models):
            raise SettingsError('models must be a list of model names')
        new['models'] = list(dict.fromkeys(m.strip() for m in models))
    if 'slot_minutes' in body:
        new['slot_minutes'] = _tokens('the slot length', body['slot_minutes'], allow_none=False)
    if 'timezone' in body:
        try:
            ZoneInfo(str(body['timezone']))
        except (ZoneInfoNotFoundError, ValueError):
            raise SettingsError(f'unknown time zone "{body["timezone"]}"') from None
        new['timezone'] = str(body['timezone'])
    for k in INFRA_FIELDS:
        if k in body:
            v = (body[k] or '').strip()
            if k == 'proxy_admin_key' and not v:
                continue          # empty = keep the stored key
            if v:
                new[k] = v
            else:
                new.pop(k, None)  # fall back to the deployment's environment
    out = dict(config or {})
    out['token_dealer'] = new
    s = from_org_config(out, env)   # same validation the runtime applies
    if s.enabled:
        if not (s.proxy_url and s.proxy_admin_key):
            raise SettingsError('LLM access cannot be enabled before the system administrator connects a proxy')
        if not s.models:
            raise SettingsError('choose at least one model before enabling LLM access')
    return out


def usage_overview(service, ledger, organization_id, settings):
    """Per teacher: allowance, tokens committed to activities, tokens used; per activity below."""
    teachers = {}
    for a in service.store.list_activities(organization_id=organization_id):
        email = (a.get('owner_email') or '').lower()
        t = teachers.setdefault(email, {'email': email, 'name': a.get('owner_name') or email,
                                        'allowance': settings.allowance_for(email),
                                        'allocated': service.allocated(organization_id, email),
                                        'used': 0, 'activities': []})
        totals = ledger.totals(activity_id=a['id'])
        keys = service.store.list_keys(activity_id=a['id'])
        used = sum(v['tokens'] for v in totals.values())
        t['used'] += used
        t['activities'].append({
            'id': a['id'], 'name': a.get('activity_name') or f"Activity {a['id']}",
            'course': a.get('context_title') or '', 'override': a.get('override'),
            'pool_tokens': a.get('pool_tokens'), 'slot_tokens': a.get('slot_tokens'),
            'total_tokens': a.get('total_tokens'), 'students': len(keys), 'used': used,
            'refused': sum(v['requests_refused'] for v in totals.values()),
        })
    return sorted(teachers.values(), key=lambda t: t['email'])
