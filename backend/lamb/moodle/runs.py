"""Private resumable runs. A result is immutable; continuing it is idempotent."""
from contextlib import contextmanager
import fcntl
import json
import os
import time
import uuid

from .storage import ensure_private
from .results import ResultStore, TTL_SECONDS, summary
from .forum_activity import TaskLimit, TaskCancelled
from .forum_traversal import initial_state, advance, project, MAX_RUN_CALLS, MAX_STEPS
from .recovery_integrity import retention_record, validate_retention

MAX_RUNS = 4
MAX_RUN_BYTES = 8 * 1024 * 1024


class CheckpointError(RuntimeError):
    pass


class RunStore:
    def __init__(self, results: ResultStore):
        self.results = results
        self.folder = results.folder.parent / 'runs'
        self.binding = results.binding

    @contextmanager
    def lock(self):
        ensure_private(self.folder)
        fd = os.open(self.folder / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('A Moodle forum check is already running. Retry the same continuation after it finishes.') from None
            yield

    def save(self, run):
        try:
            payload = json.dumps(run, ensure_ascii=False).encode()
            if len(payload) > MAX_RUN_BYTES:
                raise ValueError('Moodle run checkpoint exceeds its storage limit')
            dest = self.folder / (str(uuid.UUID(run['id'])) + '.json')
            temp = self.folder / '.checkpoint.tmp'
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as output:
                output.write(payload); output.flush(); os.fsync(output.fileno())
            os.replace(temp, dest)
            fd = os.open(self.folder, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
        except (OSError, ValueError) as exc:
            raise CheckpointError('Moodle progress could not be saved; retry the previous result.') from exc

    def read(self, identity):
        try:
            path = self.folder / (str(uuid.UUID(identity)) + '.json')
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
                payload = source.read(MAX_RUN_BYTES + 1)
            if len(payload) > MAX_RUN_BYTES: raise ValueError()
            run = validate_retention(json.loads(payload))
            if run['binding'] != self.binding or run['expires_at'] <= time.time(): raise ValueError()
            return run
        except (OSError, ValueError, KeyError, TypeError):
            raise PermissionError('Moodle run is unavailable or expired. Start a new news check.') from None

    def create(self, params):
        # Caller owns the lock. Derived run state only; authored files are separate.
        files = sorted(self.folder.glob('*.json'), key=lambda p: p.stat().st_mtime)
        for path in files:
            if path.is_symlink(): raise CheckpointError('Unsafe Moodle run storage')
            saved = retention_record(path, MAX_RUN_BYTES)
            if saved is None:
                # Preserve the corrupt handle in place and count its quota
                # slot. Other work may proceed only within existing limits.
                continue
            if saved['expires_at'] <= time.time():
                path.unlink(); files = [p for p in files if p != path]
        if len(files) >= MAX_RUNS:
            raise ValueError('Moodle run storage is full of live recovery handles or unreadable records; use an existing run, wait for expiry, or ask an administrator to inspect preserved unreadable records')
        run = {'id': str(uuid.uuid4()), 'binding': self.binding,
            'expires_at': time.time() + TTL_SECONDS, 'state': initial_state(params),
            'last_result': None, 'next_results': {}, 'working': None}
        self.save(run)
        return run

    def listing(self):
        ensure_private(self.folder)
        items = []
        for path in self.folder.glob('*.json'):
            try: run = self.read(path.stem)
            except PermissionError: continue
            if not run['last_result']: continue
            state = run['state']
            items.append({'run_id': run['id'], 'result_id': run['last_result'],
                'started_at': state['snapshot']['as_of'], 'finished': state['done'] and run['working'] is None,
                'steps_used': state['steps'],
                'continue_command': None if state['done'] and run['working'] is None else f"moodle continue {run['last_result']}"})
        return {'runs': sorted(items, key=lambda r: r['started_at'], reverse=True),
            'meaning': 'Private recent runs for this connection. Use these handles to recover after Stop or a lost response.'}

    def execute(self, client, owner_id, *, params=None, result_id=None, progress=None):
        with self.lock():
            client.checkpoint()
            if result_id:
                prior = self.results.read(result_id)
                if not prior.get('run'):
                    raise ValueError('This older result cannot be continued. Start a new news check.')
                run = self.read(prior['run']['id'])
                # Permission evidence from the current run is rechecked even for
                # an idempotent retry, before returning any saved source excerpt.
                from .scope import MoodleScope
                from .forum_traversal import require_retained_access
                if result_id in run['next_results']:
                    require_retained_access(MoodleScope(client, owner_id), run['state'])
                    identity = run['next_results'][result_id]
                    client.checkpoint()
                    snapshot = self.results.read(identity)
                    client.checkpoint()
                    return summary(identity, snapshot)
                if result_id != run['last_result']:
                    raise ValueError('Use the latest result from moodle runs to continue this check.')
                if run['state']['done']:
                    require_retained_access(MoodleScope(client, owner_id), run['state'])
                    client.checkpoint()
                    if run['working'] is not None:
                        identity, snapshot = self._publish(run, client, run['state'].get('stop_reason'), result_id)
                        client.checkpoint()
                        return summary(identity, snapshot)
                    return summary(result_id, prior)
            else:
                run = self.create(params)
                # A recovery handle exists before remote traversal starts. It is
                # listed by moodle runs if the first response is interrupted.
                snapshot = self._snapshot(run, client, 'not_started')
                identity = self.results.save(snapshot)
                run['last_result'] = identity
                self.save(run)
                result_id = identity
            state = run['state']
            if run['working'] is None:
                state.pop('stop_reason', None)
                state['steps'] += 1
                run['working'] = result_id
                self.save(run)
            elif run['working'] != result_id:
                raise ValueError('Use the latest result from moodle runs to recover this check.')
            reason = None
            # Count and persist requests before issuing them, including failures.
            # Requests spent on current-run access checks above count as well.
            state['calls'] += client.calls
            def before_request():
                if state['calls'] >= MAX_RUN_CALLS:
                    raise TaskLimit('run_request_limit')
                state['calls'] += 1
                self.save(run)
            client.before_request = before_request
            try:
                advance(client, owner_id, state, save=lambda: self.save(run), progress=progress)
                client.checkpoint()
            except TaskLimit as exc:
                reason = str(exc)
                if reason.startswith('run_') or reason == 'response_size_limit' or state['steps'] >= MAX_STEPS:
                    state['done'] = True
                    if not reason.startswith('run_') and reason != 'response_size_limit': reason = 'run_step_limit'
            except TaskCancelled:
                reason = None if state['done'] else 'interrupted'
                if state['steps'] >= MAX_STEPS: state['done'] = True
                client.revalidate()
                self._publish(run, client, reason, result_id)
                raise
            # Permission errors are deliberately not converted to partial success.
            # Persisted state remains bound to the old connection and cannot leak.
            finally:
                client.before_request = None
            state['stop_reason'] = reason
            client.revalidate()
            identity, snapshot = self._publish(run, client, reason, result_id)
            client.checkpoint()
            return summary(identity, snapshot)

    def _snapshot(self, run, client, reason):
        snapshot = project(run['state'], client, reason)
        snapshot['run'] = {'id': run['id'], 'step': run['state']['steps'],
            'step_limit': MAX_STEPS, 'can_continue': not run['state']['done'],
            'expires_at': run['expires_at']}
        return snapshot

    def _publish(self, run, client, reason, previous):
        # Persist progress before publishing. A crash between result creation and
        # the final atomic state replacement leaves only an unused immutable file;
        # a retry resumes saved progress and cannot duplicate retained post IDs.
        run['state']['stop_reason'] = reason
        self.save(run)
        snapshot = self._snapshot(run, client, reason)
        identity = self.results.save(snapshot)
        run['next_results'][previous] = identity
        run['last_result'] = identity
        run['working'] = None
        self.save(run)
        return identity, snapshot
