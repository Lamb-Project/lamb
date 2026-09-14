"""Extractive conversation labels; no inference calls or transcript mutation."""
import re
GENERIC = {'', 'lamb helper', 'free-form chat', 'conversation', 'new conversation', 'about-lamb'}

def clean(text, limit):
    text = re.sub(r'<<<(?:CANVAS[^>]*|END_CANVAS|CANVAS_CLEAR)>>>', '', str(text or ''))
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', str(text or ''))
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'[`*#|<>]', '', text)
    text = ' '.join(text.split())
    return text if len(text) <= limit else text[:limit-1].rsplit(' ', 1)[0] + '…'

def preview(title, messages):
    requests = [m.get('content', '') for m in messages if m.get('role') == 'user'
                and isinstance(m.get('content'), str)
                and not m['content'].startswith(('[System:', '[Application workflow instructions]'))]
    substantive = [t for t in requests if len(t.strip()) > 8]
    answers = [m.get('content', '') for m in messages if m.get('role') == 'assistant'
               and m.get('content') and not m.get('tool_calls')]
    if (title or '').strip().lower() in GENERIC:
        title = clean(substantive[0], 80) if substantive else 'New conversation'
    # First request gives purpose; latest answer shows where the work reached.
    parts = [clean(substantive[0], 130)] if substantive else []
    if answers and substantive:
        latest = clean(answers[-1], 200)
        if latest and latest not in parts: parts.append(latest)
    return {'title': title, 'summary': ' · '.join(parts), 'summary_type': 'extractive'}
