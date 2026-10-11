"""Organization settings for token-dealer, read from the organization's config JSON under
"token_dealer". The organization admin chooses the policy; teachers work inside it.

    "token_dealer": {
      "enabled": true,
      "proxy_url": "http://litellm:4000",          # admin API, internal
      "proxy_admin_key": "sk-...",                  # never shown to creators or students
      "public_url": "https://llm.example.edu/v1",   # what students paste into their tools
      "policy": "pool" | "per_student" | "both",
      "teacher_allowance_tokens": 2000000,          # default per teacher; null = no limit
      "teacher_allowances": {"teacher@example.edu": 5000000},
      "models": ["course-model"],                   # public names the proxy serves
      "slot_minutes": 10,
      "timezone": "Europe/Madrid"                  # timetable zone of new activities
    }

URL and admin key fall back to TOKEN_DEALER_PROXY_URL, TOKEN_DEALER_PROXY_ADMIN_KEY and
TOKEN_DEALER_PUBLIC_URL, so one proxy can serve every organization of a deployment.
"""
import os
from dataclasses import dataclass, field

POLICIES = ('pool', 'per_student', 'both')


class SettingsError(ValueError):
    pass


@dataclass
class Settings:
    enabled: bool = False
    proxy_url: str = ''
    proxy_admin_key: str = field(default='', repr=False)
    public_url: str = ''
    policy: str = 'per_student'
    teacher_allowance_tokens: int | None = None
    teacher_allowances: dict = field(default_factory=dict)
    models: list = field(default_factory=list)
    slot_minutes: int = 10
    timezone: str = 'UTC'

    def allowance_for(self, email):
        """Token allowance of one teacher, or None for no limit."""
        if email and email.lower() in self.teacher_allowances:
            return self.teacher_allowances[email.lower()]
        return self.teacher_allowance_tokens


def from_org_config(config, env=os.environ):
    raw = (config or {}).get('token_dealer') or {}
    policy = raw.get('policy', 'per_student')
    if policy not in POLICIES:
        raise SettingsError(f'policy must be one of {POLICIES}')
    slot = int(raw.get('slot_minutes', 10))
    if slot <= 0 or 60 % slot:
        raise SettingsError('slot_minutes must divide 60')
    allowances = {k.lower(): int(v) for k, v in (raw.get('teacher_allowances') or {}).items()}
    default = raw.get('teacher_allowance_tokens')
    proxy_url = (raw.get('proxy_url') or env.get('TOKEN_DEALER_PROXY_URL', '')).rstrip('/')
    return Settings(
        enabled=bool(raw.get('enabled', False)),
        proxy_url=proxy_url,
        proxy_admin_key=raw.get('proxy_admin_key') or env.get('TOKEN_DEALER_PROXY_ADMIN_KEY', ''),
        public_url=(raw.get('public_url') or env.get('TOKEN_DEALER_PUBLIC_URL') or proxy_url).rstrip('/'),
        policy=policy,
        teacher_allowance_tokens=None if default is None else int(default),
        teacher_allowances=allowances,
        models=list(raw.get('models') or []),
        slot_minutes=slot,
        timezone=raw.get('timezone') or 'UTC',
    )


def check_limits(policy, pool_tokens, slot_tokens, total_tokens):
    """Validate an activity's limits against the organization policy; raise SettingsError if it
    forbids the combination."""
    for name, v in (('pool_tokens', pool_tokens), ('slot_tokens', slot_tokens), ('total_tokens', total_tokens)):
        if v is not None and int(v) <= 0:
            raise SettingsError(f'{name} must be positive')
    per_student = slot_tokens is not None or total_tokens is not None
    if policy == 'pool' and pool_tokens is None:
        raise SettingsError('this organization gives each activity a pool: set pool_tokens')
    if policy == 'per_student':
        if pool_tokens is not None:
            raise SettingsError('this organization uses per-student allowances only: no pool')
        if not per_student:
            raise SettingsError('set a slot or a total allowance per student')
    if policy == 'both' and (pool_tokens is None or not per_student):
        raise SettingsError('this organization requires a pool and a per-student allowance')


def pool_sizing_warning(pool_tokens, slot_tokens, students):
    """Rehearsal finding (2026-10-11): a pool protects nobody unless the per-student slot caps add
    up to less than the pool's share per slot. Returns a warning string or None."""
    if not pool_tokens or not slot_tokens or not students:
        return None
    demand = slot_tokens * students
    if demand > pool_tokens:
        return (f'{students} students × {slot_tokens} tokens per slot = {demand} tokens, more than the '
                f'pool of {pool_tokens}: the first heavy users can exhaust it for everyone')
    return None
