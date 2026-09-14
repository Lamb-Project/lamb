"""Turn-scoped browser commands. Shared SQLite mailbox supports multiple workers."""
import asyncio
import json
import time
import uuid
from lamb.database_manager import LambDatabaseManager

TABS = {'assistant': ('properties', 'tests', 'chat', 'activity', 'edit'), 'kb': ('files', 'ingest', 'query'), 'rubric': ('view',)}
PAGES = {'assistants', 'assistant-create'}


def destination(args, kwargs):
    if len(args) == 1 and args[0] in PAGES:
        if 'tab' in kwargs:
            raise ValueError('List and creation destinations do not accept --tab')
        return {'resource': args[0], 'id': '', 'tab': ''}
    if len(args) != 2 or args[0] not in TABS:
        raise ValueError('Use frontend-manage open assistants|assistant-create, or assistant|kb|rubric ID [--tab TAB]')
    kind, resource_id = args
    if kind == 'rubric':
        try:
            resource_id = str(uuid.UUID(resource_id))
        except ValueError:
            raise ValueError('Rubric ID must be a UUID') from None
    elif not resource_id.isascii() or not resource_id.isdecimal() or int(resource_id) < 1:
        raise ValueError('Assistant and KB IDs must be positive integers')
    else:
        resource_id = str(int(resource_id))
    tab = kwargs.get('tab', TABS[kind][0])
    if tab not in TABS[kind]:
        raise ValueError(f'Unsupported {kind} tab. Available: {", ".join(TABS[kind])}')
    return {'resource': kind, 'id': resource_id, 'tab': tab}



class Mailbox:
    def __init__(self, db=None):
        self.db = db or LambDatabaseManager()
        self.table = f'{self.db.table_prefix}aac_frontend_actions'
        with self.db.get_connection() as c:
            c.execute(f'''CREATE TABLE IF NOT EXISTS {self.table}
                (id TEXT PRIMARY KEY, session TEXT, owner TEXT, channel TEXT,
                 expires REAL, payload TEXT, result TEXT)''')
            c.execute(f'DELETE FROM {self.table} WHERE expires < ?', (time.time()-60,))

    def create(self, session, owner, channel, payload, ttl=25):
        action = str(uuid.uuid4())
        with self.db.get_connection() as c:
            c.execute(f'INSERT INTO {self.table} VALUES (?,?,?,?,?,?,NULL)',
                      (action, session, owner, channel, time.time()+ttl, json.dumps(payload)))
        return action

    def pending(self, session, owner, channel):
        with self.db.get_connection() as c:
            rows = c.execute(f'SELECT id,payload,expires FROM {self.table} WHERE session=? AND owner=? AND channel=? AND expires>? AND result IS NULL',
                             (session, owner, channel, time.time())).fetchall()
        return [{'action_id': r[0], 'expires': r[2], **json.loads(r[1])} for r in rows]

    def acknowledge(self, action, session, owner, channel, result):
        with self.db.get_connection() as c:
            return c.execute(f'UPDATE {self.table} SET result=? WHERE id=? AND session=? AND owner=? AND channel=? AND expires>? AND result IS NULL',
                             (json.dumps(result), action, session, owner, channel, time.time())).rowcount == 1

    def result(self, action):
        with self.db.get_connection() as c:
            row = c.execute(f'SELECT result FROM {self.table} WHERE id=? AND expires>?', (action, time.time())).fetchone()
        return json.loads(row[0]) if row and row[0] else None

    def expire(self, session, owner, channel):
        with self.db.get_connection() as c:
            c.execute(f'UPDATE {self.table} SET expires=0 WHERE session=? AND owner=? AND channel=?', (session, owner, channel))


class FrontendBridge:
    def __init__(self, session, owner, channel):
        self.session, self.owner, self.channel = session, owner, str(uuid.UUID(channel))
        self.box = Mailbox()

    async def request(self, payload):
        action = self.box.create(self.session, self.owner, self.channel, payload)
        for _ in range(100):
            result = self.box.result(action)
            if result is not None:
                if result['status'] not in ('opened', 'current'):
                    raise ValueError(f"Frontend {result['status']}: {result.get('reason', '')}")
                expected = 'current' if payload['operation'] == 'current' else 'opened'
                if result['status'] != expected or (expected == 'opened' and any(result.get(k) != payload[k] for k in ('resource', 'id', 'tab'))):
                    raise ValueError('Frontend acknowledgement did not match the requested destination')
                return result
            await asyncio.sleep(.25)
        raise ValueError('Frontend acknowledgement timed out; navigation is not confirmed. Do not claim the page opened.')

    def close(self):
        self.box.expire(self.session, self.owner, self.channel)
