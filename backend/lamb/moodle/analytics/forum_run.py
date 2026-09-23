"""Private bounded forum collection. Never expose this learner-bearing state."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .client import FORUM_POSTS_FUNCTION
from .forum_context import forum_context
from .forum_participation import MAX_POSTS, _integer, summarize_forums
from .forum_state import initial_cursor, advance_cursor, normalized_thread
from ..forum_activity import TaskLimit

# Includes repeated, exhausted 1,000-discussion inventory checks per step.
MAX_RUN_CALLS = 16000
MAX_RUN_STEPS = 300
PAGES_PER_STEP = 5


def _now():
    return datetime.now(timezone.utc)


def start(store, course_id, forum_id, *, since, until, group_id=0,
          language='en', tz='UTC'):
    initial_cursor(course_id, forum_id, 1, group_id)
    for value in (since, until):
        _integer(value)
    if not since < until <= int(_now().timestamp()) or until-since > 366*86400+3600:
        raise ValueError('Invalid bounded forum window')
    ZoneInfo(tz)
    if language not in {'en', 'es', 'ca', 'eu'}:
        raise ValueError('Invalid forum language')
    return store.create({'scope': {'course_id': course_id, 'forum_id': forum_id, 'group_id': group_id},
        'since': since, 'until': until, 'language': language, 'tz': tz,
        'started_at': _now().isoformat(), 'context': None, 'cursor': None,
        'threads': [], 'posts': 0, 'pages': 0, 'calls': 0, 'steps': 0, 'done': False})


def advance(store, client, owner_id, identity):
    """Acknowledge each page atomically; revalidate authority on every resume.

    Stable inventory does not freeze post edits. Observations are explicitly
    non-atomic, and collection completion is not historical completeness.
    """
    with store.execution_lock():
        record = store.read(identity)
        state = record['state']
        if client.before_request is not None:
            raise ValueError('Forum executor cannot replace an existing request guard')
        if state['steps'] >= MAX_RUN_STEPS:
            raise TaskLimit('forum_run_step_limit')

        def save():
            nonlocal record
            record = store.replace(identity, state, expected_revision=record['revision'])

        def before_request():
            if state['calls'] >= MAX_RUN_CALLS:
                raise TaskLimit('forum_run_request_limit')
            state['calls'] += 1
            save()

        def verify():
            client.checkpoint()
            current = forum_context(client, owner_id, state['scope'])
            if state['context'] is not None and current['fingerprint'] != state['context']['fingerprint']:
                raise ValueError('Forum population or inventory changed; start a new run')
            return current

        state['steps'] += 1
        save()
        client.before_request = before_request
        try:
            current = verify()
            if state['context'] is None:
                state['context'] = current
                save()
            if not state['done']:
                target = state['pages'] + PAGES_PER_STEP
                if 'active_public_step' in state:
                    if 'public_target_pages' not in state:
                        state['public_target_pages'] = target
                        save()
                    target = state['public_target_pages']
                inventory = state['context']['discussions']
                while len(state['threads']) < len(inventory) and state['pages'] < target:
                    scope = state['scope']
                    discussion = inventory[len(state['threads'])]
                    cursor = state['cursor'] or initial_cursor(scope['course_id'], scope['forum_id'],
                        discussion['discussion_id'], scope['group_id'])
                    client.checkpoint()
                    page = client.call(FORUM_POSTS_FUNCTION, courseid=scope['course_id'],
                        forumid=scope['forum_id'], discussionid=cursor['discussionid'],
                        groupid=scope['group_id'], afterid=cursor['afterid'],
                        throughid=cursor['throughid'] or 0, limit=200)
                    updated = advance_cursor(cursor, cursor['afterid'], page)
                    added = len(updated['records']) - len(cursor['records'])
                    if state['posts'] + added > MAX_POSTS:
                        raise ValueError('Forum post bound exceeded')
                    thread = normalized_thread(updated) if updated['done'] else None
                    if thread is not None:
                        roots = [p['id'] for p in thread['posts'] if p['parent_id'] is None]
                        if roots and roots != [discussion['root_post_id']]:
                            raise ValueError('Forum root differs from inventory')
                        state['threads'].append(thread)
                    state['cursor'] = None if thread is not None else updated
                    state['posts'] += added
                    state['pages'] += 1
                    state['last_source_at'] = max(state.get('last_source_at', 0), updated['last_collected_at'])
                    save()
                verify()
                if len(state['threads']) == len(inventory):
                    completed = _now()
                    as_of = int(completed.timestamp())
                    if state.get('last_source_at', 0) > as_of:
                        raise ValueError('Forum source clock exceeds collector clock')
                    summarize_forums(state['threads'], state['context']['students'],
                        since=state['since'], until=state['until'], as_of=as_of,
                        timezone=state['tz'], inventory_complete=True)
                    state.update(done=True, completed_at=completed.isoformat(), as_of=as_of,
                                 atomic_snapshot=False)
                if 'active_public_step' in state:
                    state['finished_public_step'] = state['active_public_step']
                save()
            client.checkpoint()
            return record
        finally:
            client.before_request = None


def publish(store, runtime, client, identity, *, recipe):
    """Reserve immutable per-recipe snapshots before idempotent chart writes."""
    import uuid
    from .forum_snapshot import snapshot, RECIPES
    from .recipes import result_page
    from ..charts import ChartStore
    if recipe not in RECIPES:
        raise ValueError('Invalid forum recipe')
    with store.execution_lock():
        client.checkpoint()
        record = store.read(identity)
        state = record['state']
        if not state['done']:
            raise ValueError('Forum collection is not finished')
        current = runtime.result_binding()
        if (store.binding['organization_id'] != runtime.store.organization_id or
                store.binding['owner_id'] != runtime.store.owner_id or
                any(store.binding[key] != current.get(key) for key in ('generation','base_url','moodle_user_id'))):
            raise PermissionError('Forum run belongs to another connection')
        publications = state.setdefault('publications', {})
        publication = publications.get(recipe)
        if publication is None:
            data = snapshot(state,identity,recipe=recipe)
            binding = dict(current,course_id=state['scope']['course_id'],forum_scopes=data['forum_scopes'])
            runtime.validate_result_binding(binding,'moodle.analytics.run')
            publication = dict(id=str(uuid.uuid4()),snapshot=data,binding=binding)
            publications[recipe] = publication
            record = store.replace(identity,state,expected_revision=record['revision'])
        runtime.validate_result_binding(publication['binding'],'moodle.analytics.run')
        client.checkpoint()
        charts = ChartStore(runtime)
        chart_id = charts.save(publication['snapshot'],publication['binding'],
            command='moodle.analytics.run',publication_id=publication['id'])
        saved = charts.read(chart_id)
        client.checkpoint()
        return result_page(chart_id,saved)
