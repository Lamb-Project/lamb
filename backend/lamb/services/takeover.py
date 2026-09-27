"""Administrators acting as a creator for support (#523).

A takeover is a short-lived LAMB token for the creator carrying a ``takeover`` claim with the
real administrator. Every endpoint then treats the request as the creator. The token is valid
only while its record is active (``is_active``, checked in ``lamb.auth.decode_token``), every
write request is audited with the administrator as actor, Moodle is read-only, and the creator
sees a notice afterwards.
"""
import time
import uuid
from contextvars import ContextVar
from datetime import timedelta
from typing import Any, Dict, List, Optional

from lamb.logging_config import get_logger

logger = get_logger(__name__, component="TAKEOVER")

TTL = timedelta(minutes=60)
ADMIN_ORG_ROLES = ('owner', 'admin')

# The takeover claim of the current request, set by TakeoverMiddleware.
current_takeover: ContextVar[Optional[Dict[str, Any]]] = ContextVar('current_takeover', default=None)


class TakeoverRefused(Exception):
    """The administrator may not act as this user, or the action is refused during a takeover."""


def active_takeover() -> Optional[Dict[str, Any]]:
    return current_takeover.get()


def refuse_during_takeover(what: str) -> None:
    if active_takeover():
        raise TakeoverRefused(f'{what} is not available while an administrator is acting as this user.')


def _db():
    from lamb.database_manager import LambDatabaseManager
    return LambDatabaseManager()


def _row(takeover_id: str) -> Optional[Dict[str, Any]]:
    db = _db()
    conn = db.get_connection()
    try:
        cur = conn.execute(f'SELECT id, organization_id, actor_user_id, target_user_id, started_at, expires_at, '
                           f'ended_at, end_reason, acknowledged_at FROM {db.table_prefix}account_takeovers WHERE id = ?',
                           (takeover_id,))
        row = cur.fetchone()
        keys = ('id', 'organization_id', 'actor_user_id', 'target_user_id', 'started_at', 'expires_at',
                'ended_at', 'end_reason', 'acknowledged_at')
        return dict(zip(keys, row)) if row else None
    finally:
        conn.close()


def is_active(takeover_id: str) -> bool:
    try:
        row = _row(takeover_id)
    except Exception as e:  # a missing table or database error never grants access
        logger.error(f'Takeover check failed for {takeover_id}: {e}')
        return False
    return bool(row and row['ended_at'] is None and row['expires_at'] > time.time())


def check_allowed(actor: Dict[str, Any], actor_is_system_admin: bool, actor_org_role: Optional[str],
                  target: Optional[Dict[str, Any]], target_org_role: Optional[str]) -> None:
    """Raise TakeoverRefused unless ``actor`` may act as ``target``."""
    if not target:
        raise TakeoverRefused('User not found.')
    if target.get('id') == actor.get('id'):
        raise TakeoverRefused('You cannot act as yourself.')
    if target.get('enabled') is False:
        raise TakeoverRefused('This account is disabled.')
    if target.get('role') == 'admin':
        raise TakeoverRefused('System administrators cannot be taken over.')
    if actor_is_system_admin:
        return
    if actor_org_role not in ADMIN_ORG_ROLES:
        raise TakeoverRefused('Only system and organization administrators can act as a creator.')
    if target.get('organization_id') != actor.get('organization_id'):
        raise TakeoverRefused('You can act only as creators of your own organization.')
    if target_org_role in ADMIN_ORG_ROLES:
        raise TakeoverRefused('Organization administrators cannot be taken over by another organization administrator.')


def start(auth, target_user_id: int) -> Dict[str, Any]:
    """Start a takeover by the caller (an AuthContext) and return the creator token and its details."""
    from lamb.auth import create_token
    if auth.token_payload.get('takeover'):
        raise TakeoverRefused('A takeover session cannot start another takeover.')
    db = _db()
    # by_id has no role or enabled state; the email lookup returns the full record.
    found = db.get_creator_user_by_id(target_user_id)
    target = db.get_creator_user_by_email(found['user_email']) if found else None
    target_role = (db.get_user_organization_role(target['id'], target['organization_id'])
                   if target and target.get('organization_id') else None)
    check_allowed(auth.user, auth.is_system_admin, auth.organization_role, target, target_role)
    now = int(time.time())
    takeover_id = uuid.uuid4().hex
    expires = now + int(TTL.total_seconds())
    conn = db.get_connection()
    try:
        with conn:
            conn.execute(f'INSERT INTO {db.table_prefix}account_takeovers (id, organization_id, actor_user_id, '
                         f'target_user_id, started_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)',
                         (takeover_id, target['organization_id'], auth.user['id'], target['id'], now, expires))
    finally:
        conn.close()
    actor = {'id': auth.user['id'], 'email': auth.user.get('email'), 'name': auth.user.get('name')}
    token = create_token({'sub': str(target['id']), 'email': target['email'],
                          'role': target.get('role') or 'user',
                          'takeover': {'id': takeover_id, 'actor': actor, 'expires_at': expires}}, expires_delta=TTL)
    db.write_audit_log(target['organization_id'], auth.user['id'], 'takeover.start', 'user', str(target['id']),
                       {'takeover_id': takeover_id, 'expires_at': expires})
    logger.info(f"Takeover {takeover_id}: user {auth.user['id']} acts as user {target['id']} until {expires}")
    return {'token': token, 'takeover_id': takeover_id, 'expires_at': expires,
            'user': {'id': target['id'], 'name': target.get('name'), 'email': target['email']}}


def end(takeover: Dict[str, Any], reason: str = 'ended') -> bool:
    db = _db()
    conn = db.get_connection()
    try:
        with conn:
            cur = conn.execute(f'UPDATE {db.table_prefix}account_takeovers SET ended_at = ?, end_reason = ? '
                               f'WHERE id = ? AND ended_at IS NULL', (int(time.time()), reason, takeover['id']))
            changed = cur.rowcount > 0
    finally:
        conn.close()
    row = _row(takeover['id'])
    if changed and row:
        db.write_audit_log(row['organization_id'], row['actor_user_id'], 'takeover.end', 'user',
                           str(row['target_user_id']), {'takeover_id': row['id'], 'reason': reason})
    return changed


def audit_request(takeover: Dict[str, Any], method: str, path: str) -> None:
    """Record one write request made during a takeover: method and path, never the body."""
    row = _row(takeover['id'])
    if row:
        _db().write_audit_log(row['organization_id'], row['actor_user_id'], 'takeover.request', 'user',
                              str(row['target_user_id']), {'takeover_id': row['id'], 'method': method, 'path': path})


def notices(user_id: int) -> List[Dict[str, Any]]:
    """Takeovers of this creator's account not yet acknowledged, newest first."""
    db = _db()
    conn = db.get_connection()
    try:
        rows = conn.execute(
            f'SELECT t.id, t.started_at, t.expires_at, t.ended_at, u.user_name, u.user_email '
            f'FROM {db.table_prefix}account_takeovers t JOIN {db.table_prefix}Creator_users u ON u.id = t.actor_user_id '
            f'WHERE t.target_user_id = ? AND t.acknowledged_at IS NULL ORDER BY t.started_at DESC', (user_id,)).fetchall()
    finally:
        conn.close()
    now = time.time()
    return [{'id': r[0], 'started_at': r[1], 'ended_at': r[3] or (r[2] if r[2] <= now else None),
             'active': r[3] is None and r[2] > now, 'actor_name': r[4], 'actor_email': r[5]} for r in rows]


def acknowledge(user_id: int, ids: List[str]) -> int:
    """Dismiss notices; an active takeover cannot be dismissed."""
    if not ids:
        return 0
    db = _db()
    conn = db.get_connection()
    try:
        with conn:
            marks = ','.join('?' * len(ids))
            cur = conn.execute(
                f'UPDATE {db.table_prefix}account_takeovers SET acknowledged_at = ? WHERE target_user_id = ? '
                f'AND id IN ({marks}) AND acknowledged_at IS NULL AND (ended_at IS NOT NULL OR expires_at <= ?)',
                (int(time.time()), user_id, *ids, int(time.time())))
            return cur.rowcount
    finally:
        conn.close()


class TakeoverMiddleware:
    """Marks requests made with a takeover token and audits their writes (#523).

    Pure ASGI, so the context variable reaches the endpoint, its threadpool work and AAC tool
    calls. Only the Authorization header is read; request bodies are never logged.
    """

    WRITE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http':
            return await self.app(scope, receive, send)
        claim = None
        for name, value in scope.get('headers') or []:
            if name == b'authorization' and value[:7].lower() == b'bearer ':
                claim = _takeover_claim(value[7:].decode('latin-1').strip())
                break
        if claim is None:
            return await self.app(scope, receive, send)
        marker = current_takeover.set(claim)
        try:
            if scope.get('method') in self.WRITE_METHODS:
                try:
                    audit_request(claim, scope['method'], scope.get('path', ''))
                except Exception as e:
                    logger.error(f'Takeover audit failed: {e}')
            return await self.app(scope, receive, send)
        finally:
            current_takeover.reset(marker)


def _takeover_claim(token: str) -> Optional[Dict[str, Any]]:
    import jwt
    try:
        unverified = jwt.decode(token, options={'verify_signature': False})
    except Exception:
        return None
    if 'takeover' not in unverified:
        return None
    from lamb.auth import decode_token
    payload = decode_token(token)  # signature and active record
    claim = (payload or {}).get('takeover')
    return claim if isinstance(claim, dict) else None
