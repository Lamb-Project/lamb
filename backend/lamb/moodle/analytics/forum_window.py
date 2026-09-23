"""Exact explicit local calendar window for forum post creation counts."""
import time
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .window import calendar_date, midnight


def parse_window(since, until, through, tz):
    if (until is None)==(through is None):
        raise ValueError('Forum analytics requires exactly one of --until or --through')
    try:
        zone=ZoneInfo(tz)
        begin=calendar_date(since)
        end=calendar_date(until) if until is not None else calendar_date(through)+timedelta(days=1)
    except (TypeError,OverflowError,ZoneInfoNotFoundError):
        raise ValueError('Use valid local dates and an IANA timezone') from None
    if not 1 <= (end-begin).days <= 366:
        raise ValueError('Use a forum window of 1 to 366 local days; requested bounds were not changed')
    start,finish=midnight(begin,zone),midnight(end,zone)
    if finish>int(time.time()):
        raise ValueError('Forum window must end in the past; requested bounds were not changed')
    if finish-start>366*86400+3600:
        raise ValueError('Forum window exceeds the elapsed-time bound; requested bounds were not changed')
    return start,finish
