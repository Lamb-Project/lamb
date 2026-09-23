"""Owner-scoped housekeeping for derived data, not teaching resources.

Locks are acquired in run -> evidence order, matching RunStore.execute. Import
cleanup uses the delivery lock. Unknown/corrupt references fail closed. The
periodic sweep is independent of user activity and does not read source bodies
into responses or logs.
"""
import asyncio
import logging
import os
from pathlib import Path
import time

from lamb.private_storage import data_root, file_lock, read_json, atomic_json, sync_directory, private_directory
from lamb.moodle.import_store import ImportStore, MAX_OWNER_BYTES, MAX_RECORDS, CATEGORIES

logger = logging.getLogger(__name__)
TEMP_TTL = 3600
SWEEP_INTERVAL = 300


def files(folder, pattern='*.json', limit=MAX_RECORDS):
    folder = private_directory(folder)
    result = []
    for path in folder.glob(pattern):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Unsafe private storage entry')
        result.append(path)
        if len(result) > limit:
            raise ValueError('Private storage inventory exceeds its safety bound; administrator review required')
    return result


def run_references(runs, now):
    """All idempotent retries as well as the latest continuation remain usable."""
    protected = set()
    for run in runs:
        if run['expires_at'] > now:
            protected.update(filter(None, (run.get('last_result'), run.get('working'))))
            protected.update(run.get('next_results', {}))
            protected.update(run.get('next_results', {}).values())
    return protected


class OwnerStorage:
    def __init__(self, organization_id, owner_id, *, root=None):
        if any(type(i) is not int or i <= 0 for i in (organization_id, owner_id)):
            raise ValueError('A positive organization and owner id are required')
        self.root = Path(root) if root is not None else data_root()
        self.org, self.owner = organization_id, owner_id
        self.moodle = self.root / 'moodle'
        self.tasks = self.moodle / str(self.org) / str(self.owner)

    def imports(self):
        return ImportStore(self.org, self.owner, self.moodle)

    def inspect(self):
        from lamb.moodle.charts import MAX_CHARTS,MAX_CALENDAR_BYTES
        stores = {
            'aac_results': (self.root / 'aac_results' / str(self.org) / str(self.owner), 32 * 1024 * 1024, '24h; oldest unpinned result may be evicted at quota'),
            'evidence': (self.tasks / 'results', 16 * 4 * 1024 * 1024, '24h; live run references protected from quota eviction'),
            'runs': (self.tasks / 'runs', 4 * 8 * 1024 * 1024, '24h; live runs not evicted'),
            'completion_runs': (self.tasks / 'completion-runs', 4 * 1024 * 1024, '24h; private learner cursors; live runs not evicted'),
            'charts': (self.moodle / 'charts' / str(self.org) / str(self.owner), MAX_CHARTS * MAX_CALENDAR_BYTES,
                       'durable; no automatic expiry; 100 records; 128 KiB per chart, 512 KiB per deadline calendar'),
            'course_cache': (self.tasks / 'course-cache', None, 'rebuildable; retained until explicit source refresh'),
        }
        inventory = {}
        for name, (folder, cap, policy) in stores.items():
            with file_lock(folder, blocking=False):
                entries = files(folder)
                inventory[name] = {'bytes': sum(p.stat().st_size for p in entries), 'records': len(entries),
                                   'quota_bytes': cap, 'policy': policy}
        store = self.imports()
        with store.lock():
            categories = {cat: files(store.root / cat) for cat in sorted(CATEGORIES)}
            inventory['imports'] = {'bytes': sum(p.stat().st_size for entries in categories.values() for p in entries),
                'records': sum(map(len, categories.values())), 'quota_bytes': MAX_OWNER_BYTES,
                'record_limit': MAX_RECORDS, 'categories': {cat: len(entries) for cat, entries in categories.items()},
                'policy': 'unapproved reviews 1h; receipts, revisions and approved batches durable'}
        return {'organization_id': self.org, 'owner_id': self.owner, 'stores': inventory,
                'notice': 'Private copies only. Cleanup never deletes a KB, uploaded document, transcript or learning scenario.'}

    def clean(self, *, now=None):
        now = time.time() if now is None else now
        result = {'removed_records': 0, 'reclaimed_bytes': 0, 'compacted_reviews': 0}

        def remove(path):
            size = path.stat().st_size
            path.unlink()
            sync_directory(path.parent)
            result['removed_records'] += 1
            result['reclaimed_bytes'] += size

        def temporaries(folder):
            for pattern in ('.pending-*', '.checkpoint.tmp', '.write-*'):
                for path in files(folder, pattern):
                    if path.stat().st_mtime + TEMP_TTL <= now:
                        remove(path)

        from lamb.aac.result_store import MAX_FILE_BYTES
        folder = self.root / 'aac_results' / str(self.org) / str(self.owner)
        with file_lock(folder, blocking=False):
            for path in files(folder):
                envelope = read_json(path, MAX_FILE_BYTES)
                if envelope['expires_at'] <= now:
                    remove(path)
            temporaries(folder)

        from lamb.moodle.runs import MAX_RUN_BYTES
        from lamb.moodle.results import MAX_RESULT_BYTES
        with file_lock(self.tasks / 'runs', blocking=False):
            run_files = files(self.tasks / 'runs')
            runs = [read_json(path, MAX_RUN_BYTES) for path in run_files]
            protected = run_references(runs, now)
            with file_lock(self.tasks / 'results', blocking=False):
                for path in files(self.tasks / 'results'):
                    envelope = read_json(path, MAX_RESULT_BYTES)
                    if envelope['expires_at'] <= now and path.stem not in protected:
                        remove(path)
                temporaries(self.tasks / 'results')
            for path, run in zip(run_files, runs):
                if run['expires_at'] <= now:
                    remove(path)
            temporaries(self.tasks / 'runs')

        # Chart snapshots are durable, but interrupted atomic writes are not.
        # Never apply an expiry policy to the published JSON files here.
        chart_folder = self.moodle / 'charts' / str(self.org) / str(self.owner)
        with file_lock(chart_folder, blocking=False):
            temporaries(chart_folder)

        from lamb.moodle.analytics.checkpoints import MAX_CHECKPOINT_BYTES
        import math
        folder = self.tasks / 'completion-runs'
        with file_lock(folder, blocking=False):
            records = [(path, read_json(path, MAX_CHECKPOINT_BYTES)) for path in files(folder)]
            for _, record in records:
                expiry = record.get('expires_at')
                if type(expiry) not in (int, float) or not math.isfinite(expiry):
                    raise ValueError('Cannot verify completion checkpoint expiry')
            for path, record in records:
                if record['expires_at'] <= now:
                    remove(path)
            temporaries(folder)

        store = self.imports()
        with store.lock():
            reviews = {path.stem: store.get('reviews', path.stem) for path in files(store.root / 'reviews')}
            protected = self._protected_reviews(store, reviews, now=now)
            for key, ticket in reviews.items():
                path = store.path('reviews', key)
                if key not in protected and ticket['review']['expires_at'] <= now:
                    remove(path)
                elif 'content' in ticket or 'originals' in ticket:
                    # Legacy approvals retain all hashes, session/source binding,
                    # outcome markers and handles. Confirm always rematerializes.
                    old = path.stat().st_size
                    atomic_json(path, {k: v for k, v in ticket.items() if k not in {'content', 'originals'}})
                    result['reclaimed_bytes'] += max(0, old - path.stat().st_size)
                    result['compacted_reviews'] += 1
            for cat in CATEGORIES:
                temporaries(store.root / cat)
        return result

    @staticmethod
    def _protected_reviews(store, reviews, *, now=None):
        now = time.time() if now is None else now
        protected = set()
        for key, ticket in reviews.items():
            if ticket.get('approved') or ticket.get('import_id') or ticket.get('failed_result'):
                protected.add(key)
                protected.update(ticket.get('children', []))
            # Keep children for the entire parent's approval window too.
            elif ticket['review']['expires_at'] > now:
                protected.update(ticket.get('children', []))
        for cat in ('receipts', 'versions'):
            for path in files(store.root / cat):
                receipt = store.get(cat, path.stem)
                key = receipt.get('review', {}).get('review_id')
                if key:
                    protected.add(key)
        return protected

    def discard_review(self, identity):
        """Owner explicitly cancels a preparation; approved/attempted work survives."""
        return self.discard_import_review(self.imports(), identity)

    @staticmethod
    def discard_import_review(store, identity):
        with store.lock():
            reviews = {path.stem: store.get('reviews', path.stem) for path in files(store.root / 'reviews')}
            ticket = store.get('reviews', identity)
            if identity in OwnerStorage._protected_reviews(store, reviews):
                raise ValueError('Review belongs to approved, attempted or parent-protected work; inspect its recovery receipt')
            candidates = [identity, *ticket.get('children', [])]
            # Recompute without this parent so only its exclusive, unused children go.
            protected = OwnerStorage._protected_reviews(store, {k: v for k, v in reviews.items() if k != identity})
            removed = 0
            for key in candidates:
                if key in protected:
                    continue
                path = store.path('reviews', key)
                if path.exists():
                    path.unlink()
                    removed += 1
            sync_directory(store.root / 'reviews')
            return {'discarded_reviews': removed, 'notice': 'Nothing was imported. Review again before approving.'}

    def purge_originals(self, identity):
        """Explicitly discard private binary copies, never recovery metadata.

        This is intentionally unavailable for uncertain or in-progress outcomes.
        Destination documents and KB files, citation hashes, receipt identities,
        historical revisions and duplicate-prevention markers are not deleted.
        """
        store = self.imports()
        with store.lock():
            receipt = store.get('receipts', identity)
            rows = [('receipts', identity, receipt)]
            rows.extend(('versions', path.stem, store.get('versions', path.stem))
                        for path in files(store.root / 'versions'))
            rows = [(cat, key, row) for cat, key, row in rows if row.get('import_id') == identity]
            if not rows or receipt.get('import_id') != identity or any(
                    row.get('status') not in {'completed', 'failed'} for _, _, row in rows):
                raise ValueError('Import has an active or uncertain outcome; preserve its originals and inspect the destination first')
            reclaimed = 0
            for cat, key, row in rows:
                if not any(k in row for k in ('content', 'originals')):
                    continue
                path = store.path(cat, key)
                before = path.stat().st_size
                pruned = {k: v for k, v in row.items() if k not in {'content', 'originals'}}
                pruned['private_originals_purged_at'] = int(time.time())
                atomic_json(path, pruned)
                reclaimed += max(0, before - path.stat().st_size)
            return {'import_id': identity, 'reclaimed_bytes': reclaimed,
                    'notice': 'Private binary copies purged. Imported teaching resources, receipts, revisions and citation hashes were retained. Historical original bytes cannot be recovered from this store.'}


def owners(root):
    """Streaming discovery; never follow links or walk arbitrary document trees."""
    for base in (root / 'aac_results', root / 'moodle', root / 'moodle' / 'imports'):
        if not base.exists():
            continue
        if base.is_symlink():
            raise ValueError('Unsafe private storage root')
        with os.scandir(base) as organizations:
            for org in organizations:
                if not org.name.isdecimal() or int(org.name) <= 0 or not org.is_dir(follow_symlinks=False):
                    continue
                with os.scandir(org.path) as users:
                    for owner in users:
                        if owner.name.isdecimal() and int(owner.name) > 0 and owner.is_dir(follow_symlinks=False):
                            yield int(org.name), int(owner.name)


def sweep_batch(iterator, root, limit=16):
    for _ in range(limit):
        identity = next(iterator, None)
        if identity is None:
            return True
        try:
            OwnerStorage(*identity, root=root).clean()
        except (OSError, ValueError, PermissionError, KeyError, TypeError):
            # Do not log source content, credentials, names or malformed JSON.
            logger.warning('Private-storage cleanup skipped an owner: busy, unsafe or invalid storage')
    return False


async def cleanup_loop(root):
    while True:
        iterator = owners(root)
        try:
            while True:
                worker = asyncio.create_task(asyncio.to_thread(sweep_batch, iterator, root))
                try:
                    finished = await asyncio.shield(worker)
                except asyncio.CancelledError:
                    # A cancelled to_thread await does not stop its thread. Let
                    # the bounded batch release file locks before closing it.
                    await worker
                    raise
                if finished:
                    break
                await asyncio.sleep(1)
        except (OSError, ValueError):
            logger.warning('Private-storage sweep could not enumerate its configured root')
        finally:
            iterator.close()
        await asyncio.sleep(SWEEP_INTERVAL)
