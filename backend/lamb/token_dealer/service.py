"""What teachers and students do: configure an LLM-access activity, get a key, rotate it, lose it.

Every change goes to the proxy first and to LAMB's records second, and is undone in the proxy
if recording fails, so the two never disagree about what exists.
"""
import hashlib
import secrets
from datetime import datetime, timezone

from . import schedule as sched
from .proxy_client import ProxyError
from .settings import SettingsError, check_limits, pool_sizing_warning
from .units import tokens_to_units


class AllocationError(ValueError):
    """The teacher's token allowance does not cover this."""


class KeyExists(ValueError):
    """The student already holds a key in this activity; the secret was shown once. Rotate instead."""


def user_ref(organization_id, lms_user_id):
    """The opaque reference the proxy sees instead of the student."""
    return 'lamb-u-' + hashlib.sha256(f'{organization_id}:{lms_user_id}'.encode()).hexdigest()[:16]


class TokenDealerService:
    def __init__(self, store, settings_for, client_for):
        """settings_for(org_id) -> Settings; client_for(org_id) -> ProxyClient."""
        self.store, self.settings_for, self.client_for = store, settings_for, client_for

    # ── allocation ─────────────────────────────────────────────────────
    def allocated(self, organization_id, owner_email, exclude_activity=None):
        """Tokens a teacher has committed: activity pools, plus per-student totals of issued keys
        in activities without a pool. Slot-only keys commit nothing up front."""
        total = 0
        for a in self.store.list_activities(organization_id=organization_id, owner_email=owner_email):
            if a['id'] == exclude_activity:
                continue
            if a['pool_tokens']:
                total += a['pool_tokens']
            elif a['total_tokens']:
                total += a['total_tokens'] * len(self.store.list_keys(activity_id=a['id']))
        return total

    def _check_allocation(self, settings, organization_id, owner_email, extra, exclude_activity=None):
        allowance = settings.allowance_for(owner_email)
        if allowance is None:
            return
        used = self.allocated(organization_id, owner_email, exclude_activity)
        if used + extra > allowance:
            raise AllocationError(f'this needs {extra} tokens; the teacher has {allowance - used} of {allowance} left')

    # ── activities ─────────────────────────────────────────────────────
    def configure_activity(self, organization_id, resource_link_id, owner_email, models, schedule,
                           pool_tokens=None, slot_tokens=None, total_tokens=None, owner_name=None,
                           context_id=None, context_title=None, activity_name=None):
        """Create the activity, or update it if this LTI resource link already has one. Returns
        (activity_id, warnings)."""
        settings = self.settings_for(organization_id)
        if not settings.enabled:
            raise SettingsError('LLM access is not enabled for this organization')
        check_limits(settings.policy, pool_tokens, slot_tokens, total_tokens)
        bad = [m for m in models if m not in settings.models]
        if not models or bad:
            raise SettingsError(f'models must be chosen from {settings.models}')
        schedule = sched.validate(schedule, settings.slot_minutes)
        existing = self.store.get_activity_by_resource_link(resource_link_id)
        if existing and existing['organization_id'] != organization_id:
            raise SettingsError('this LTI link belongs to another organization')
        self._check_allocation(settings, organization_id, owner_email, pool_tokens or 0,
                               exclude_activity=existing['id'] if existing else None)
        client = self.client_for(organization_id)
        fields = dict(models=models, schedule=schedule, pool_tokens=pool_tokens, slot_tokens=slot_tokens,
                      total_tokens=total_tokens, owner_email=owner_email, owner_name=owner_name,
                      context_id=context_id, context_title=context_title, activity_name=activity_name)
        if existing is None:
            team_id = client.create_team(f'lamb-{organization_id}-{resource_link_id}-{secrets.token_hex(3)}', models,
                                         tokens_to_units(pool_tokens),
                                         {'lamb_org': organization_id, 'lamb_resource_link': resource_link_id})
            try:
                activity_id = self.store.create_activity(resource_link_id=resource_link_id, organization_id=organization_id,
                                                         proxy_team_id=team_id, **fields)
            except Exception:
                client.delete_team(team_id)
                raise
        else:
            activity_id = existing['id']
            client.update_team(existing['proxy_team_id'], models=models, max_budget=tokens_to_units(pool_tokens))
            self.store.update_activity(activity_id, **fields)
            if (existing['slot_tokens'], existing['total_tokens'], existing['models']) != (slot_tokens, total_tokens, models):
                for k in self.store.list_keys(activity_id=activity_id):
                    client.update_key(k['proxy_token'], models=models, max_budget=tokens_to_units(total_tokens),
                                      budget_limits=[{'budget_duration': f'{settings.slot_minutes}m',
                                                      'max_budget': tokens_to_units(slot_tokens)}] if slot_tokens else [])
        return activity_id, self.warnings(activity_id)

    def warnings(self, activity_id):
        a = self.store.get_activity(activity_id)
        w = pool_sizing_warning(a['pool_tokens'], a['slot_tokens'], len(self.store.list_keys(activity_id=activity_id)))
        return [w] if w else []

    def set_override(self, activity_id, override):
        if override not in sched.OVERRIDES:
            raise SettingsError(f'override must be one of {sched.OVERRIDES}')
        self.store.update_activity(activity_id, override=override)   # the worker applies it within one cycle

    # ── keys ───────────────────────────────────────────────────────────
    def issue_key(self, activity_id, lms_user_id, user_email=None, user_name=None, notice_version=None, now=None):
        """Issue the student's key. Returns {'key_id', 'secret', 'prefix', 'endpoint'}; the secret is
        not stored anywhere and cannot be shown again."""
        a = self.store.get_activity(activity_id)
        if a is None or a['status'] != 'active':
            raise SettingsError('this activity is not active')
        if self.store.get_current_key(activity_id, lms_user_id):
            raise KeyExists('a key was already issued; rotate it to get a new secret')
        settings = self.settings_for(a['organization_id'])
        if a['total_tokens'] and not a['pool_tokens']:
            self._check_allocation(settings, a['organization_id'], a['owner_email'], a['total_tokens'])
        ref = user_ref(a['organization_id'], lms_user_id)
        end = sched.end_of_validity(a['schedule'])
        now = now or datetime.now(timezone.utc)
        duration = f'{max(1, int((end - now).total_seconds() // 60))}m' if end else None
        client = self.client_for(a['organization_id'])
        # The proxy wants key aliases unique across all keys it has ever kept; a suffix keeps a
        # re-issue unique even when an old key could not be deleted.
        alias = f"lamb-{a['organization_id']}-{a['resource_link_id']}/{ref}/{secrets.token_hex(3)}"
        k = client.generate_key(a['models'], ref, a['proxy_team_id'], alias,
                                {'lamb_org': a['organization_id'], 'lamb_activity': activity_id},
                                tokens_to_units(a['total_tokens']), tokens_to_units(a['slot_tokens']),
                                f'{settings.slot_minutes}m', duration)
        try:
            if not sched.is_open(a['schedule'], a['override'], now):
                client.block_key(k['token'])          # closed now: never usable before the worker's next cycle
            key_id = self.store.create_key(activity_id, a['organization_id'], lms_user_id, ref, k['key'][:7], k['token'],
                                           user_email, user_name, int(end.timestamp()) if end else None, notice_version)
        except Exception:
            client.delete_keys([k['token']])
            raise
        self.store.record_applied(f'key:{key_id}', 'open' if sched.is_open(a['schedule'], a['override'], now) else 'closed')
        return {'key_id': key_id, 'secret': k['key'], 'prefix': k['key'][:7], 'endpoint': settings.public_url}

    def revoke_key(self, key_id, reason='instructor'):
        k = self.store.get_key(key_id)
        if k is None or k['status'] == 'revoked':
            return
        try:
            self.client_for(k['organization_id']).delete_keys([k['proxy_token']])
        except ProxyError as e:
            if e.status != 404:
                raise
        self.store.set_key_status(key_id, 'revoked', reason)

    def rotate_key(self, activity_id, lms_user_id, user_email=None, user_name=None, notice_version=None):
        old = self.store.get_current_key(activity_id, lms_user_id)
        if old:
            self.revoke_key(old['id'], 'rotated')
        return self.issue_key(activity_id, lms_user_id, user_email, user_name, notice_version)

    def block_student(self, key_id, reason='instructor'):
        """Keep the key but refuse it (the worker closes it in the proxy)."""
        self.store.set_key_status(key_id, 'blocked', reason)

    def unblock_student(self, key_id):
        self.store.set_key_status(key_id, 'active', None)
