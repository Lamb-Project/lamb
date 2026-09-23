"""Private forum checkpoints. Storage binding does not establish Moodle access.

Executors must revalidate current scope/population before using this state or
returning any result. This module performs no network calls or publication.
"""
from copy import deepcopy
from lamb.private_storage import sync_directory
from .checkpoints import CompletionCheckpoints
from .forum_state import advance_cursor

MAX_FORUM_CHECKPOINT_BYTES = 4 * 1024 * 1024


class ForumCheckpoints(CompletionCheckpoints):
    namespace = 'forum-analytics-runs'
    max_bytes = MAX_FORUM_CHECKPOINT_BYTES

    def acknowledge_page(self, identity, after_id, page, *, expected_revision):
        """Atomically acknowledge one validated page; recover lost acknowledgement.

An identical already-saved page returns its durable revision without writing.
A stale writer with different progress must reload, not overwrite later state.
"""
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('Invalid forum checkpoint revision')
        with self.execution_lock():
            record = self.read(identity)
            state = deepcopy(record['state'])
            cursor = advance_cursor(state['cursor'], after_id, page)
            if cursor == state['cursor']:
                if expected_revision > record['revision']:
                    raise ValueError('Forum checkpoint revision is in the future')
                # A prior writer may have renamed successfully and lost its
                # directory fsync acknowledgement. Finish durability on retry.
                try:
                    sync_directory(self.folder)
                except OSError:
                    raise ValueError('Forum checkpoint durability could not be confirmed; retry the saved page') from None
                return record
            state['cursor'] = cursor
            return self.replace(identity, state, expected_revision=expected_revision)
