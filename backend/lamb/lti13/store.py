"""Durable registration, transaction and identity state. No legacy rows are rewritten.

For LAMB an LMS is one installation on LTI 1.1 and on LTI 1.3 (#579). A person and a course
keep the identifiers the LMS gives them in both versions. The installation of an LTI 1.3
session travels as an opaque handle, wherever an LTI 1.1 session carries the name the LMS
gives itself: the handle names the registration and deployment the session came through,
so every token made from a launch stays tied to them. An activity keeps the key it was
created with: the LMS's own identifier when it was first set up on LTI 1.1, an opaque
identifier when it was first set up on LTI 1.3. A launch of either version finds it.
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
    migrate_installations(cursor, prefix)


def migrate_installations(cursor, prefix):
    """One installation for both LTI versions (#579): what each registration's LMS calls
    itself, and the grade service of each learner keyed as the activity is."""
    columns = {row[1] for row in cursor.execute(f'PRAGMA table_info({prefix}lti13_registrations)')}
    if 'installation' not in columns:
        cursor.execute(f"ALTER TABLE {prefix}lti13_registrations ADD COLUMN installation TEXT NOT NULL DEFAULT ''")
    if 'installation_declared' not in columns:
        cursor.execute(f"ALTER TABLE {prefix}lti13_registrations ADD COLUMN installation_declared INTEGER NOT NULL DEFAULT 0")
    cursor.execute(f'''CREATE TABLE IF NOT EXISTS {prefix}lti13_grade_endpoints (
        resource_link_id TEXT NOT NULL, student_email TEXT NOT NULL,
        registration_id INTEGER NOT NULL, deployment_id TEXT NOT NULL, subject TEXT NOT NULL,
        endpoint TEXT NOT NULL, updated_at INTEGER NOT NULL,
        PRIMARY KEY(resource_link_id, student_email),
        FOREIGN KEY(registration_id) REFERENCES {prefix}lti13_registrations(id))''')


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
        value['installation'] = value.get('installation') or ''
        value['installation_declared'] = bool(value.get('installation_declared'))
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
                self._declare(c, cur.lastrowid, data.get('installation'))
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
            self._declare(c, registration_id, data.get('installation'))
            return registration_id

    def _declare(self, connection, registration_id, installation):
        """The system administrator says which installation this registration is. Left empty,
        the first launch records what the LMS calls itself."""
        installation = str(installation or '').strip()
        if not installation:
            return
        if is_scoped(installation) or len(installation) > 255 or any(ord(ch) < 32 for ch in installation):
            raise ValueError('Invalid LMS installation identifier')
        connection.execute(f'UPDATE {self.p}lti13_registrations SET installation=?, installation_declared=1 WHERE id=?',
                           (installation, registration_id))

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

    # -- one installation for both versions (#579) ---------------------------------------

    def installation_for(self, registration, guid):
        """The installation a launch of this registration belongs to.

        It is what the LMS calls itself (`tool_platform.guid`, the value LTI 1.1 sends as
        `tool_consumer_instance_guid`), recorded on the first launch and fixed from then on:
        a platform cannot name another installation later. A name another platform already
        holds is not taken; the platform is then known by its issuer, as is one that sends no
        name. The system administrator can declare the installation on the registration.
        """
        from lamb.lti_access import same_instance
        if registration['installation']:
            return registration['installation']
        guid = str(guid or '').strip()
        chosen = guid or registration['issuer']
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            if guid:
                others = c.execute(f"SELECT installation FROM {self.p}lti13_registrations WHERE issuer<>? AND installation<>?",
                                   (registration['issuer'], '')).fetchall()
                if any(same_instance(row[0], guid) for row in others):
                    chosen = registration['issuer']
            # No revision change: sessions and the launch in progress stay valid.
            c.execute(f"UPDATE {self.p}lti13_registrations SET installation=? WHERE id=? AND installation=''",
                      (chosen, registration['id']))
            return c.execute(f'SELECT installation FROM {self.p}lti13_registrations WHERE id=?',
                             (registration['id'],)).fetchone()[0]

    def instance_handle(self, registration_id, deployment_id, installation):
        """What an LTI 1.3 session carries as its LMS instance."""
        return self.object_id(registration_id, deployment_id, 'instance', installation)

    def instance(self, handle):
        """The installation and the registration behind a handle. ValueError when the handle is
        unknown or its registration or deployment is no longer enabled."""
        value = self.object(handle, 'instance')
        return value['external_id'], self.registration(value['registration_id'], value['deployment_id'])

    def _activity_scope(self, connection, resource_link_id):
        try:
            row = connection.execute(f'SELECT lms_scope FROM {self.p}lti_activities WHERE resource_link_id=?',
                                     (resource_link_id,)).fetchone()
        except sqlite3.OperationalError:  # the column of a later migration
            row = connection.execute(f'SELECT \'\' FROM {self.p}lti_activities WHERE resource_link_id=?',
                                     (resource_link_id,)).fetchone()
        return None if row is None else (row[0] or '')

    def _opaque_activity(self, connection, installation, external_id, prefer=None):
        """The opaque key of an activity first set up on LTI 1.3 from this installation."""
        from lamb.lti_access import same_instance
        rows = connection.execute(f'''SELECT o.id, o.registration_id, o.deployment_id, r.installation, r.issuer
            FROM {self.p}lti13_objects o
            JOIN {self.p}lti13_registrations r ON r.id=o.registration_id
            JOIN {self.p}lti_activities a ON a.resource_link_id=o.id
            WHERE o.kind='resource' AND o.external_id=? ORDER BY o.rowid''', (external_id,)).fetchall()
        found = [row for row in rows if row['installation'] and same_instance(row['installation'], installation)]
        mine = [row for row in found if (row['registration_id'], row['deployment_id']) == prefer]
        return (mine or found)[0]['id'] if found else None

    def activity_key(self, registration, deployment_id, installation, external_id):
        """The key of the activity an LTI 1.3 launch opens.

        The LMS's own identifier when an activity set up on LTI 1.1 from this installation has
        it; else the opaque key of an activity set up on LTI 1.3 from this installation; else
        a new opaque key under this registration. An activity from before installations were
        recorded has none: a platform takes it only when LAMB has seen its installation on
        LTI 1.1, or the system administrator declared the installation on the registration.
        """
        from lamb.activity_access import scope_instance
        from lamb.lti_access import same_instance, seen_instances
        with self.connection() as c:
            recorded = self._activity_scope(c, external_id)
            if recorded is not None:
                owner = scope_instance(self.db, recorded)
                if owner:
                    if same_instance(owner, installation):
                        return external_id
                elif (registration['installation_declared']
                      or any(same_instance(seen, installation) for seen in seen_instances(self.db))):
                    return external_id
            opaque = self._opaque_activity(c, installation, external_id, (registration['id'], deployment_id))
        return opaque or self.object_id(registration['id'], deployment_id, 'resource', external_id)

    def legacy_activity_key(self, installation, external_id):
        """The key of the activity an LTI 1.1 launch opens: its own identifier, as always, unless
        no such activity exists and one was set up on LTI 1.3 from the same installation."""
        installation = str(installation or '').strip()
        if not installation or not external_id:
            return external_id
        with self.connection() as c:
            if self._activity_scope(c, external_id) is not None:
                return external_id
            return self._opaque_activity(c, installation, external_id) or external_id

    # -- grade service of each learner ---------------------------------------------------

    def save_grade_endpoint(self, resource_link_id, student_email, registration_id, deployment_id, subject, endpoint):
        with self.connection() as c:
            c.execute(f'''INSERT INTO {self.p}lti13_grade_endpoints
                (resource_link_id,student_email,registration_id,deployment_id,subject,endpoint,updated_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(resource_link_id,student_email) DO UPDATE SET
                    registration_id=excluded.registration_id,deployment_id=excluded.deployment_id,
                    subject=excluded.subject,endpoint=excluded.endpoint,updated_at=excluded.updated_at''',
                (resource_link_id, student_email, registration_id, deployment_id, subject,
                 json.dumps(endpoint), int(time.time())))

    def clear_grade_endpoint(self, resource_link_id, student_email):
        """An LTI 1.1 launch makes Basic Outcomes the learner's current grade return."""
        with self.connection() as c:
            c.execute(f'DELETE FROM {self.p}lti13_grade_endpoints WHERE resource_link_id=? AND student_email=?',
                      (resource_link_id, student_email))

    def has_grade_endpoint(self, resource_link_id, student_email):
        with self.connection() as c:
            return c.execute(f'''SELECT 1 FROM {self.p}lti13_grade_endpoints
                WHERE resource_link_id=? AND student_email=?''', (resource_link_id, student_email)).fetchone() is not None

    def grade_target(self, resource_link_id, student_email):
        with self.connection() as c:
            row = c.execute(f'''SELECT * FROM {self.p}lti13_grade_endpoints
                WHERE resource_link_id=? AND student_email=?''', (resource_link_id, student_email)).fetchone()
        if not row:
            raise ValueError('Learner has no validated LTI 1.3 grade target; relaunch from the LMS')
        return self.registration(row['registration_id'], row['deployment_id']), row['subject'], json.loads(row['endpoint'])


def installation_of(lms_instance, db=None):
    """What the LMS of a session calls itself: the name itself on LTI 1.1, the name behind the
    handle on LTI 1.3. ValueError when the handle's registration is no longer enabled."""
    if is_scoped(lms_instance):
        return Store(db).instance(lms_instance)[0]
    return str(lms_instance or '').strip()


def session_claims(data):
    """Stamp module/session JWTs without changing legacy tokens or the module contract."""
    identity = data.get('lti_identity') if isinstance(data.get('lti_identity'), dict) else {}
    ids = [data.get('lti_lms_instance'), data.get('lms_instance'), identity.get('lms_instance')]
    ids = [v for v in ids if is_scoped(v)]
    if not ids:
        return {}
    store = Store()
    objects = [store.object(v, 'instance') for v in ids]
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
