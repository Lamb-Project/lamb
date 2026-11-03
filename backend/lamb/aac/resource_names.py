"""Scoped resource-name resolution. Never infer identity from one inventory page."""
import re
import unicodedata
from difflib import SequenceMatcher


def normalized(value, *, assistant=False):
    value = unicodedata.normalize('NFKC', str(value)).casefold().strip()
    if assistant:
        value = re.sub(r'^\d+_', '', value)
    return ' '.join(re.sub(r'[_\-\s]+', ' ', value).split())


def choose(items, value, *, kind='resource'):
    """Return one verified inventory entry, or a useful bounded ambiguity error."""
    by_id = {}
    for item in items:
        identifier = item.get('id', item.get('assistant_id'))
        if identifier is not None:
            by_id[str(identifier)] = item
    items = list(by_id.values())
    names = lambda item: [str(item.get(k, '')) for k in ('name', 'fullname', 'shortname') if item.get(k)]
    norm = lambda s: normalized(s, assistant=kind == 'assistant')
    needle = norm(value)
    matches = [item for item in items if str(value) in names(item)]
    if not matches:
        matches = [item for item in items if needle in [norm(n) for n in names(item)]]
    if not matches and len(needle) >= 4:
        matches = [item for item in items if any(set(needle.split()) <= set(norm(n).split()) for n in names(item))]
    if not matches and len(needle) >= 6:
        scores = sorted([(max((SequenceMatcher(None, needle, norm(n)).ratio() for n in names(i)), default=0), n, i)
                         for n, i in enumerate(items)], reverse=True)
        if scores and scores[0][0] >= .90:
            if len(scores) == 1 or scores[0][0] - scores[1][0] >= .10:
                matches = [scores[0][2]]
            else:
                matches = [row[2] for row in scores if row[0] >= scores[0][0] - .10]
    if len(matches) == 1:
        return matches[0]
    if matches:
        choices = [{'id': i.get('id', i.get('assistant_id')), 'name': names(i)[0],
                    **({'owner': i['owner']} if i.get('owner') else {})} for i in matches[:5]]
        raise ValueError(f"Ambiguous {kind} name {value!r}. Ask one question to distinguish these accessible resources: {choices}")
    raise ValueError(f"No accessible {kind} matches {value!r}. Search the available inventory; do not demand an exact spelling.")


def unwrap(value):
    return value.get('data', value) if isinstance(value, dict) and 'data' in value else value


async def assistants(http):
    result, offset = [], 0
    while True:
        raw = unwrap(await http.get('/creator/assistant/get_assistants', params={'limit': 100, 'offset': offset}))
        page = raw if isinstance(raw, list) else raw.get('assistants', [])
        result.extend(page)
        offset += len(page)
        total = raw.get('total_count') if isinstance(raw, dict) else None
        if (total is not None and offset >= total) or (total is None and len(page) < 100):
            break
        if not page or offset >= 10000:
            raise ValueError('Assistant inventory is incomplete; narrow the search before resolving a name.')
    shared = unwrap(await http.get('/creator/lamb/assistant-sharing/shared-with-me'))
    result.extend(shared if isinstance(shared, list) else shared.get('assistants', []))
    return result


async def resolve(http, kind, value):
    if str(value).isascii() and str(value).isdecimal():
        return str(int(value))
    if kind == 'assistant':
        items = await assistants(http)
    elif kind == 'kb':
        raw = unwrap(await http.get('/creator/knowledgebases/user'))
        items = raw if isinstance(raw, list) else raw.get('knowledge_bases', [])
        shared = unwrap(await http.get('/creator/knowledgebases/shared'))
        items = [*items, *(shared if isinstance(shared, list) else shared.get('knowledge_bases', []))]
    else:
        raise ValueError('Unsupported resource type')
    item = choose(items, value, kind=kind)
    return str(item.get('id', item.get('assistant_id')))
