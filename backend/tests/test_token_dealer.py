"""token-dealer control plane (#533): timetables, policy, records, usage ledger, proxy client,
service and worker. No network: the proxy is a fake or an httpx mock transport."""
import json
import sqlite3
from datetime import datetime, timezone

import httpx
import pytest

from lamb.migrations import MigrationRunner
from lamb.token_dealer import schedule as sched
from lamb.token_dealer.ledger import UsageLedger
from lamb.token_dealer.proxy_client import ProxyClient, ProxyError, ProxyUnavailable
from lamb.token_dealer.service import AllocationError, KeyExists, TokenDealerService, user_ref
from lamb.token_dealer.settings import Settings, SettingsError, check_limits, from_org_config, pool_sizing_warning
from lamb.token_dealer.store import TokenDealerStore
from lamb.token_dealer.units import tokens_to_units, units_to_tokens
from lamb.token_dealer.worker import Worker

UTC = timezone.utc
WEEKLY = {'timezone': 'Europe/Madrid', 'mode': 'weekly', 'weekly': [{'days': [0], 'start': '15:00', 'end': '17:00'}]}
MONDAY_1600_MADRID = datetime(2026, 10, 12, 14, 0, tzinfo=UTC)   # 16:00 CEST
MONDAY_1700_MADRID = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)


# ── units, schedule, settings ──────────────────────────────────────────
def test_units_round_trip():
    assert tokens_to_units(4000) == 0.004 and units_to_tokens(0.004) == 4000 and tokens_to_units(None) is None


def test_weekly_schedule_in_local_time():
    s = sched.validate(WEEKLY)
    assert sched.is_open(s, 'auto', MONDAY_1600_MADRID)
    assert not sched.is_open(s, 'auto', MONDAY_1700_MADRID)          # end is exclusive
    assert not sched.is_open(s, 'auto', datetime(2026, 10, 13, 14, 0, tzinfo=UTC))
    assert sched.is_open(s, 'open', MONDAY_1700_MADRID) and not sched.is_open(s, 'closed', MONDAY_1600_MADRID)
    assert sched.next_change(s, 'auto', MONDAY_1600_MADRID) == MONDAY_1700_MADRID


def test_date_bounds_and_end_of_validity():
    s = sched.validate({'timezone': 'Europe/Madrid', 'mode': 'always', 'from': '2026-10-12', 'until': '2026-10-12'})
    assert sched.is_open(s, 'auto', MONDAY_1600_MADRID)
    assert not sched.is_open(s, 'auto', datetime(2026, 10, 12, 22, 30, tzinfo=UTC))   # 00:30 on the 13th, local
    assert sched.end_of_validity(s) == datetime(2026, 10, 12, 22, 0, tzinfo=UTC)


@pytest.mark.parametrize('bad', [
    {'mode': 'weekly'}, {'mode': 'weekly', 'weekly': [{'days': [0], 'start': '15:05', 'end': '17:00'}]},
    {'mode': 'weekly', 'weekly': [{'days': [7], 'start': '15:00', 'end': '17:00'}]},
    {'mode': 'weekly', 'weekly': [{'days': [0], 'start': '17:00', 'end': '15:00'}]},
    {'timezone': 'Mars/Olympus'}, {'from': '2026-12-01', 'until': '2026-11-01'}, {'mode': 'sometimes'}])
def test_invalid_schedules_are_refused(bad):
    with pytest.raises(sched.ScheduleError):
        sched.validate(bad)


def test_settings_from_org_config_with_env_fallback():
    s = from_org_config({'token_dealer': {'enabled': True, 'policy': 'both', 'models': ['m'],
                                          'teacher_allowance_tokens': 1000, 'teacher_allowances': {'T@x.edu': 5}}},
                        env={'TOKEN_DEALER_PROXY_URL': 'http://proxy:4000/', 'TOKEN_DEALER_PROXY_ADMIN_KEY': 'sk-admin'})
    assert (s.proxy_url, s.public_url, s.proxy_admin_key) == ('http://proxy:4000', 'http://proxy:4000', 'sk-admin')
    assert s.allowance_for('t@x.edu') == 5 and s.allowance_for('other@x.edu') == 1000
    assert 'sk-admin' not in repr(s)
    with pytest.raises(SettingsError):
        from_org_config({'token_dealer': {'policy': 'anarchy'}})


@pytest.mark.parametrize('policy,pool,slot,total,ok', [
    ('pool', 100, None, None, True), ('pool', None, 10, None, False),
    ('per_student', None, 10, None, True), ('per_student', 100, 10, None, False), ('per_student', None, None, None, False),
    ('both', 100, 10, None, True), ('both', 100, None, None, False), ('both', None, 10, 20, False)])
def test_policy_decides_which_limits_an_activity_may_have(policy, pool, slot, total, ok):
    if ok:
        check_limits(policy, pool, slot, total)
    else:
        with pytest.raises(SettingsError):
            check_limits(policy, pool, slot, total)


def test_pool_sizing_warning_follows_the_rehearsal_rule():
    assert pool_sizing_warning(13000, 4000, 10)                 # 40,000 of slot caps against a 13,000 pool
    assert pool_sizing_warning(13000, 1000, 10) is None


# ── records ────────────────────────────────────────────────────────────
class Db:
    table_prefix = 'T_'

    def __init__(self, path):
        self.path = path

    def get_connection(self):
        c = sqlite3.connect(self.path)
        c.execute('PRAGMA foreign_keys = ON')
        return c


@pytest.fixture
def store(tmp_path):
    db = Db(str(tmp_path / 'lamb.db'))
    with sqlite3.connect(db.path) as c:
        c.execute('CREATE TABLE T_organizations (id INTEGER PRIMARY KEY)')
        c.execute('INSERT INTO T_organizations VALUES (1)')
        MigrationRunner(db)._migration_33(c.cursor())
        MigrationRunner(db)._migration_33(c.cursor())        # idempotent
    return TokenDealerStore(db)


def test_store_round_trips_activities_and_keys(store):
    aid = store.create_activity(resource_link_id='rl-1', organization_id=1, owner_email='t@x.edu', models=['m'],
                                schedule={'mode': 'always'}, slot_tokens=4000, proxy_team_id='team-1')
    a = store.get_activity_by_resource_link('rl-1')
    assert a['id'] == aid and a['models'] == ['m'] and a['schedule'] == {'mode': 'always'} and a['override'] == 'auto'
    kid = store.create_key(aid, 1, 'u1', 'ref', 'sk-abcd', 'hash-1')
    with pytest.raises(sqlite3.IntegrityError):                # one current key per student and activity
        store.create_key(aid, 1, 'u1', 'ref', 'sk-efgh', 'hash-2')
    store.set_key_status(kid, 'revoked', 'rotated')
    kid2 = store.create_key(aid, 1, 'u1', 'ref', 'sk-efgh', 'hash-2')
    assert store.get_current_key(aid, 'u1')['id'] == kid2
    assert store.key_index() == {'hash-1': (kid, aid, 1), 'hash-2': (kid2, aid, 1)}
    store.record_error('key:1', 'closed', 'boom')
    store.record_applied('key:1', 'closed')
    assert store.get_sync_state('key:1')['applied'] == 'closed' and store.get_sync_state('key:1')['last_error'] is None


# ── usage ledger ───────────────────────────────────────────────────────
def log(rid, token, start='2026-10-11T12:41:07.5+00:00', status='success', p=10, c=5):
    return {'request_id': rid, 'api_key': token, 'startTime': start, 'status': status,
            'model_group': 'course-model', 'prompt_tokens': p, 'completion_tokens': c}


def test_ledger_aggregates_per_slot_and_deduplicates(tmp_path):
    ledger = UsageLedger(tmp_path / 'usage.db')
    index = {'h1': (1, 10, 1)}
    rows = [log('a', 'h1'), log('b', 'h1', start='2026-10-11T12:49:59+00:00'), log('c', 'h1', start='2026-10-11T12:50:00+00:00'),
            log('d', 'h1', status='failure', p=0, c=0), log('e', 'not-ours')]
    assert ledger.record(rows, index) == (4, 1)
    assert ledger.record(rows, index) == (0, 5)                 # overlap re-read changes nothing
    assert ledger.totals() == {1: {'requests_ok': 3, 'requests_refused': 1, 'prompt_tokens': 30, 'completion_tokens': 15, 'tokens': 45}}
    assert [s[1:] for s in ledger.slots(10)] == [(2, 1, 30), (1, 0, 15)]
    ledger.set_cursor('p', 100.0)
    ledger.set_cursor('p', 50.0)                                 # never moves back
    assert ledger.cursor('p') == 100.0


# ── proxy client ───────────────────────────────────────────────────────
def mock_client(handler):
    return ProxyClient('http://proxy', 'sk-admin', transport=httpx.MockTransport(handler))


def test_client_sends_the_admin_calls_the_proxy_expects():
    seen = []

    def handler(req):
        seen.append((req.method, req.url.path, json.loads(req.content) if req.content else dict(req.url.params)))
        assert req.headers['authorization'] == 'Bearer sk-admin'
        if req.url.path == '/key/generate':
            return httpx.Response(200, json={'key': 'sk-student', 'token': 'hash'})
        if req.url.path == '/spend/logs/v2':
            page = int(req.url.params['page'])
            return httpx.Response(200, json={'data': [{'request_id': str(page)}], 'total_pages': 2})
        return httpx.Response(200, json={'team_id': 't1'})

    c = mock_client(handler)
    assert c.generate_key(['m'], 'ref', 't1', 'alias', max_budget=0.007, slot_budget=0.004) == {'key': 'sk-student', 'token': 'hash'}
    c.block_key('hash')
    assert [r['request_id'] for r in c.iter_spend_logs(0, 600)] == ['1', '2']
    body = seen[0][2]
    assert body['budget_limits'] == [{'budget_duration': '10m', 'max_budget': 0.004}] and body['max_budget'] == 0.007
    assert seen[1][1:] == ('/key/block', {'key': 'hash'})
    assert seen[2][2]['start_date'] == '1970-01-01 00:00:00'


def test_client_fails_closed():
    with pytest.raises(ProxyError) as e:
        mock_client(lambda r: httpx.Response(429, text='budget')).block_key('h')
    assert e.value.status == 429

    def down(req):
        raise httpx.ConnectError('refused')
    with pytest.raises(ProxyUnavailable):
        mock_client(down).block_key('h')


# ── service and worker, against a fake proxy ───────────────────────────
class FakeProxy:
    def __init__(self):
        self.calls, self.n, self.logs, self.fail = [], 0, [], set()

    def __getattr__(self, name):
        def call(*a, **kw):
            if name in self.fail:
                raise ProxyUnavailable('down')
            self.calls.append((name, a, kw))
            if name == 'create_team':
                return 'team-1'
            if name == 'generate_key':
                self.n += 1
                return {'key': f'sk-secret-{self.n}', 'token': f'hash-{self.n}'}
            if name == 'iter_spend_logs':
                return iter(self.logs)
        return call

    def names(self):
        return [c[0] for c in self.calls]


SETTINGS = Settings(enabled=True, proxy_url='http://proxy', proxy_admin_key='k', public_url='https://llm.x/v1',
                    policy='per_student', teacher_allowance_tokens=20000, models=['m'])


@pytest.fixture
def svc(store):
    proxy = FakeProxy()
    return TokenDealerService(store, lambda org: SETTINGS, lambda org: proxy), proxy


def test_configure_issue_rotate_revoke(svc):
    service, proxy = svc
    aid, warnings = service.configure_activity(1, 'rl-1', 't@x.edu', ['m'], WEEKLY, slot_tokens=4000, total_tokens=7000)
    assert warnings == [] and proxy.names() == ['create_team']
    issued = service.issue_key(aid, 'u1', now=MONDAY_1600_MADRID)
    assert issued['secret'] == 'sk-secret-1' and issued['endpoint'] == 'https://llm.x/v1'
    gen = proxy.calls[-1]
    assert gen[0] == 'generate_key' and gen[1][1] == user_ref(1, 'u1') and gen[1][5:7] == (0.007, 0.004)
    with pytest.raises(KeyExists):
        service.issue_key(aid, 'u1', now=MONDAY_1600_MADRID)
    service.rotate_key(aid, 'u1')
    assert ('delete_keys', (['hash-1'],), {}) in proxy.calls
    service.revoke_key(service.store.get_current_key(aid, 'u1')['id'])
    assert service.store.get_current_key(aid, 'u1') is None


def test_a_key_issued_while_closed_is_blocked_at_once(svc):
    service, proxy = svc
    aid, _ = service.configure_activity(1, 'rl-1', 't@x.edu', ['m'], WEEKLY, slot_tokens=4000)
    service.issue_key(aid, 'u1', now=MONDAY_1700_MADRID)
    assert proxy.names()[-2:] == ['generate_key', 'block_key']


def test_issuance_rolls_back_the_proxy_key_if_recording_fails(svc, monkeypatch):
    service, proxy = svc
    aid, _ = service.configure_activity(1, 'rl-1', 't@x.edu', ['m'], WEEKLY, slot_tokens=4000)
    monkeypatch.setattr(service.store, 'create_key', lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError('locked')))
    with pytest.raises(sqlite3.OperationalError):
        service.issue_key(aid, 'u1', now=MONDAY_1600_MADRID)
    assert proxy.names()[-1] == 'delete_keys'


def test_teacher_allowance_bounds_totals_and_policy_is_enforced(svc):
    service, proxy = svc
    aid, _ = service.configure_activity(1, 'rl-1', 't@x.edu', ['m'], WEEKLY, total_tokens=7000)
    service.issue_key(aid, 'u1', now=MONDAY_1600_MADRID)
    service.issue_key(aid, 'u2', now=MONDAY_1600_MADRID)            # 14,000 of 20,000
    with pytest.raises(AllocationError):
        service.issue_key(aid, 'u3', now=MONDAY_1600_MADRID)
    with pytest.raises(SettingsError):                                # this organization has no pools
        service.configure_activity(1, 'rl-2', 't@x.edu', ['m'], WEEKLY, pool_tokens=1000, slot_tokens=10)
    with pytest.raises(SettingsError):
        service.configure_activity(1, 'rl-2', 't@x.edu', ['other'], WEEKLY, slot_tokens=10)


def test_worker_reconciles_per_key_and_only_on_change(svc, tmp_path):
    service, proxy = svc
    aid, _ = service.configure_activity(1, 'rl-1', 't@x.edu', ['m'], WEEKLY, slot_tokens=4000)
    k1 = service.issue_key(aid, 'u1', now=MONDAY_1600_MADRID)['key_id']
    service.issue_key(aid, 'u2', now=MONDAY_1600_MADRID)
    worker = Worker(service.store, UsageLedger(tmp_path / 'u.db'), lambda o: SETTINGS, lambda o: proxy)
    proxy.calls.clear()
    assert worker.reconcile(MONDAY_1600_MADRID) == {'opened': 0, 'closed': 0, 'errors': 0}
    assert worker.reconcile(MONDAY_1700_MADRID) == {'opened': 0, 'closed': 2, 'errors': 0}
    assert proxy.names() == ['block_key', 'block_key']
    service.set_override(aid, 'open')
    service.block_student(k1)
    assert worker.reconcile(MONDAY_1700_MADRID) == {'opened': 1, 'closed': 0, 'errors': 0}
    proxy.fail.add('unblock_key')
    service.set_override(aid, 'auto')
    service.set_override(aid, 'open')
    service.unblock_student(k1)
    assert worker.reconcile(MONDAY_1700_MADRID)['errors'] == 1
    assert service.store.get_sync_state(f'key:{k1}')['last_error']
    proxy.fail.clear()
    assert worker.reconcile(MONDAY_1700_MADRID)['opened'] == 1      # retried on the next cycle


def test_worker_ingests_into_the_ledger(svc, tmp_path):
    service, proxy = svc
    aid, _ = service.configure_activity(1, 'rl-1', 't@x.edu', ['m'], WEEKLY, slot_tokens=4000)
    service.issue_key(aid, 'u1', now=MONDAY_1600_MADRID)
    worker = Worker(service.store, UsageLedger(tmp_path / 'u.db'), lambda o: SETTINGS, lambda o: proxy)
    proxy.logs = [log('r1', 'hash-1'), log('r2', 'hash-1'), log('r3', 'someone-else')]
    assert worker.ingest(now=MONDAY_1600_MADRID.timestamp()) == {'new': 2, 'skipped': 1, 'errors': 0}
    assert worker.ingest(now=MONDAY_1600_MADRID.timestamp()) == {'new': 0, 'skipped': 3, 'errors': 0}
    assert worker.ledger.totals(activity_id=aid)[1]['tokens'] == 30
