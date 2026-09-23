"""Calendar-boundary planning, shared by AAC and terminal tasks; no source I/O."""
from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EVENT_RECIPES = frozenset({'resource-reach','view-trends','view-heatmap',
                          'view-distribution','active-day-distribution'})
MAX_LOCAL_DAYS = 90
# Existing optional Moodle adapters enforce this transport bound in seconds.
# Do not silently exceed it, shrink a range or claim multi-window support.
MAX_SOURCE_SECONDS = 90 * 86400


def calendar_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Use a calendar date YYYY-MM-DD')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('Use a valid calendar date YYYY-MM-DD') from None


def midnight(day, zone):
    local = datetime.combine(day, datetime.min.time(), zone)
    stamp = int(local.timestamp())
    if datetime.fromtimestamp(stamp, zone).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError('This local midnight does not exist; the range needs an explicit supported boundary')
    if local.utcoffset() != local.replace(fold=1).utcoffset():
        raise ValueError('This local midnight is ambiguous; the range needs an explicit supported boundary')
    return stamp


def plan_window(since, *, until=None, through=None, tz='UTC'):
    if (until is None) == (through is None):
        raise ValueError('Provide exactly one end: --through inclusive or --until exclusive')
    try:
        zone = ZoneInfo(tz)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        raise ValueError('Use an IANA timezone') from None
    start = calendar_date(since)
    try:
        end = calendar_date(through) + timedelta(days=1) if through is not None else calendar_date(until)
    except OverflowError:
        raise ValueError('Inclusive end is outside the supported calendar range') from None
    days = (end-start).days
    if days < 1:
        raise ValueError('The exclusive end must follow the start')
    begin, finish = midnight(start,zone), midnight(end,zone)
    seconds = finish-begin
    supported = days <= MAX_LOCAL_DAYS and seconds <= MAX_SOURCE_SECONDS
    reason = None
    if days > MAX_LOCAL_DAYS:
        reason = 'The requested interval exceeds 90 local calendar days. Multi-window event collection is not implemented.'
    elif seconds > MAX_SOURCE_SECONDS:
        reason = 'The exact local interval exceeds the installed adapter transport limit across an offset change. Multi-window event collection is not implemented.'
    return {'since':start.isoformat(),'until':end.isoformat(),
        'through':(end-timedelta(days=1)).isoformat(),'timezone':tz,
        'calendar_days':days,'since_timestamp':begin,'until_timestamp':finish,
        'elapsed_seconds':seconds,'collection_supported':supported,'reason':reason,
        'source_availability':'not_checked','historical_coverage':'unknown',
        'notice':'This is the requested interval, not discovered data availability. No Moodle data was read. '
                 'Keep these bounds unchanged; do not silently shorten or split unsupported requests.'}


def require_event_window(since, until, tz):
    plan = plan_window(since,until=until,tz=tz)
    if not plan['collection_supported']:
        raise ValueError(f"Requested [{plan['since']}, {plan['until']}) in {tz}: "
                         f"{plan['calendar_days']} local days. {plan['reason']} Keep the requested interval unchanged.")
    return plan


def require_event_timestamps(since, until, tz='UTC'):
    """Protect raw/internal collectors too, including partial final days."""
    zone = ZoneInfo(tz)
    start, end = datetime.fromtimestamp(since,zone), datetime.fromtimestamp(until,zone)
    last = end.date() + (timedelta(days=1) if end.time() != datetime.min.time() else timedelta())
    days = (last-start.date()).days
    if days > MAX_LOCAL_DAYS:
        raise ValueError('Requested event interval exceeds 90 local calendar days; multi-window collection is unsupported. Do not shorten it silently.')
    if until-since > MAX_SOURCE_SECONDS:
        raise ValueError('Requested event interval exceeds the adapter elapsed-time bound across an offset change; multi-window collection is unsupported. Keep the requested bounds.')
