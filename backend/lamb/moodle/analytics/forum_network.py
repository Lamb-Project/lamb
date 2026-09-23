"""Private, deterministic current-student reply graph; no public ACL boundary.

Edges point from the reply author to the immediate parent author. Only the reply
must be inside the requested creation window; its parent can predate the window.
No names, message text, centrality scores or inferred social isolation.
"""
from collections import Counter

from .forum_participation import summarize_forums


def summarize_network(discussions, students, *, since, until, as_of, timezone,
                      inventory_complete):
    # Reuse bounded shape, visibility, clock, duplicate and ancestry validation.
    volume = summarize_forums(discussions, students, since=since, until=until,
        as_of=as_of, timezone=timezone, inventory_complete=inventory_complete)
    population = set(students)
    edges, excluded = Counter(), Counter()
    complete = volume['coverage']['collection_complete']
    for thread in discussions:
        public = {p['id']:p for p in thread['posts']
                  if not p['private'] and not p['deleted']
                  and p['author_id'] is not None and p['created'] is not None}
        for reply in public.values():
            if reply['parent_id'] is None or not since <= reply['created'] < until:
                continue
            parent = public.get(reply['parent_id'])
            if parent is None:
                excluded['unavailable_parent'] += 1
                complete = False
                continue
            if parent['created'] > reply['created']:
                excluded['parent_after_reply'] += 1
                complete = False
                continue
            source, target = reply['author_id'], parent['author_id']
            if source not in population or target not in population:
                excluded['outside_current_student_population'] += 1
                continue
            if source == target:
                excluded['self_reply'] += 1
                continue
            edges[source, target] += 1
    incoming = {s:set() for s in population}
    outgoing = {s:set() for s in population}
    in_replies, out_replies = Counter(), Counter()
    for (source, target), count in edges.items():
        outgoing[source].add(target)
        incoming[target].add(source)
        out_replies[source] += count
        in_replies[target] += count
    rows = []
    for identity in sorted(population):
        peers = incoming[identity] | outgoing[identity]
        rows.append({'student_id':identity, 'in_degree':len(incoming[identity]),
            'out_degree':len(outgoing[identity]), 'unique_peers':len(peers),
            'incoming_replies':in_replies[identity], 'outgoing_replies':out_replies[identity],
            'no_observed_peer_interaction':not peers if complete else None})
    return {'window':volume['window'], 'as_of':as_of, 'timezone':timezone,
        'population_students':len(students), 'student_rows':rows,
        'edges':[{'source_student_id':a, 'target_student_id':b, 'replies':n}
                 for (a,b),n in sorted(edges.items())],
        'directed_edges':len(edges), 'peer_replies':sum(edges.values()),
        'coverage':{'complete':complete, 'source':volume['coverage'],
                    'excluded_reply_relationships':dict(excluded)},
        'limitations':[
            'Current-student peer network only; nonstudent relationships and self-replies excluded.',
            'Direction is reply author to immediate parent author; not all discussion participants.',
            'Reply creation is inside [since, until); a parent can predate the window.',
            'Degrees count distinct directed peers, not reply volume; unique peers unions both directions.',
            'Missing or unavailable parents are not reconstructed; incomplete counts are lower bounds.',
            'No observed peer interaction does not establish social isolation, disengagement or learning.',
            'Network position is not learning, contribution quality or social value.',
            'Private/deleted/redacted posts excluded; population is current, collection is not atomic.']}
