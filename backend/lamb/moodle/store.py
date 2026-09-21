"""Atomic connector fields inside existing creator and organization config JSON."""
import json
import time
from contextlib import contextmanager

from .policy import MoodlePolicy, MoodleConfigurationError
from .connection import public_connection


class ConnectionConflict(RuntimeError):
    pass


class ConnectionStore:
    def __init__(self, db, organization_id, owner_id):
        self.db = db
        self.organization_id = int(organization_id)
        self.owner_id = int(owner_id)

    @contextmanager
    def transaction(self, write=False):
        connection = self.db.get_connection()
        if connection is None:
            raise RuntimeError('Moodle connection storage is unavailable')
        try:
            if write:
                connection.execute('BEGIN IMMEDIATE')
            with connection:
                yield connection
        finally:
            connection.close()

    def _read(self, connection):
        row = connection.execute(f'''SELECT u.user_config, o.config, o.status
            FROM {self.db.table_prefix}Creator_users u
            JOIN {self.db.table_prefix}organizations o ON o.id=u.organization_id
            WHERE u.id=? AND u.organization_id=?''', (self.owner_id, self.organization_id)).fetchone()
        if row is None or row[2] != 'active':
            raise PermissionError('Creator or organization is unavailable')
        try:
            user = json.loads(row[0]) if row[0] else {}
            org = json.loads(row[1]) if row[1] else {}
            if not isinstance(user, dict) or not isinstance(org, dict): raise ValueError()
        except (TypeError, ValueError):
            raise MoodleConfigurationError('Invalid stored creator or organization configuration') from None
        return user, org

    def snapshot(self):
        with self.transaction() as connection:
            user, org = self._read(connection)
        return {'policy': MoodlePolicy.from_config(org), 'record': user.get('moodle_connection'),
                'generation': user.get('moodle_connection_generation', 0)}

    def _write_user(self, connection, user):
        connection.execute(f'''UPDATE {self.db.table_prefix}Creator_users
            SET user_config=?, updated_at=? WHERE id=? AND organization_id=?''',
            (json.dumps(user), int(time.time()), self.owner_id, self.organization_id))

    def approval_preferences(self):
        from lamb.aac.preferences import approval_preferences
        with self.transaction() as connection:
            user, _ = self._read(connection)
        return approval_preferences(user)

    def set_approval_preferences(self, advanced_mode):
        if type(advanced_mode) is not bool:
            raise ValueError('Advanced mode must be a boolean')
        with self.transaction(write=True) as connection:
            user, _ = self._read(connection)
            user['aac_approval_preferences'] = {'advanced_mode': advanced_mode}
            self._write_user(connection, user)
        return {'advanced_mode': advanced_mode}

    def save(self, record, *, expected_generation, expected_policy):
        with self.transaction(write=True) as connection:
            user, org = self._read(connection)
            policy = MoodlePolicy.from_config(org)
            if user.get('moodle_connection_generation', 0) != expected_generation or policy != expected_policy:
                raise ConnectionConflict('Moodle settings or connection changed. Connect again.')
            policy.require_connection_url(record['base_url'])
            user['moodle_connection'] = record
            user['moodle_connection_generation'] = expected_generation + 1
            self._write_user(connection, user)
        return public_connection(record)

    def disconnect(self):
        with self.transaction(write=True) as connection:
            user, _ = self._read(connection)
            user.pop('moodle_connection', None)
            user['moodle_connection_generation'] = user.get('moodle_connection_generation', 0) + 1
            self._write_user(connection, user)

    def configure(self, settings):
        """Caller must enforce admin permission; patch only this connector section."""
        policy = MoodlePolicy.from_config({'moodle': settings})
        settings = {'enabled': policy.enabled, 'base_url': policy.base_url, 'mode': policy.mode,
                    'write_groups': sorted(policy.write_groups), 'allow_grade_write': policy.allow_grade_write}
        with self.transaction(write=True) as connection:
            _, org = self._read(connection)
            org['moodle'] = settings
            connection.execute(f'''UPDATE {self.db.table_prefix}organizations
                SET config=?, updated_at=? WHERE id=?''', (json.dumps(org), int(time.time()), self.organization_id))
        return settings
