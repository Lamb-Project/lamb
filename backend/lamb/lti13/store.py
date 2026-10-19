"""Durable registration, transaction and identity state. No legacy rows are rewritten.

Opaque internal IDs let existing modules keep their activity/user interfaces while
all 1.3 external identifiers are keyed by registration, deployment and object kind.
The original identifiers remain available for service calls and administration.
"""
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager

from . import PREFIX, is_scoped


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def migrate(cursor, prefix):
    statements = [
        '''CREATE TABLE IF NOT EXISTS {p}lti13_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            issuer TEXT NOT NULL, client_id TEXT NOT NULL,
            authorization_url TEXT NOT NULL, token_url TEXT NOT NULL, jwks_url TEXT NOT NULL,
            deployment_ids TEXT NOT NULL, organization_ids TEXT NOT NULL,
            service_origins TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            revision INTEGER NOT NULL DEFAULT 1, updated_at INTEGER NOT NULL,
            UNIQUE(issuer, client_id))''',
        '''CREATE TABLE IF NOT EXISTS {p}lti13_objects (
            id TEXT PRIMARY KEY, registration_id INTEGER NOT NULL,
            deployment_id TEXT NOT NULL, kind TEXT NOT NULL, external_id TEXT NOT NULL,
            UNIQUE(registration_id, deployment_id, kind, external_id),
            FOREIGN KEY(registration_id) REFERENCES {p}lti13_registrations(id))''',
        '''CREATE TABLE IF NOT EXISTS {p}lti13_transactions (
            state_hash TEXT PRIMARY KEY, registration_id INTEGER NOT NULL,
            revision INTEGER NOT NULL, deployment_hint TEXT NOT NULL,
            nonce_hash TEXT NOT NULL, proof_hash TEXT NOT NULL,
            target TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
            consumed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(registration_id) REFERENCES {p}lti13_registrations(id))''',
        '''CREATE INDEX IF NOT EXISTS {p}lti13_transactions_expiry
            ON {p}lti13_transactions(expires_at)''',
        '''CREATE TABLE IF NOT EXISTS {p}lti13_identity_links (
            user_id TEXT NOT NULL, creator_user_id INTEGER NOT NULL, linked_at INTEGER NOT NULL,
            PRIMARY KEY(user_id, creator_user_id),
            FOREIGN KEY(user_id) REFERENCES {p}lti13_objects(id),
            FOREIGN KEY(creator_user_id) REFERENCES {p}Creator_users(id))''',
        '''CREATE TABLE IF NOT EXISTS {p}lti13_grade_targets (
            resource_id TEXT NOT NULL, user_id TEXT NOT NULL, student_email TEXT NOT NULL,
            endpoint TEXT NOT NULL, updated_at INTEGER NOT NULL,
            PRIMARY KEY(resource_id, user_id), UNIQUE(resource_id, student_email),
            FOREIGN KEY(resource_id) REFERENCES {p}lti13_objects(id),
            FOREIGN KEY(user_id) REFERENCES {p}lti13_objects(id))''',
    ]
    for sql in statements:
        cursor.execute(sql.format(p=prefix))


class Store:
    def __init__(self, db=None):
        if db is None:
            from lamb.database_manager import LambDatabaseManager
            db = LambDatabaseManager()
        self.db = db
        self.p = db.table_prefix

    @contextmanager
    def connection(self):
        conn = self.db.get_connection()
        if conn is None:
            raise RuntimeError('LTI database unavailable')
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _registration(row):
        if row is None:
            return None
        value = dict(row)
        for key in ('deployment_ids', 'organization_ids', 'service_origins'):
            value[key] = json.loads(value[key])
        value['enabled'] = bool(value['enabled'])
        return value

    def registrations(self, issuer=None):
        with self.connection() as c:
            sql = f'SELECT * FROM {self.p}lti13_registrations'
            rows = c.execute(sql + (' WHERE issuer=?' if issuer is not None else '') + ' ORDER BY id',
                             (issuer,) if issuer is not None else ()).fetchall()
            return [self._registration(row) for row in rows]

    def registration(self, registration_id, deployment_id=None):
        with self.connection() as c:
            row = c.execute(f'SELECT * FROM {self.p}lti13_registrations WHERE id=?',
                            (registration_id,)).fetchone()
        value = self._registration(row)
        if not value or not value['enabled']:
            raise ValueError('Unknown or disabled LTI registration')
        if deployment_id is not None and deployment_id not in value['deployment_ids']:
            raise ValueError('Unknown or disabled LTI deployment')
        return value

    def save_registration(self, data, registration_id=None):
        fields = ('name', 'issuer', 'client_id', 'authorization_url', 'token_url', 'jwks_url',
                  'deployment_ids', 'organization_ids', 'service_origins', 'enabled')
        values = [json.dumps(data[k]) if isinstance(data[k], list) else data[k] for k in fields]
        with self.connection() as c:
            if registration_id is None:
                cur = c.execute(f'''INSERT INTO {self.p}lti13_registrations
                    ({','.join(fields)},updated_at) VALUES ({','.join('?' for _ in fields)},?)''',
                    (*values, int(time.time())))
                return cur.lastrowid
            old = c.execute(f'SELECT issuer,client_id FROM {self.p}lti13_registrations WHERE id=?',
                            (registration_id,)).fetchone()
            if not old:
                raise ValueError('Registration not found')
            if (old['issuer'], old['client_id']) != (data['issuer'], data['client_id']):
                raise ValueError('Issuer and client ID are immutable; create a new registration')
            c.execute(f'''UPDATE {self.p}lti13_registrations SET
                {','.join(k+'=?' for k in fields)}, revision=revision+1, updated_at=? WHERE id=?''',
                (*values, int(time.time()), registration_id))
            return registration_id

    def new_transaction(self, registration, target, deployment_hint=''):
        state, nonce, proof = (secrets.token_urlsafe(32) for _ in range(3))
        now = int(time.time())
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute(f'DELETE FROM {self.p}lti13_transactions WHERE expires_at<?', (now,))
            count = c.execute(f'''SELECT COUNT(*) FROM {self.p}lti13_transactions
                WHERE registration_id=? AND consumed=0''', (registration['id'],)).fetchone()[0]
            if count >= 1000:
                raise ValueError('Too many pending LTI logins; retry shortly')
            c.execute(f'''INSERT INTO {self.p}lti13_transactions
                (state_hash,registration_id,revision,deployment_hint,nonce_hash,proof_hash,
                 target,created_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?)''',
                (digest(state), registration['id'], registration['revision'], deployment_hint,
                 digest(nonce), digest(proof), target, now, now + 600))
        return state, nonce, proof

    def transaction(self, state, proof):
        if not isinstance(state, str) or not isinstance(proof, str) or len(state) > 128 or len(proof) > 128:
            raise ValueError('Invalid LTI transaction')
        with self.connection() as c:
            row = c.execute(f'SELECT * FROM {self.p}lti13_transactions WHERE state_hash=?',
                            (digest(state),)).fetchone()
        if (not row or row['consumed'] or row['expires_at'] <= time.time()
                or not secrets.compare_digest(row['proof_hash'], digest(proof))):
            raise ValueError('Missing, expired or replayed LTI transaction')
        return dict(row)

    def consume(self, transaction):
        with self.connection() as c:
            # Atomic across workers. A registration edit between validation and consumption fails closed.
            n = c.execute(f'''UPDATE {self.p}lti13_transactions SET consumed=1
                WHERE state_hash=? AND consumed=0 AND expires_at>?
                AND EXISTS (SELECT 1 FROM {self.p}lti13_registrations r
                    WHERE r.id=registration_id AND r.enabled=1 AND r.revision=?)''',
                (transaction['state_hash'], int(time.time()), transaction['revision'])).rowcount
            if n != 1:
                raise ValueError('Expired or replayed LTI transaction')

    def object_id(self, registration_id, deployment_id, kind, external_id):
        with self.connection() as c:
            c.execute(f'''INSERT OR IGNORE INTO {self.p}lti13_objects
                (id,registration_id,deployment_id,kind,external_id) VALUES (?,?,?,?,?)''',
                (PREFIX + kind[0] + '_' + secrets.token_hex(16), registration_id, deployment_id, kind, external_id))
            return c.execute(f'''SELECT id FROM {self.p}lti13_objects
                WHERE registration_id=? AND deployment_id=? AND kind=? AND external_id=?''',
                (registration_id, deployment_id, kind, external_id)).fetchone()[0]

    def object(self, internal_id, kind=None):
        with self.connection() as c:
            row = c.execute(f'SELECT * FROM {self.p}lti13_objects WHERE id=?', (internal_id,)).fetchone()
        if not row or (kind is not None and row['kind'] != kind):
            raise ValueError('Unknown LTI identity or resource')
        value = dict(row)
        self.registration(value['registration_id'], value['deployment_id'])
        return value

    def creators(self, user_id):
        user = self.object(user_id, 'user')
        reg = self.registration(user['registration_id'], user['deployment_id'])
        with self.connection() as c:
            rows = c.execute(f'''SELECT cu.* FROM {self.p}Creator_users cu
                JOIN {self.p}lti13_identity_links link ON link.creator_user_id=cu.id
                WHERE link.user_id=? AND cu.enabled=1''', (user_id,)).fetchall()
        return [dict(row) for row in rows if row['organization_id'] in reg['organization_ids']]

    def link_creator(self, user_id, creator_id):
        user = self.object(user_id, 'user')
        reg = self.registration(user['registration_id'], user['deployment_id'])
        creator = self.db.get_creator_user_by_id(creator_id)
        if not creator or not creator.get('enabled', True) or creator['organization_id'] not in reg['organization_ids']:
            raise ValueError('Creator account is not allowed for this LMS registration')
        with self.connection() as c:
            c.execute(f'''INSERT OR IGNORE INTO {self.p}lti13_identity_links
                (user_id,creator_user_id,linked_at) VALUES (?,?,?)''', (user_id, creator_id, int(time.time())))

    def assert_org(self, resource_id, organization_id):
        resource = self.object(resource_id, 'resource')
        reg = self.registration(resource['registration_id'], resource['deployment_id'])
        if organization_id not in reg['organization_ids']:
            raise ValueError('Organization is not allowed for this LMS registration')

    def save_grade_target(self, resource_id, user_id, student_email, endpoint):
        with self.connection() as c:
            c.execute(f'''INSERT INTO {self.p}lti13_grade_targets
                (resource_id,user_id,student_email,endpoint,updated_at) VALUES (?,?,?,?,?)
                ON CONFLICT(resource_id,user_id) DO UPDATE SET
                    student_email=excluded.student_email,endpoint=excluded.endpoint,updated_at=excluded.updated_at''',
                (resource_id, user_id, student_email, json.dumps(endpoint), int(time.time())))

    def grade_target(self, resource_id, student_email):
        resource = self.object(resource_id, 'resource')
        with self.connection() as c:
            row = c.execute(f'''SELECT g.endpoint,u.external_id AS subject FROM {self.p}lti13_grade_targets g
                JOIN {self.p}lti13_objects u ON u.id=g.user_id
                WHERE g.resource_id=? AND g.student_email=? AND u.registration_id=? AND u.deployment_id=?''',
                (resource_id, student_email, resource['registration_id'], resource['deployment_id'])).fetchone()
        if not row:
            raise ValueError('Learner has no validated LTI 1.3 grade target; relaunch from the LMS')
        return self.registration(resource['registration_id'], resource['deployment_id']), row['subject'], json.loads(row['endpoint'])


def session_claims(data):
    """Stamp module/session JWTs without changing legacy tokens or the module contract."""
    ids = [data.get(k) for k in ('lti_resource_link_id', 'resource_link_id', 'lti_lms_user_id', 'lms_user_id')]
    ids = [v for v in ids if is_scoped(v)]
    if not ids:
        return {}
    store = Store()
    objects = [store.object(v) for v in ids]
    origin = {(o['registration_id'], o['deployment_id']) for o in objects}
    if len(origin) != 1:
        raise ValueError('Cross-registration LTI session')
    reg_id, deployment = next(iter(origin))
    reg = store.registration(reg_id, deployment)
    return {'lti13_registration_id': reg_id, 'lti13_deployment_id': deployment,
            'lti13_registration_revision': reg['revision']}


def session_active(data):
    if 'lti13_registration_id' not in data:
        return True
    try:
        reg = Store().registration(data['lti13_registration_id'], data['lti13_deployment_id'])
        return reg['revision'] == data['lti13_registration_revision']
    except (ValueError, KeyError):
        return False
