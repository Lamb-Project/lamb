"""The token-dealer worker: its own process, never part of the web server.

    python -m lamb.token_dealer.worker            # loops until stopped
    python -m lamb.token_dealer.worker --once     # one reconcile and one ingestion, then exit

Two jobs on one lock (only one worker runs per deployment):
  reconcile, every 10 s: make the proxy's block state of every key match LAMB's view
    (timetable, instructor override, key status). Per key, not per team: a key block takes effect
    at once on every proxy instance that shares Redis; a team block waits out a 60 s auth cache.
  ingest, every 20 s: pull the proxy's spend logs from a 3-minute overlapping window and add them
    to the usage ledger, deduplicated on request id. Spend logs reach the proxy's database in
    batches, 10 to 30 s after the request.
It can run on another machine than LAMB's web server as long as it reaches LAMB's database and
the proxy; the ledger file is its own.
"""
import argparse
import fcntl
import logging
import os
import signal
import time
from datetime import datetime, timezone

from . import schedule as sched
from .proxy_client import ProxyError

log = logging.getLogger('lamb.token_dealer.worker')
OVERLAP = 180          # seconds re-read on every ingestion
AHEAD = 60             # seconds past now in the query window (proxy clock skew)


class Worker:
    def __init__(self, store, ledger, settings_for, client_for):
        self.store, self.ledger, self.settings_for, self.client_for = store, ledger, settings_for, client_for

    def desired(self, activity, key, now):
        if key['status'] != 'active' or activity['status'] != 'active':
            return 'closed'
        return 'open' if sched.is_open(activity['schedule'], activity['override'], now) else 'closed'

    def reconcile(self, now=None):
        """Returns {'opened': n, 'closed': n, 'errors': n}."""
        now = now or datetime.now(timezone.utc)
        out = {'opened': 0, 'closed': 0, 'errors': 0}
        clients = {}
        for a in self.store.list_activities(status=None):
            keys = self.store.list_keys(activity_id=a['id'])
            if not keys:
                continue
            for k in keys:
                want = self.desired(a, k, now)
                obj = f"key:{k['id']}"
                state = self.store.get_sync_state(obj)
                if state and state['applied'] == want:
                    continue
                org = a['organization_id']
                try:
                    client = clients.get(org) or clients.setdefault(org, self.client_for(org))
                    (client.unblock_key if want == 'open' else client.block_key)(k['proxy_token'])
                    self.store.record_applied(obj, want)
                    out['opened' if want == 'open' else 'closed'] += 1
                except ProxyError as e:
                    self.store.record_error(obj, want, e)
                    out['errors'] += 1
                    log.warning('reconcile %s -> %s failed: %s', obj, want, e)
        return out

    def ingest(self, now=None):
        """Returns {'new': n, 'skipped': n, 'errors': n} over every proxy in use."""
        now = time.time() if now is None else now
        out = {'new': 0, 'skipped': 0, 'errors': 0}
        index = self.store.key_index()
        orgs = sorted({a['organization_id'] for a in self.store.list_activities(status=None)})
        seen_sources = set()
        for org in orgs:
            settings = self.settings_for(org)
            source = settings.proxy_url
            if not source or source in seen_sources:
                continue
            seen_sources.add(source)
            last = self.ledger.cursor(source)
            start = (last if last is not None else now - 3600) - OVERLAP
            try:
                rows, newest = [], last or 0
                for row in self.client_for(org).iter_spend_logs(start, now + AHEAD):
                    rows.append(row)
                    try:
                        newest = max(newest, datetime.fromisoformat(str(row['startTime']).replace('Z', '+00:00')).timestamp())
                    except (KeyError, ValueError):
                        pass
                new, skipped = self.ledger.record(rows, index)
                out['new'] += new
                out['skipped'] += skipped
                if newest:
                    self.ledger.set_cursor(source, newest)
            except ProxyError as e:
                out['errors'] += 1
                log.warning('ingest from %s failed: %s', source, e)
        return out


def _production():
    """Wire the worker to LAMB's database, organization settings and proxies."""
    from lamb.database_manager import LambDatabaseManager
    import config
    from .ledger import UsageLedger
    from .proxy_client import ProxyClient
    from .settings import from_org_config
    from .store import TokenDealerStore

    db = LambDatabaseManager()
    store = TokenDealerStore(db)

    def settings_for(org_id):
        org = db.get_organization_by_id(org_id) or {}
        return from_org_config(org.get('config') or {})

    def client_for(org_id):
        s = settings_for(org_id)
        return ProxyClient(s.proxy_url, s.proxy_admin_key)

    path = os.environ.get('TOKEN_DEALER_LEDGER_PATH') or os.path.join(config.LAMB_DB_PATH, 'token_dealer_usage.db')
    return Worker(store, UsageLedger(path), settings_for, client_for), path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--reconcile-every', type=float, default=10)
    ap.add_argument('--ingest-every', type=float, default=20)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    worker, ledger_path = _production()
    lock = open(ledger_path + '.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error('another token-dealer worker holds %s.lock; exiting', ledger_path)
        return 1
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    next_r = next_i = next_p = 0.0
    while not stop:
        t = time.time()
        if t >= next_r:
            r = worker.reconcile()
            if r['opened'] or r['closed'] or r['errors']:
                log.info('reconcile %s', r)
            next_r = t + args.reconcile_every
        if t >= next_i:
            i = worker.ingest()
            if i['new'] or i['errors']:
                log.info('ingest %s', i)
            next_i = t + args.ingest_every
        if t >= next_p:
            worker.ledger.prune_seen()
            next_p = t + 3600
        if args.once:
            break
        time.sleep(0.5)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
