"""Activity timetables: when an LLM-access activity is open.

A schedule is a dict stored as JSON on the activity:

    {"timezone": "Europe/Madrid",
     "mode": "always" | "weekly",
     "weekly": [{"days": [0, 2], "start": "15:00", "end": "17:00"}],   # 0 = Monday
     "from": "2026-10-12", "until": "2026-12-20"}                     # optional, inclusive, local dates

The instructor's override ("auto", "open", "closed") wins over the timetable. Times must fall
on the slot granularity (10 minutes by default) because the proxy's budget windows are aligned
to the clock (:00, :10, :20 ...).
"""
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

OVERRIDES = ('auto', 'open', 'closed')


class ScheduleError(ValueError):
    pass


def _hm(value):
    try:
        h, m = value.split(':')
        t = dtime(int(h), int(m))
    except (AttributeError, ValueError):
        raise ScheduleError(f'time must be HH:MM, got {value!r}')
    return t


def validate(schedule, slot_minutes=10):
    """Return a normalised copy of schedule or raise ScheduleError."""
    if not isinstance(schedule, dict):
        raise ScheduleError('schedule must be an object')
    tz = schedule.get('timezone') or 'UTC'
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise ScheduleError(f'unknown time zone {tz!r}')
    mode = schedule.get('mode', 'always')
    if mode not in ('always', 'weekly'):
        raise ScheduleError('mode must be "always" or "weekly"')
    weekly = []
    if mode == 'weekly':
        entries = schedule.get('weekly') or []
        if not entries:
            raise ScheduleError('a weekly schedule needs at least one window')
        for w in entries:
            days = w.get('days')
            if not days or not all(isinstance(d, int) and 0 <= d <= 6 for d in days):
                raise ScheduleError('days must be a non-empty list of 0 (Monday) to 6 (Sunday)')
            start, end = _hm(w.get('start')), _hm(w.get('end'))
            for t in (start, end):
                if t.minute % slot_minutes:
                    raise ScheduleError(f'times must fall on {slot_minutes}-minute steps, got {t:%H:%M}')
            if not start < end:
                raise ScheduleError('a window must end after it starts, on the same day')
            weekly.append({'days': sorted(set(days)), 'start': f'{start:%H:%M}', 'end': f'{end:%H:%M}'})
    bounds = {}
    for k in ('from', 'until'):
        if schedule.get(k):
            try:
                bounds[k] = date.fromisoformat(schedule[k]).isoformat()
            except ValueError:
                raise ScheduleError(f'{k} must be YYYY-MM-DD')
    if 'from' in bounds and 'until' in bounds and bounds['from'] > bounds['until']:
        raise ScheduleError('from must not be after until')
    return {'timezone': tz, 'mode': mode, 'weekly': weekly, **bounds}


def is_open(schedule, override='auto', now=None):
    """True if the activity is open at now (aware datetime, default: current UTC time)."""
    if override == 'open':
        return True
    if override == 'closed':
        return False
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo(schedule.get('timezone') or 'UTC'))
    day = local.date().isoformat()
    if schedule.get('from') and day < schedule['from']:
        return False
    if schedule.get('until') and day > schedule['until']:
        return False
    if schedule.get('mode', 'always') == 'always':
        return True
    t = local.time()
    for w in schedule.get('weekly', []):
        if local.weekday() in w['days'] and _hm(w['start']) <= t < _hm(w['end']):
            return True
    return False


def next_change(schedule, override='auto', now=None, slot_minutes=10, horizon_days=14):
    """The next slot boundary at which is_open flips, or None within the horizon."""
    if override in ('open', 'closed'):
        return None
    now = now or datetime.now(timezone.utc)
    step = timedelta(minutes=slot_minutes)
    t = datetime.fromtimestamp((int(now.timestamp()) // (slot_minutes * 60) + 1) * slot_minutes * 60, timezone.utc)
    state = is_open(schedule, override, now)
    end = now + timedelta(days=horizon_days)
    while t <= end:
        if is_open(schedule, override, t) != state:
            return t
        t += step
    return None


def end_of_validity(schedule):
    """UTC datetime after which the activity can never open again (end of 'until'), or None."""
    if not schedule.get('until'):
        return None
    tz = ZoneInfo(schedule.get('timezone') or 'UTC')
    return datetime.combine(date.fromisoformat(schedule['until']) + timedelta(days=1), dtime(0), tz).astimezone(timezone.utc)
