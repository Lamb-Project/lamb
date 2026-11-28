"""Activity identity and teaching access, independent of assistant ownership (#565)."""
from contextlib import closing
import json
import time

from fastapi import HTTPException


def migrate(cursor, prefix):
    columns = {r[1] for r in cursor.execute(f'PRAGMA table_info({prefix}lti_activities)')}
    for name in ('lms_origin', 'lms_scope'):
        if name not in columns:
            cursor.execute(f"ALTER TABLE {prefix}lti_activities ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
    cursor.execute(f'''CREATE TABLE IF NOT EXISTS {prefix}activity_instructors (
        activity_id INTEGER NOT NULL, creator_user_id INTEGER NOT NULL,
        verified_at INTEGER NOT NULL,
        PRIMARY KEY (activity_id, creator_user_id),
        FOREIGN KEY (activity_id) REFERENCES {prefix}lti_activities(id) ON DELETE CASCADE,
        FOREIGN KEY (creator_user_id) REFERENCES {prefix}Creator_users(id) ON DELETE CASCADE)''')


def activity_by_id(db, activity_id):
    with closing(db.get_connection()) as conn:
        cursor = conn.execute(f'SELECT * FROM {db.table_prefix}lti_activities WHERE id=?', (activity_id,))
        row = cursor.fetchone()
        return dict(zip([c[0] for c in cursor.description], row)) if row else None


def creator_by_id(db, user_id):
    with closing(db.get_connection()) as conn:
        cursor = conn.execute(f'SELECT * FROM {db.table_prefix}Creator_users WHERE id=? AND enabled=1', (user_id,))
        row = cursor.fetchone()
        return dict(zip([c[0] for c in cursor.description], row)) if row else None


def is_owner(activity, creator):
    return bool(creator and creator.get('organization_id') == activity.get('organization_id')
                and (creator.get('user_email') or creator.get('email')) == activity.get('owner_email'))


def relationship(db, activity, creator):
    if not creator or creator.get('organization_id') != activity.get('organization_id'):
        return 'none'
    if is_owner(activity, creator):
        return 'owner'
    with closing(db.get_connection()) as conn:
        row = conn.execute(f'''SELECT 1 FROM {db.table_prefix}activity_instructors
            WHERE activity_id=? AND creator_user_id=?''', (activity['id'], creator['id'])).fetchone()
    return 'instructor' if row else 'catalogue'


def creators_for_payload(db, payload):
    if payload.get('activity_creator_id') is not None:
        creator = creator_by_id(db, payload['activity_creator_id'])
        return [creator] if creator else []
    from lamb.lti_activity_manager import LtiActivityManager
    from types import SimpleNamespace
    try:
        return LtiActivityManager.identify_instructor(SimpleNamespace(db_manager=db),
            payload.get('lti_lms_user_id', ''), payload.get('lti_lms_instance', ''))
    except ValueError:
        return []


def owner_for_payload(db, activity, payload):
    return next((c for c in creators_for_payload(db, payload) if is_owner(activity, c)), None)


def require_owner(db, activity, payload):
    creator = owner_for_payload(db, activity, payload)
    if not creator:
        raise HTTPException(403, 'Only the activity owner can change settings')
    return creator


def valid_creator_token(db, payload):
    """Recheck Creator bridge grants on every use; ordinary LTI tokens keep their contract."""
    if 'activity_creator_id' not in payload:
        return True
    activity = activity_by_id(db, payload.get('lti_activity_id'))
    creator = creator_by_id(db, payload['activity_creator_id'])
    return bool(activity and activity['status'] == 'active'
                and payload.get('lti_resource_link_id') == activity['resource_link_id']
                and relationship(db, activity, creator) in ('owner', 'instructor'))


def validate_assistants(db, activity, creator, assistant_ids, *, evaluator=False):
    allowed = {a['id']: a for a in db.get_published_assistants_for_org_user(
        activity['organization_id'], creator['id'], creator.get('user_email') or creator.get('email'))}
    try:
        ids = [int(a) for a in assistant_ids]
    except (ValueError, TypeError):
        raise HTTPException(400, 'Invalid assistant selection')
    if not ids or any(a not in allowed for a in ids):
        raise HTTPException(403, 'Assistant is not available to you in this organization')
    if evaluator and any(not allowed[a].get('rubric_eval_ready') for a in ids):
        raise HTTPException(400, 'The evaluator must be an available assistant with a rubric')
    return ids


def launch_scope(db, resource_link_id, lms_instance):
    """The installation a launch comes from and how an activity records it: the LTI version
    that recorded it, and what the LMS calls itself. The version is a note, not part of the
    identity: an activity belongs to its installation on LTI 1.1 and on LTI 1.3 (#579)."""
    from lamb.lti13 import is_scoped
    from lamb.lti13.store import installation_of
    origin = installation_of(lms_instance, db)  # as the LMS sends it, never parsed
    version = '1.3' if is_scoped(lms_instance) else '1.1'
    return origin, json.dumps([version, origin]) if origin else ''


def scope_instance(db, scope):
    """The installation an activity is recorded on; '' when none is."""
    try:
        value = json.loads(scope) if scope else None
    except (TypeError, ValueError):
        return ''
    if not isinstance(value, list):
        return ''
    if len(value) == 2 and isinstance(value[1], str):
        return value[1].strip()
    if len(value) == 3 and value[0] == '1.3' and db is not None:
        # A record of a build before #579: the registration and the deployment.
        with closing(db.get_connection()) as conn:
            row = conn.execute(f'SELECT installation FROM {db.table_prefix}lti13_registrations WHERE id=?',
                               (value[1],)).fetchone()
        return (row[0] or '').strip() if row else ''
    return ''


def same_scope(recorded, launched, db=None):
    """Whether a launch comes from the installation an activity is recorded on, whatever the
    LTI version of either."""
    if recorded == launched:
        return True
    from lamb.lti_access import same_instance
    old, new = scope_instance(db, recorded), scope_instance(db, launched)
    return bool(old and new) and same_instance(old, new)


def _seen_on_lti11(scope):
    try:
        value = json.loads(scope)
    except (TypeError, ValueError):
        return False
    return isinstance(value, list) and len(value) == 2 and value[0] == '1.1'


def record_launch(db, activity, payload, *, instructor=True):
    """Call only after an authenticated launch/setup, never with unsigned form identity."""
    if 'activity_creator_id' in payload:
        return
    origin, scope = launch_scope(db, activity['resource_link_id'], payload.get('lti_lms_instance', ''))
    accounts = creators_for_payload(db, payload) if instructor else []
    with closing(db.get_connection()) as conn, conn:
        current = conn.execute(f'SELECT lms_origin, lms_scope FROM {db.table_prefix}lti_activities WHERE id=?', (activity['id'],)).fetchone()
        recorded = (current[1] if current else '') or ''
        if recorded and not same_scope(recorded, scope, db):
            raise HTTPException(403, 'This activity belongs to another LMS installation')
        # That the installation was seen on LTI 1.1 stays on record when LTI 1.3 launches follow.
        if scope and not (_seen_on_lti11(recorded) and not _seen_on_lti11(scope)):
            conn.execute(f'''UPDATE {db.table_prefix}lti_activities SET lms_origin=?, lms_scope=? WHERE id=?''',
                         (origin, scope, activity['id']))
        elif recorded:
            origin, scope = current[0] or origin, recorded
        for field in ('context_id', 'context_title'):
            value = payload.get('lti_' + field)
            if value:
                conn.execute(f'UPDATE {db.table_prefix}lti_activities SET {field}=? WHERE id=?', (value, activity['id']))
                activity[field] = value
        for creator in accounts:
            if creator.get('organization_id') == activity['organization_id']:
                conn.execute(f'''INSERT INTO {db.table_prefix}activity_instructors VALUES (?,?,?)
                    ON CONFLICT(activity_id,creator_user_id) DO UPDATE SET verified_at=excluded.verified_at''',
                    (activity['id'], creator['id'], int(time.time())))
    activity.update(lms_origin=origin, lms_scope=scope)


def context(db, activity):
    org = db.get_organization_by_id(activity['organization_id']) or {}
    return {key: activity.get(key) or '' for key in
            ('activity_name', 'context_id', 'context_title', 'lms_origin', 'lms_scope')} | {
                'activity_id': activity['id'], 'org_name': org.get('name', ''),
                'context_known': bool(activity.get('lms_scope'))}
