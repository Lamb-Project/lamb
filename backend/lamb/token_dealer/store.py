"""LAMB-side records of token-dealer: activities, student keys and the state last applied to the
proxy. Lives in LAMB's own database (migration 33); write rate is low (configuration, issuance,
boundaries). Usage does not live here: see ledger.py.

Works with any object that has get_connection() and table_prefix (LambDatabaseManager in
production, a small stand-in in tests).
"""
import json
import sqlite3
import time
from contextlib import closing

ACTIVITY_FIELDS = ('resource_link_id', 'organization_id', 'context_id', 'context_title', 'activity_name',
                   'owner_email', 'owner_name', 'models_json', 'pool_tokens', 'slot_tokens', 'total_tokens',
                   'schedule_json', 'override', 'status', 'proxy_team_id')
KEY_STATUSES = ('active', 'blocked', 'revoked')


class TokenDealerStore:
    def __init__(self, db):
        self.db = db
        self.tp = db.table_prefix

    def _conn(self):
        c = self.db.get_connection()
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _activity(row):
        if row is None:
            return None
        a = dict(row)
        a['models'] = json.loads(a.pop('models_json') or '[]')
        a['schedule'] = json.loads(a.pop('schedule_json') or '{}')
        return a

    # ── activities ─────────────────────────────────────────────────────
    def create_activity(self, **f):
        f = dict(f)
        f['models_json'] = json.dumps(f.pop('models', []))
        f['schedule_json'] = json.dumps(f.pop('schedule', {}))
        f.setdefault('override', 'auto')
        f.setdefault('status', 'active')
        cols = [k for k in ACTIVITY_FIELDS if k in f]
        now = int(time.time())
        with closing(self._conn()) as c, c:
            cur = c.execute(f"INSERT INTO {self.tp}token_dealer_activities ({', '.join(cols)}, created_at, updated_at) "
                            f"VALUES ({', '.join('?' for _ in cols)}, ?, ?)", [f[k] for k in cols] + [now, now])
            return cur.lastrowid

    def update_activity(self, activity_id, **f):
        f = dict(f)
        if 'models' in f:
            f['models_json'] = json.dumps(f.pop('models'))
        if 'schedule' in f:
            f['schedule_json'] = json.dumps(f.pop('schedule'))
        cols = [k for k in ACTIVITY_FIELDS if k in f]
        if not cols:
            return
        with closing(self._conn()) as c, c:
            c.execute(f"UPDATE {self.tp}token_dealer_activities SET {', '.join(k + ' = ?' for k in cols)}, updated_at = ? "
                      f"WHERE id = ?", [f[k] for k in cols] + [int(time.time()), activity_id])

    def get_activity(self, activity_id):
        with closing(self._conn()) as c:
            return self._activity(c.execute(f"SELECT * FROM {self.tp}token_dealer_activities WHERE id = ?",
                                            (activity_id,)).fetchone())

    def get_activity_by_resource_link(self, resource_link_id):
        with closing(self._conn()) as c:
            return self._activity(c.execute(f"SELECT * FROM {self.tp}token_dealer_activities WHERE resource_link_id = ?",
                                            (resource_link_id,)).fetchone())

    def list_activities(self, organization_id=None, owner_email=None, status='active'):
        q, args = f"SELECT * FROM {self.tp}token_dealer_activities WHERE 1=1", []
        for col, v in (('organization_id', organization_id), ('owner_email', owner_email), ('status', status)):
            if v is not None:
                q += f" AND {col} = ?"
                args.append(v)
        with closing(self._conn()) as c:
            return [self._activity(r) for r in c.execute(q + " ORDER BY id", args).fetchall()]

    # ── keys ───────────────────────────────────────────────────────────
    def create_key(self, activity_id, organization_id, lms_user_id, user_ref, key_prefix, proxy_token,
                   user_email=None, user_name=None, expires_at=None, notice_version=None):
        now = int(time.time())
        with closing(self._conn()) as c, c:
            cur = c.execute(
                f"INSERT INTO {self.tp}token_dealer_keys (activity_id, organization_id, lms_user_id, user_ref, "
                f"user_email, user_name, key_prefix, proxy_token, status, created_at, expires_at, "
                f"notice_version, notice_accepted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)",
                (activity_id, organization_id, lms_user_id, user_ref, user_email, user_name, key_prefix, proxy_token,
                 now, expires_at, notice_version, now if notice_version else None))
            return cur.lastrowid

    def get_key(self, key_id):
        with closing(self._conn()) as c:
            r = c.execute(f"SELECT * FROM {self.tp}token_dealer_keys WHERE id = ?", (key_id,)).fetchone()
            return dict(r) if r else None

    def get_current_key(self, activity_id, lms_user_id):
        """The student's key in this activity that is not revoked, or None."""
        with closing(self._conn()) as c:
            r = c.execute(f"SELECT * FROM {self.tp}token_dealer_keys WHERE activity_id = ? AND lms_user_id = ? "
                          f"AND status != 'revoked' ORDER BY id DESC LIMIT 1", (activity_id, lms_user_id)).fetchone()
            return dict(r) if r else None

    def list_keys(self, activity_id=None, statuses=('active', 'blocked')):
        q, args = f"SELECT * FROM {self.tp}token_dealer_keys WHERE status IN ({', '.join('?' for _ in statuses)})", list(statuses)
        if activity_id is not None:
            q += " AND activity_id = ?"
            args.append(activity_id)
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute(q + " ORDER BY id", args).fetchall()]

    def set_key_status(self, key_id, status, reason=None):
        if status not in KEY_STATUSES:
            raise ValueError(status)
        with closing(self._conn()) as c, c:
            c.execute(f"UPDATE {self.tp}token_dealer_keys SET status = ?, status_reason = ?, "
                      f"revoked_at = CASE WHEN ? = 'revoked' THEN ? ELSE revoked_at END WHERE id = ?",
                      (status, reason, status, int(time.time()), key_id))

    def key_index(self, tokens=None):
        """proxy_token -> (key_id, activity_id, organization_id) for usage attribution: of every key
        ever issued, or only of the given tokens (the worker passes those of the rows it fetched)."""
        q = f"SELECT id, activity_id, organization_id, proxy_token FROM {self.tp}token_dealer_keys"
        with closing(self._conn()) as c:
            if tokens is None:
                rows = c.execute(q).fetchall()
            else:
                tokens, rows = list(tokens), []
                for i in range(0, len(tokens), 500):
                    chunk = tokens[i:i + 500]
                    rows += c.execute(f"{q} WHERE proxy_token IN ({', '.join('?' for _ in chunk)})", chunk).fetchall()
            return {r['proxy_token']: (r['id'], r['activity_id'], r['organization_id']) for r in rows}

    def organization_ids(self):
        """Organizations with at least one LLM-access activity: the proxies the worker reads usage from."""
        with closing(self._conn()) as c:
            return [r[0] for r in c.execute(
                f"SELECT DISTINCT organization_id FROM {self.tp}token_dealer_activities ORDER BY organization_id")]

    def reconcile_candidates(self):
        """The keys whose proxy state may need a change, with the state last applied, in one query:
        every live key of an active activity (timetables move on their own), and the live keys of
        archived activities that the proxy has not yet been told to close. Archived activities whose
        keys are closed cost nothing per cycle, however many accumulate."""
        q = (f"SELECT k.id, k.status, k.proxy_token, k.organization_id, k.activity_id, "
             f"a.status AS activity_status, a.override, a.schedule_json, s.applied "
             f"FROM {self.tp}token_dealer_keys k JOIN {self.tp}token_dealer_activities a ON a.id = k.activity_id "
             f"LEFT JOIN {self.tp}token_dealer_sync_state s ON s.object = 'key:' || k.id "
             f"WHERE k.status IN ('active', 'blocked') "
             f"AND (a.status = 'active' OR s.applied IS NULL OR s.applied != 'closed') ORDER BY k.id")
        schedules, out = {}, []
        with closing(self._conn()) as c:
            for r in c.execute(q):
                aid = r['activity_id']
                if aid not in schedules:
                    schedules[aid] = json.loads(r['schedule_json'] or '{}')
                out.append({'key': {'id': r['id'], 'status': r['status'], 'proxy_token': r['proxy_token']},
                            'activity': {'id': aid, 'organization_id': r['organization_id'], 'status': r['activity_status'],
                                         'override': r['override'], 'schedule': schedules[aid]},
                            'applied': r['applied']})
        return out

    # ── sync state (what the proxy was last told) ──────────────────────
    def get_sync_state(self, obj):
        with closing(self._conn()) as c:
            r = c.execute(f"SELECT * FROM {self.tp}token_dealer_sync_state WHERE object = ?", (obj,)).fetchone()
            return dict(r) if r else None

    def record_applied(self, obj, state):
        now = int(time.time())
        with closing(self._conn()) as c, c:
            c.execute(f"INSERT INTO {self.tp}token_dealer_sync_state (object, desired, applied, applied_at) VALUES (?, ?, ?, ?) "
                      f"ON CONFLICT(object) DO UPDATE SET desired = excluded.desired, applied = excluded.applied, "
                      f"applied_at = excluded.applied_at, last_error = NULL, last_error_at = NULL", (obj, state, state, now))

    def record_error(self, obj, desired, error):
        now = int(time.time())
        with closing(self._conn()) as c, c:
            c.execute(f"INSERT INTO {self.tp}token_dealer_sync_state (object, desired, last_error, last_error_at) VALUES (?, ?, ?, ?) "
                      f"ON CONFLICT(object) DO UPDATE SET desired = excluded.desired, last_error = excluded.last_error, "
                      f"last_error_at = excluded.last_error_at", (obj, desired, str(error)[:300], now))
