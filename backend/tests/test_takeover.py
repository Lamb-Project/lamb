"""Administrators acting as a creator (#523)."""
import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from lamb.services import takeover


@pytest.fixture
def db(tmp_path):
    """A fresh LAMB database with one organization pair and five users."""
    from lamb.database_manager import LambDatabaseManager
    with patch('config.LAMB_DB_PATH', str(tmp_path)), patch.object(LambDatabaseManager, '_system_org_initialized', True), \
            patch.object(LambDatabaseManager, '_ready_databases', set()):
        manager = LambDatabaseManager()
        with patch('lamb.services.takeover._db', lambda: manager), \
                patch('lamb.auth_context._db', manager), \
                patch('lamb.database_manager.LambDatabaseManager', lambda: manager):
            conn = manager.get_connection()
            tp = manager.table_prefix
            with conn:
                for oid, slug in ((10, 'org-a'), (20, 'org-b')):
                    conn.execute(f"INSERT INTO {tp}organizations (id, slug, name, is_system, status, config, created_at, updated_at) "
                                 f"VALUES (?, ?, ?, 0, 'active', '{{}}', 0, 0)", (oid, slug, slug))
                cols = [r[1] for r in conn.execute(f'PRAGMA table_info({tp}Creator_users)')]
                users = {1: ('sys@x.test', 10, 'admin', 1), 2: ('orgadmin@x.test', 10, 'user', 1),
                         3: ('ana@x.test', 10, 'user', 1), 4: ('bob@x.test', 20, 'user', 1),
                         5: ('off@x.test', 10, 'user', 0), 6: ('coadmin@x.test', 10, 'user', 1)}
                for uid, (email, org, role, enabled) in users.items():
                    row = {'id': uid, 'organization_id': org, 'user_email': email, 'user_name': email.split('@')[0],
                           'user_type': 'creator', 'user_config': '{}', 'created_at': 0, 'updated_at': 0,
                           'enabled': enabled, 'role': role}
                    keys = [k for k in row if k in cols]
                    conn.execute(f"INSERT INTO {tp}Creator_users ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})",
                                 [row[k] for k in keys])
            conn.close()
            manager.assign_organization_role(10, 2, 'admin')
            manager.assign_organization_role(10, 6, 'admin')
            manager.assign_organization_role(10, 3, 'member')
            yield manager


def auth_for(db, uid):
    from lamb.auth_context import _build_auth_context
    from lamb.auth import create_token
    user = db.get_creator_user_by_id(uid)
    return _build_auth_context(create_token({'sub': str(uid), 'email': user['user_email'], 'role': 'user'}))


def test_who_may_act_as_whom(db):
    sysadmin, orgadmin, ana = auth_for(db, 1), auth_for(db, 2), auth_for(db, 3)
    assert takeover.start(sysadmin, 4)['user']['email'] == 'bob@x.test'  # any organization
    assert takeover.start(orgadmin, 3)['user']['email'] == 'ana@x.test'  # own organization
    for actor, target, reason in ((orgadmin, 4, 'own organization'), (orgadmin, 6, 'Organization administrators'),
                                  (orgadmin, 1, 'System administrators'), (orgadmin, 2, 'yourself'),
                                  (sysadmin, 5, 'disabled'), (ana, 4, 'Only system and organization'),
                                  (sysadmin, 999, 'not found')):
        with pytest.raises(takeover.TakeoverRefused, match=reason):
            takeover.start(actor, target)


def test_token_acts_as_the_creator_only_while_active(db):
    from lamb.auth import decode_token
    from lamb.auth_context import _build_auth_context
    started = takeover.start(auth_for(db, 2), 3)
    ctx = _build_auth_context(started['token'])
    assert ctx.user['email'] == 'ana@x.test' and not ctx.is_org_admin and not ctx.is_system_admin
    assert ctx.token_payload['takeover']['actor']['email'] == 'orgadmin@x.test'
    with pytest.raises(takeover.TakeoverRefused, match='cannot start another'):
        takeover.start(ctx, 4)
    assert takeover.end(ctx.token_payload['takeover']) is True
    assert decode_token(started['token']) is None and _build_auth_context(started['token']) is None


def test_expired_record_invalidates_the_token(db):
    from lamb.auth import decode_token
    started = takeover.start(auth_for(db, 1), 3)
    conn = db.get_connection()
    with conn:
        conn.execute(f'UPDATE {db.table_prefix}account_takeovers SET expires_at = ?', (int(time.time()) - 1,))
    conn.close()
    assert decode_token(started['token']) is None


def test_creator_sees_notices_and_dismisses_them_after_the_end(db):
    started = takeover.start(auth_for(db, 2), 3)
    [notice] = takeover.notices(3)
    assert notice['actor_email'] == 'orgadmin@x.test' and notice['active'] is True
    assert takeover.acknowledge(3, [started['takeover_id']]) == 0  # an active takeover stays visible
    takeover.end({'id': started['takeover_id']})
    assert takeover.notices(3)[0]['active'] is False
    assert takeover.acknowledge(4, [started['takeover_id']]) == 0  # only the account owner
    assert takeover.acknowledge(3, [started['takeover_id']]) == 1 and takeover.notices(3) == []


def audit_rows(db):
    conn = db.get_connection()
    try:
        return [(a, json.loads(d)) for a, d in conn.execute(
            f'SELECT action, details FROM {db.table_prefix}audit_log WHERE action LIKE "takeover.%" ORDER BY id')]
    finally:
        conn.close()


def test_middleware_marks_takeover_requests_and_audits_writes_only(db):
    started = takeover.start(auth_for(db, 1), 3)
    seen = []

    async def app(scope, receive, send):
        seen.append(takeover.active_takeover())

    mw = takeover.TakeoverMiddleware(app)
    header = [(b'authorization', b'Bearer ' + started['token'].encode())]
    for method in ('GET', 'POST', 'DELETE'):
        asyncio.run(mw({'type': 'http', 'method': method, 'path': '/creator/assistant/x', 'headers': header}, None, None))
    normal = auth_for(db, 3)
    from lamb.auth import create_token
    plain = create_token({'sub': '3', 'email': 'ana@x.test', 'role': 'user'})
    asyncio.run(mw({'type': 'http', 'method': 'POST', 'path': '/p', 'headers': [(b'authorization', b'Bearer ' + plain.encode())]}, None, None))
    assert [bool(s) for s in seen] == [True, True, True, False] and takeover.active_takeover() is None
    rows = audit_rows(db)
    assert [a for a, _ in rows] == ['takeover.start', 'takeover.request', 'takeover.request']
    assert [d['method'] for a, d in rows[1:]] == ['POST', 'DELETE'] and 'body' not in json.dumps(rows)
    assert normal.user['email'] == 'ana@x.test'


def test_moodle_is_read_only_during_a_takeover():
    from lamb.moodle.policy import MoodlePolicy
    from lamb.moodle import store as moodle_store
    full = MoodlePolicy(True, 'https://moodle.example', 'full', frozenset({'forum'}), True)
    fake = SimpleNamespace(transaction=lambda: _Ctx(), _read=lambda c: ({'moodle_connection': {'x': 1}}, {}))
    with patch.object(moodle_store.MoodlePolicy, 'from_config', lambda org: full):
        assert moodle_store.ConnectionStore.snapshot(fake)['policy'] == full
        marker = takeover.current_takeover.set({'id': 't'})
        try:
            policy = moodle_store.ConnectionStore.snapshot(fake)['policy']
            assert policy.mode == 'readonly' and not policy.write_groups and not policy.allow_grade_write
            with pytest.raises(PermissionError, match='read-only'):
                policy.require_write('forum')
            with pytest.raises(PermissionError, match='read-only'):
                moodle_store.ConnectionStore.disconnect(fake)
        finally:
            takeover.current_takeover.reset(marker)


class _Ctx:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False
