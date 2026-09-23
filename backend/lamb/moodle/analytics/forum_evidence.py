"""Read-time semantic labels for old/new immutable authorized forum snapshots."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo


def with_forum_semantics(snapshot):
    recipe=snapshot.get('recipe')
    if not isinstance(recipe,dict) or recipe.get('id') not in {'forum-participation','forum-discussions'}:
        return snapshot
    result=deepcopy(snapshot)
    window=result.get('metrics',{}).get('window')
    if isinstance(window,dict) and all(type(window.get(k)) is int for k in ('since','until')):
        zone=ZoneInfo(result['timezone'])
        result['window_start_local']=datetime.fromtimestamp(window['since'],zone).isoformat()
        result['window_end_local']=datetime.fromtimestamp(window['until'],zone).isoformat()
        result['window_label']=(f"[{result['window_start_local']}, {result['window_end_local']}) "
                                f"{result['timezone']}; end exclusive")
    result['forum_exclusion_basis']=(
        'outside_population_window_posts counts public posts INSIDE the requested date window '
        'whose authors are OUTSIDE the current student population. It does NOT count posts outside the date window. '
        'Do not infer an outside-window total by subtracting student posts from source_posts.')
    result['forum_reply_basis']=(
        'For forum-participation rows, replies counts ONLY current students public replies created INSIDE '
        'the requested window. It is not the all-author discussion reply count.'
        if recipe['id']=='forum-participation' else
        'observed_public_replies_as_of is a COUNT of replies by all visible authors, including self-replies, '
        'through the snapshot, not only the date window. It is not a last-activity timestamp. '
        'last_observed_public_post_at is the separate timestamp; age is seconds at the snapshot, not now.')
    return result
