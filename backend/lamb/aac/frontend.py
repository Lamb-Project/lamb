"""Turn-scoped browser commands. Shared SQLite mailbox supports multiple workers."""
import asyncio
import json
import time
import uuid
from contextlib import closing, suppress
from functools import lru_cache

TABS = {'assistant': ('properties', 'tests', 'chat', 'activity', 'edit'), 'kb': ('files', 'ingest', 'query'), 'rubric': ('view',), 'learning-scenario': ('view', 'edit')}
PAGES = {'assistants', 'assistant-create', 'learning-scenarios'}


def destination(args, kwargs):
    if len(args) == 1 and args[0] in PAGES:
        if 'tab' in kwargs:
            raise ValueError('List and creation destinations do not accept --tab')
        return {'resource': args[0], 'id': '', 'tab': ''}
    if len(args) != 2 or args[0] not in TABS:
        raise ValueError('Use frontend-manage open assistants|assistant-create, or assistant|kb|rubric ID [--tab TAB]')
    kind, resource_id = args
    if kind in ('rubric', 'learning-scenario'):
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
        from lamb.database_manager import LambDatabaseManager
        self.db = db or LambDatabaseManager()
        self.table = f'{self.db.table_prefix}aac_frontend_actions'
        with closing(self.db.get_connection()) as c, c:
            c.execute(f'''CREATE TABLE IF NOT EXISTS {self.table}
                (id TEXT PRIMARY KEY, session TEXT, owner TEXT, channel TEXT,
                 expires REAL, payload TEXT, result TEXT)''')
            c.execute(f'DELETE FROM {self.table} WHERE expires < ?', (time.time()-60,))

    def create(self, session, owner, channel, payload, ttl=25):
        action = str(uuid.uuid4())
        with closing(self.db.get_connection()) as c, c:
            c.execute(f'DELETE FROM {self.table} WHERE expires < ?', (time.time()-60,))
            c.execute(f'INSERT INTO {self.table} VALUES (?,?,?,?,?,?,NULL)',
                      (action, session, owner, channel, time.time()+ttl, json.dumps(payload)))
        return action

    def claim(self, action, session, owner, channel):
        # One-shot, server-clock freshness check before the browser navigates.
        with closing(self.db.get_connection()) as c, c:
            return c.execute(f"UPDATE {self.table} SET result=? WHERE id=? AND session=? AND owner=? AND channel=? AND expires>? AND result IS NULL",
                             ('"claimed"', action, session, owner, channel, time.time()+10)).rowcount == 1

    def acknowledge(self, action, session, owner, channel, result):
        with closing(self.db.get_connection()) as c, c:
            return c.execute(f'UPDATE {self.table} SET result=? WHERE id=? AND session=? AND owner=? AND channel=? AND expires>? AND result=\'"claimed"\'',
                             (json.dumps(result), action, session, owner, channel, time.time())).rowcount == 1

    def result(self, action):
        with closing(self.db.get_connection()) as c, c:
            row = c.execute(f'SELECT result FROM {self.table} WHERE id=? AND expires>?', (action, time.time())).fetchone()
        result = json.loads(row[0]) if row and row[0] else None
        return None if result == 'claimed' else result

    def expire(self, session, owner, channel):
        with closing(self.db.get_connection()) as c, c:
            c.execute(f'UPDATE {self.table} SET expires=0 WHERE session=? AND owner=? AND channel=?', (session, owner, channel))


@lru_cache(maxsize=1)
def get_mailbox():
    """One wrapper per worker; connections remain operation-scoped, never shared."""
    return Mailbox()


async def stream_with_frontend(source, bridge):
    """Pump model and tool events while a tool waits for a browser acknowledgement."""
    queue = asyncio.Queue(maxsize=8)
    end = object()
    if bridge:
        bridge.emit = queue.put

    async def produce():
        try:
            try:
                async for event in source:
                    await queue.put(event)
            finally:
                await source.aclose()
        except BaseException as exc:
            if asyncio.current_task().cancelling():
                raise
            await queue.put(exc)
        await queue.put(end)

    task = asyncio.create_task(produce())
    try:
        while True:
            event = await queue.get()
            if event is end:
                break
            if isinstance(event, BaseException):
                raise event
            yield event
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        if bridge:
            bridge.emit = None


class FrontendBridge:
    def __init__(self, session, owner, channel):
        self.session, self.owner, self.channel = session, owner, str(uuid.UUID(channel))
        self.box = get_mailbox()
        self.emit = None
        self.has_actions = False

    async def request(self, payload):
        if self.emit is None:
            raise ValueError('No connected frontend stream; navigation is not available.')
        action = self.box.create(self.session, self.owner, self.channel, payload)
        self.has_actions = True
        await self.emit({'frontend_action': {'action_id': action, **payload}})
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
        if self.has_actions:
            self.box.expire(self.session, self.owner, self.channel)
