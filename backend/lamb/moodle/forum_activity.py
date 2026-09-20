"""Deterministic, bounded forum traversal. No model, workstation profile or writes."""
from datetime import date, datetime, timezone
from html.parser import HTMLParser
import json
import re
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .scope import MoodleScope

MAX_CALLS = 160
MAX_SECONDS = 90
MAX_SOURCE_BYTES = 2 * 1024 * 1024
PAGE_SIZE = 50


def validate_request(params):
    courses = params.get('course_ids', ())
    if bool(params.get('all_courses')) == bool(courses):
        raise ValueError('Choose --all-courses or one or more --course ID options')
    if len(courses) > 100:
        raise ValueError('Select at most 100 courses')
    if not 1 <= int(params.get('max_posts', 200)) <= 200:
        raise ValueError('max_posts must be between 1 and 200')
    try:
        zone = ZoneInfo(params.get('tz', 'UTC'))
        month = params.get('month')
        if month:
            if params.get('since') or params.get('until') or not re.fullmatch(r'\d{4}-\d{2}', month):
                raise ValueError()
            first = date.fromisoformat(month + '-01')
            last = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
        else:
            first, last = date.fromisoformat(params['since']), date.fromisoformat(params['until'])
        if not first < last or (last - first).days > 366:
            raise ValueError()
    except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError):
        raise ValueError('Use --month YYYY-MM or --since YYYY-MM-DD --until YYYY-MM-DD (exclusive), within 366 days, and a valid --tz IANA timezone') from None
    return datetime.combine(first, datetime.min.time(), zone), datetime.combine(last, datetime.min.time(), zone)


class TaskLimit(Exception):
    pass


class TaskCancelled(Exception):
    pass


class GuardedClient:
    """Check revocation, cancellation and the shared task budget before each request."""
    readonly = True

    def __init__(self, client, *, revalidate, cancel=None, max_calls=MAX_CALLS, max_seconds=MAX_SECONDS):
        self.client, self.revalidate, self.cancel = client, revalidate, cancel
        self.calls, self.max_calls = 0, max_calls
        self.before_request = None
        self.started, self.max_seconds = time.monotonic(), max_seconds

    def checkpoint(self):
        if self.cancel is not None and self.cancel.is_set():
            raise TaskCancelled('Moodle read stopped. Saved progress may be available in moodle runs.')
        self.revalidate()

    def call(self, function, **params):
        self.checkpoint()
        if self.calls >= self.max_calls or time.monotonic() - self.started >= self.max_seconds:
            raise TaskLimit('request_or_time_limit')
        if self.before_request is not None:
            self.before_request()
        self.calls += 1
        result = self.client.call(function, **params)
        self.checkpoint()
        if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_SOURCE_BYTES:
            raise TaskLimit('response_size_limit')
        return result


class TextPreview(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style'} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def preview(value, limit=240):
    parser = TextPreview()
    parser.feed(str(value))
    text = ' '.join(' '.join(parser.parts).split())
    return text[:limit], len(text) > limit


def transient_failure(exc):
    """Retry read-only transport failures, never permission/validation errors."""
    import httpx
    from moodle_cli.client.exceptions import MoodleAPIError
    cause = exc
    while cause is not None:
        if isinstance(cause, (httpx.TransportError, TimeoutError, ConnectionError)):
            return True
        status = getattr(cause, 'status_code', None)
        if status is None:
            status = getattr(getattr(cause, 'response', None), 'status_code', None)
        if status in {408, 429, 500, 502, 503, 504}:
            return True
        if isinstance(cause, MoodleAPIError) and getattr(cause, 'error_code', '') in {'ratelimitexceeded', 'servicenotavailable'}:
            return True
        cause = cause.__cause__
    return False


def failure_reason(exc):
    # No raw provider errors, URLs containing credentials, or response bodies.
    from moodle_cli.client.exceptions import MoodleAPIError
    if isinstance(exc, PermissionError):
        return 'excluded', 'instructor_scope_not_verified'
    if isinstance(exc, MoodleAPIError):
        code = getattr(exc, 'error_code', '')
        if code in {'accessexception', 'nopermissions', 'requireloginerror', 'notingroup'}:
            return 'denied', 'moodle_permission_denied'
        if code in {'invalidrecord', 'wsfunctionnotavailable', 'wsfunctionnotfound'}:
            return 'unsupported', 'resource_or_function_unavailable'
    return 'failed', 'moodle_read_failed'


def forum_activity(client, owner_id, params, *, progress=None):
    """In-memory one-step adapter; durable runtime tasks use RunStore."""
    from .forum_traversal import initial_state, advance, project
    state = initial_state(params)
    reason = None
    try:
        advance(client, owner_id, state, progress=progress)
    except TaskLimit as exc:
        if not state['initialized']:
            raise
        reason = str(exc)
    client.checkpoint()
    state['calls'] = client.calls
    return project(state, client, reason)
