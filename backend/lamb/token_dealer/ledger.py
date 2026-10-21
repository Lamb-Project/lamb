"""Usage ledger: what the proxy served and refused, aggregated per key, slot and model.

Kept in its own SQLite file, not LAMB's database: at classroom scale the proxy logs hundreds of
requests a second, and LAMB's database must not compete for its write lock. LAMB's screens need
totals, so the ledger keeps totals plus the request ids of the last day for deduplication.
"""
import sqlite3
import time
from contextlib import closing
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_slot (
  key_id INTEGER NOT NULL, activity_id INTEGER NOT NULL, organization_id INTEGER NOT NULL,
  slot_start INTEGER NOT NULL, model TEXT NOT NULL,
  requests_ok INTEGER NOT NULL DEFAULT 0, requests_refused INTEGER NOT NULL DEFAULT 0,
  prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (key_id, slot_start, model));
CREATE INDEX IF NOT EXISTS idx_usage_slot_activity ON usage_slot (activity_id, slot_start);
CREATE TABLE IF NOT EXISTS seen_request (request_id TEXT PRIMARY KEY, seen_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS ingest_cursor (source TEXT PRIMARY KEY, last_start REAL NOT NULL, updated_at INTEGER NOT NULL);
"""


def _epoch(ts):
    if isinstance(ts, (int, float)):
        return float(ts)
    return datetime.fromisoformat(str(ts).replace('Z', '+00:00')).timestamp()


class UsageLedger:
    def __init__(self, path, slot_seconds=600):
        self.path, self.slot = str(path), slot_seconds
        with closing(self._conn()) as c, c:
            c.executescript(SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=10.0)
        c.execute('PRAGMA journal_mode=WAL')
        c.row_factory = sqlite3.Row
        return c

    def record(self, rows, key_index):
        """Add spend-log rows; returns (new, skipped). Rows already seen and rows of keys that are
        not token-dealer keys are skipped. Refused requests count as refused, with no tokens."""
        new = skipped = 0
        now = int(time.time())
        ids = list({row.get('request_id') for row in rows if row.get('request_id')})
        with closing(self._conn()) as c, c:
            # The overlapping window re-reads most rows on every pass: look them up in batches.
            seen = set()
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                seen.update(r[0] for r in c.execute(
                    f"SELECT request_id FROM seen_request WHERE request_id IN ({', '.join('?' for _ in chunk)})", chunk))
            for row in rows:
                rid = row.get('request_id')
                if not rid or rid in seen:
                    skipped += 1
                    continue
                seen.add(rid)
                c.execute('INSERT INTO seen_request VALUES (?, ?)', (rid, now))
                hit = key_index.get(row.get('api_key'))
                if not hit:
                    skipped += 1
                    continue
                key_id, activity_id, org_id = hit
                ok = row.get('status', 'success') == 'success'
                slot = int(_epoch(row['startTime']) // self.slot * self.slot)
                c.execute(
                    'INSERT INTO usage_slot VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(key_id, slot_start, model) DO UPDATE SET '
                    'requests_ok = requests_ok + excluded.requests_ok, requests_refused = requests_refused + excluded.requests_refused, '
                    'prompt_tokens = prompt_tokens + excluded.prompt_tokens, completion_tokens = completion_tokens + excluded.completion_tokens',
                    (key_id, activity_id, org_id, slot, row.get('model_group') or row.get('model') or '',
                     int(ok), int(not ok), int(row.get('prompt_tokens') or 0) if ok else 0,
                     int(row.get('completion_tokens') or 0) if ok else 0))
                new += 1
        return new, skipped

    def cursor(self, source):
        with closing(self._conn()) as c:
            r = c.execute('SELECT last_start FROM ingest_cursor WHERE source = ?', (source,)).fetchone()
            return r['last_start'] if r else None

    def set_cursor(self, source, last_start):
        with closing(self._conn()) as c, c:
            c.execute('INSERT INTO ingest_cursor VALUES (?, ?, ?) ON CONFLICT(source) DO UPDATE SET '
                      'last_start = MAX(last_start, excluded.last_start), updated_at = excluded.updated_at',
                      (source, last_start, int(time.time())))

    def prune_seen(self, older_than_seconds=86400):
        with closing(self._conn()) as c, c:
            return c.execute('DELETE FROM seen_request WHERE seen_at < ?', (int(time.time()) - older_than_seconds,)).rowcount

    def totals(self, key_ids=None, activity_id=None, since=None):
        """Per-key totals: {key_id: {requests_ok, requests_refused, prompt_tokens, completion_tokens, tokens}}."""
        q, args = ('SELECT key_id, SUM(requests_ok) ok, SUM(requests_refused) refused, SUM(prompt_tokens) p, '
                   'SUM(completion_tokens) cpl FROM usage_slot WHERE 1=1'), []
        if activity_id is not None:
            q += ' AND activity_id = ?'
            args.append(activity_id)
        if key_ids is not None:
            q += f" AND key_id IN ({', '.join('?' for _ in key_ids)})"
            args += list(key_ids)
        if since is not None:
            q += ' AND slot_start >= ?'
            args.append(int(since))
        with closing(self._conn()) as c:
            return {r['key_id']: {'requests_ok': r['ok'], 'requests_refused': r['refused'], 'prompt_tokens': r['p'],
                                  'completion_tokens': r['cpl'], 'tokens': r['p'] + r['cpl']}
                    for r in c.execute(q + ' GROUP BY key_id', args)}

    def slots(self, activity_id, since=None):
        """Per-slot totals for one activity: [(slot_start, requests_ok, requests_refused, tokens)]."""
        q, args = ('SELECT slot_start, SUM(requests_ok), SUM(requests_refused), SUM(prompt_tokens + completion_tokens) '
                   'FROM usage_slot WHERE activity_id = ?'), [activity_id]
        if since is not None:
            q += ' AND slot_start >= ?'
            args.append(int(since))
        with closing(self._conn()) as c:
            return [tuple(r) for r in c.execute(q + ' GROUP BY slot_start ORDER BY slot_start', args)]
