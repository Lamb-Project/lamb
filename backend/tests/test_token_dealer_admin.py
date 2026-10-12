"""Org-admin layer of token-dealer: policy belongs to the org admin, the proxy connection to the
system admin; the admin key is never shown; usage overview per teacher."""
import pytest

from lamb.token_dealer.admin import apply_update, settings_view, usage_overview
from lamb.token_dealer.ledger import UsageLedger
from lamb.token_dealer.settings import SettingsError

from tests.test_token_dealer import MONDAY_1600_MADRID, SETTINGS, WEEKLY, log, store, svc  # noqa: F401

CONNECTED = {'token_dealer': {'proxy_url': 'http://proxy:4000', 'proxy_admin_key': 'sk-master',
                              'public_url': 'https://llm.x/v1', 'models': ['course-model']}}


def test_org_admin_sees_policy_but_not_the_proxy_connection():
    view = settings_view(CONNECTED, is_system_admin=False, env={})
    assert view['proxy_configured'] and view['public_url'] == 'https://llm.x/v1'
    assert 'proxy_url' not in view and 'proxy_admin_key' not in str(view) and 'sk-master' not in str(view)
    sysview = settings_view(CONNECTED, is_system_admin=True, env={})
    assert sysview['proxy_url'] == 'http://proxy:4000' and sysview['proxy_admin_key_set'] is True
    assert 'sk-master' not in str(sysview)


def test_environment_fallback_is_reported_to_the_system_admin():
    env = {'TOKEN_DEALER_PROXY_URL': 'http://litellm:4000', 'TOKEN_DEALER_PROXY_ADMIN_KEY': 'sk-env'}
    view = settings_view({}, is_system_admin=True, env=env)
    assert view['proxy_configured'] and view['infrastructure_from_environment']['proxy_url']
    assert view['infrastructure_from_environment']['proxy_admin_key'] and not view['enabled']


def test_org_admin_cannot_touch_the_proxy_connection():
    with pytest.raises(PermissionError):
        apply_update(CONNECTED, {'proxy_url': 'http://evil'}, is_system_admin=False, env={})
    with pytest.raises(PermissionError):
        apply_update(CONNECTED, {'proxy_admin_key': 'x'}, is_system_admin=False, env={})


def test_org_admin_sets_policy_allowances_and_enables():
    out = apply_update(CONNECTED, {'enabled': True, 'policy': 'both', 'teacher_allowance_tokens': '500000',
                                   'teacher_allowances': {' Big.Course@X.edu ': 2000000}, 'models': ['course-model', 'course-model'],
                                   'slot_minutes': 10, 'timezone': 'Europe/Madrid'}, is_system_admin=False, env={})
    td = out['token_dealer']
    assert td['enabled'] and td['policy'] == 'both' and td['teacher_allowance_tokens'] == 500000
    assert td['teacher_allowances'] == {'big.course@x.edu': 2000000} and td['models'] == ['course-model']
    assert td['proxy_admin_key'] == 'sk-master'          # untouched
    assert CONNECTED['token_dealer'].get('enabled') is None   # input not mutated


@pytest.mark.parametrize('body, message', [
    ({'policy': 'unlimited'}, 'policy'),
    ({'teacher_allowance_tokens': -5}, 'negative'),
    ({'teacher_allowance_tokens': 'lots'}, 'whole number'),
    ({'teacher_allowances': {'nobody': 10}}, 'email'),
    ({'slot_minutes': 7}, 'divide 60'),
    ({'timezone': 'Mars/Olympus'}, 'time zone'),
    ({'models': ['']}, 'model'),
    ({'colour': 'blue'}, 'unknown'),
])
def test_invalid_policy_is_refused(body, message):
    with pytest.raises(SettingsError, match=message):
        apply_update(CONNECTED, body, is_system_admin=True, env={})


def test_cannot_enable_without_a_proxy_or_models():
    with pytest.raises(SettingsError, match='proxy'):
        apply_update({}, {'enabled': True, 'models': ['m']}, is_system_admin=False, env={})
    with pytest.raises(SettingsError, match='model'):
        apply_update({'token_dealer': {**CONNECTED['token_dealer'], 'models': []}}, {'enabled': True},
                     is_system_admin=False, env={})


def test_system_admin_connects_a_proxy_and_an_empty_key_keeps_the_stored_one():
    out = apply_update({}, {'proxy_url': 'http://p:4000', 'proxy_admin_key': 'sk-1', 'public_url': 'https://llm/v1'},
                       is_system_admin=True, env={})
    out = apply_update(out, {'proxy_admin_key': '', 'public_url': ''}, is_system_admin=True, env={})
    assert out['token_dealer']['proxy_admin_key'] == 'sk-1' and 'public_url' not in out['token_dealer']


def test_usage_overview_per_teacher(svc, tmp_path):
    service, proxy = svc
    a1, _ = service.configure_activity(1, 'rl-1', 't@x.edu', ['m'], WEEKLY, slot_tokens=4000, total_tokens=7000,
                                       activity_name='Lab', context_title='Databases')
    proxy.create_team = lambda *a, **kw: 'team-2'        # the fake hands out one team id
    service.configure_activity(1, 'rl-2', 'u@x.edu', ['m'], WEEKLY, slot_tokens=1000, total_tokens=2000)
    issued = service.issue_key(a1, 's1', now=MONDAY_1600_MADRID)
    key = service.store.get_current_key(a1, 's1')
    ledger = UsageLedger(str(tmp_path / 'usage.db'))
    ledger.record([log('r1', key['proxy_token'], p=100, c=50), log('r2', key['proxy_token'], status='failure', p=0, c=0)],
                  service.store.key_index())
    rows = usage_overview(service, ledger, 1, SETTINGS)
    assert [t['email'] for t in rows] == ['t@x.edu', 'u@x.edu']
    t = rows[0]
    assert t['allowance'] == 20000 and t['allocated'] == 7000 and t['used'] == 150 and issued['secret']
    assert t['activities'][0]['name'] == 'Lab' and t['activities'][0]['students'] == 1
    assert t['activities'][0]['refused'] == 1 and rows[1]['used'] == 0
