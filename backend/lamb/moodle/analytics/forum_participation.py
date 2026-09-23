"""Pure bounded forum evidence reduction, not a public recipe or ACL boundary.

Caller supplies authorized discussions and an exhausted current population.
Student IDs remain private here until an authorized learner-table projection.
No post text, names, reply content or inferred resolution/quality is returned.
"""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

MAX_STUDENTS = 1000
MAX_DISCUSSIONS = 1000
MAX_POSTS = 10000


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('Invalid forum evidence integer')
    return value


def summarize_forums(discussions, students, *, since, until, as_of, timezone,
                     inventory_complete):
    """Normalized posts: id, parent_id (null root), author_id, created,
    deleted/private booleans. Null author/created means redacted source data.
    Threads: id, forum_id, complete boolean, posts list.
    Window is [since, until); as_of bounds all source evidence independently.
    """
    zone = ZoneInfo(timezone)
    for stamp in (since, until, as_of):
        _integer(stamp)
    if not since < until <= as_of or until-since > 366*86400+3600:
        raise ValueError('Invalid bounded forum window')
    if type(inventory_complete) is not bool:
        raise ValueError('Explicit forum inventory coverage required')
    if (not isinstance(students, (list, tuple, set)) or len(students) > MAX_STUDENTS
            or any(type(s) is not int or s < 1 for s in students) or len(set(students)) != len(students)):
        raise ValueError('Invalid complete student population')
    if not isinstance(discussions, list) or len(discussions) > MAX_DISCUSSIONS:
        raise ValueError('Forum discussion bound exceeded')
    learner = {s:{'student_id':s, 'posts':0, 'replies':0, 'discussions_started':0} for s in students}
    days = {s:set() for s in students}
    seen_threads, seen_posts = set(), set()
    rows, exclusions = [], Counter()
    for thread in discussions:
        did = _integer(thread['id'], 1)
        fid = _integer(thread['forum_id'], 1)
        if did in seen_threads or type(thread.get('complete')) is not bool:
            raise ValueError('Duplicate discussion or unknown coverage')
        seen_threads.add(did)
        posts = thread.get('posts')
        if not isinstance(posts, list) or len(seen_posts)+len(posts) > MAX_POSTS:
            raise ValueError('Forum post bound exceeded')
        parents, usable = {}, []
        redacted = 0
        for post in posts:
            pid = _integer(post['id'], 1)
            if pid in seen_posts:
                raise ValueError('Duplicate forum post')
            seen_posts.add(pid)
            parent = post['parent_id']
            if parent is not None:
                _integer(parent, 1)
            parents[pid] = parent
            if any(type(post.get(flag)) is not bool for flag in ('deleted', 'private')):
                raise ValueError('Unknown post visibility')
            author, stamp = post['author_id'], post['created']
            if author is not None:
                _integer(author, 1)
            if stamp is not None:
                _integer(stamp)
                if stamp > as_of:
                    raise ValueError('Forum post after observation cutoff')
            if post['deleted'] or post['private']:
                exclusions['deleted' if post['deleted'] else 'private'] += 1
                continue
            if author is None or stamp is None:
                exclusions['redacted'] += 1
                redacted += 1
                continue
            usable.append(post)
        # Reject cycles; missing parents reduce evidence coverage, not fabricate roots.
        complete = thread['complete'] and not redacted
        resolved = set()
        for pid in parents:
            visiting, node = set(), pid
            while node is not None and node not in resolved:
                if node in visiting:
                    raise ValueError('Cyclic forum reply graph')
                if node not in parents:
                    complete = False
                    break
                visiting.add(node)
                node = parents[node]
            resolved.update(visiting)
        roots = [post for post in usable if post['parent_id'] is None]
        if len(roots) > 1:
            raise ValueError('Multiple discussion roots')
        complete = complete and len(roots) == 1
        replies = sum(post['parent_id'] is not None for post in usable)
        last = max((post['created'] for post in usable), default=None)
        selected = [post for post in usable if since <= post['created'] < until]
        for post in selected:
            author = post['author_id']
            if author not in learner:
                exclusions['outside_population_window_posts'] += 1
                continue
            item = learner[author]
            item['posts'] += 1
            item['replies'] += post['parent_id'] is not None
            item['discussions_started'] += post['parent_id'] is None
            days[author].add(datetime.fromtimestamp(post['created'], zone).date())
        rows.append({'discussion_id':did, 'forum_id':fid,
            'observed_public_posts_in_window':len(selected),
            'observed_public_replies_as_of':replies,
            'no_observed_public_replies':replies == 0 if complete else None,
            'last_observed_public_post_at':last,
            'seconds_since_last_observed_public_post':as_of-last if last is not None else None,
            'public_thread_complete':complete, 'resolution_status':'unknown'})
    for identity, item in learner.items():
        item['active_local_days'] = len(days[identity])
    complete = inventory_complete and all(row['public_thread_complete'] for row in rows)
    student_rows = sorted(learner.values(), key=lambda row:(-row['posts'], row['student_id']))
    return {'window':{'since':since, 'until':until, 'until_exclusive':True},
        'as_of':as_of, 'timezone':timezone, 'population_students':len(students),
        'student_rows':student_rows,
        'students_without_observed_public_posts':sum(row['posts'] == 0 for row in student_rows),
        'student_public_posts_in_window':sum(row['posts'] for row in student_rows),
        'discussion_rows':sorted(rows, key=lambda row:(row['last_observed_public_post_at'] is None,
            row['last_observed_public_post_at'] or 0, row['discussion_id'])),
        'coverage':{'inventory_complete':inventory_complete, 'collection_complete':complete,
            'source_posts':len(seen_posts), 'exclusions':dict(exclusions)},
        'limitations':['Counts describe observed public posts, not participation quality or learning.',
            'No observed public replies does not mean unanswered or unresolved; private/deleted posts are excluded.',
            'Reply counts include all visible authors and self-replies, not just current students.',
            'Student metrics use post creation in the requested window, not edit time.',
            'Discussion reply counts and last activity cover retrieved posts through as_of, not only the window.',
            'Zeros are observed absence, not proven nonparticipation; partial collection yields lower bounds.',
            'Current population is not historical enrolment. Collection is not atomic.']}
