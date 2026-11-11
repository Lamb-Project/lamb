"""The token-dealer worker: its own process, never part of the web server.

    python -m lamb.token_dealer.worker            # loops until stopped
    python -m lamb.token_dealer.worker --once     # one reconcile and one ingestion, then exit

Two jobs on one lock (only one worker runs per deployment); intervals in timing.py, from the environment:
  reconcile, every 30 s and right after each minute mark: make the proxy's block state of every
    live key match LAMB's view (timetable, instructor override, key status). Teachers' actions are
    applied at once by the service; this is the timetable driver and the safety net. Per key, not
    per team: a key block takes effect at once on every proxy instance that shares Redis; a team
    block waits out a 60 s auth cache.
  ingest, every 60 s: pull the proxy's spend logs from an overlapping window (600 s by default) and
    add them to the usage ledger, deduplicated on request id. Spend logs reach the proxy's database
    in batches, 10 to 30 s after the request, stamped with the request's start time.
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

from . import timing
from .proxy_client import ProxyError
from .service import desired_state

log = logging.getLogger('lamb.token_dealer.worker')
BOUNDARY = 60          # timetables change only on minute marks: reconcile right after each one
AHEAD = 60             # seconds past now in the query window (proxy clock skew)


class Worker:
    def __init__(self, store, ledger, settings_for, client_for, overlap=None):
        self.store, self.ledger, self.settings_for, self.client_for = store, ledger, settings_for, client_for
        self.overlap = timing.ingest_overlap_seconds() if overlap is None else overlap

    def desired(self, activity, key, now):
        return desired_state(activity, key, now)

    def reconcile(self, now=None):
        """Returns {'opened': n, 'closed': n, 'errors': n}. One query reads only the keys that can need a
        change (store.reconcile_candidates); the proxy is called only for those whose state differs."""
        now = now or datetime.now(timezone.utc)
        out = {'opened': 0, 'closed': 0, 'errors': 0}
        clients = {}
        for c in self.store.reconcile_candidates():
            k, a = c['key'], c['activity']
            want = desired_state(a, k, now)
            if c['applied'] == want:
                continue
            obj, org = f"key:{k['id']}", a['organization_id']
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
        seen_sources = set()
        for org in self.store.organization_ids():
            settings = self.settings_for(org)
            source = settings.proxy_url
            if not source or source in seen_sources:
                continue
            seen_sources.add(source)
            last = self.ledger.cursor(source)
            start = (last if last is not None else now - 3600) - self.overlap
            try:
                rows, newest = [], last or 0
                for row in self.client_for(org).iter_spend_logs(start, now + AHEAD):
                    rows.append(row)
                    try:
                        newest = max(newest, datetime.fromisoformat(str(row['startTime']).replace('Z', '+00:00')).timestamp())
                    except (KeyError, ValueError):
                        pass
                index = self.store.key_index({r.get('api_key') for r in rows if r.get('api_key')})
                new, skipped = self.ledger.record(rows, index)
                out['new'] += new
                out['skipped'] += skipped
                if newest:
                    self.ledger.set_cursor(source, newest)
            except ProxyError as e:
                out['errors'] += 1
                log.warning('ingest from %s failed: %s', source, e)
        return out


def next_boundary(t, step=BOUNDARY):
    """The first minute mark after t: a reconcile there makes timetable changes take effect at once
    instead of up to one cycle late (swarm run, 2026-10-11: openings were up to 9.9 s late)."""
    return (int(t) // step + 1) * step


def _production():
    """Wire the worker to LAMB's database, organization settings and proxies."""
    from . import wiring
    path = wiring.ledger_path()
    return Worker(wiring.store(), wiring.ledger(), wiring.settings_for, wiring.client_for), path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--reconcile-every', type=float, default=timing.reconcile_seconds(),
                    help='seconds between reconciles (TOKEN_DEALER_RECONCILE_SECONDS, default 30)')
    ap.add_argument('--ingest-every', type=float, default=timing.ingest_seconds(),
                    help='seconds between usage ingestions (TOKEN_DEALER_INGEST_SECONDS, default 60)')
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    worker, ledger_path = _production()
    log.info('reconcile every %ss and after each minute mark; ingest every %ss, re-reading %ss',
             args.reconcile_every, args.ingest_every, worker.overlap)
    lock = open(ledger_path + '.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error('another token-dealer worker holds %s.lock; exiting', ledger_path)
        return 1
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    next_r = next_i = next_p = 0.0
    next_b = next_boundary(time.time())
    while not stop:
        t = time.time()
        if t >= next_b + 0.2:
            next_r = t
            next_b = next_boundary(t)
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
        time.sleep(0.2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
