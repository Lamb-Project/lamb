"""How often the worker runs, read from the environment so production and test rigs can differ.
The defaults are production values; development rigs set shorter ones.

  TOKEN_DEALER_RECONCILE_SECONDS       30   timetables and safety net; teachers' actions apply at once anyway
  TOKEN_DEALER_INGEST_SECONDS          60   how fresh the usage figures are; limits never depend on it
  TOKEN_DEALER_INGEST_OVERLAP_SECONDS  600  usage re-read on each ingest; must exceed the longest request,
                                            since a spend log carries its request's start time
"""
import logging
import os

log = logging.getLogger('lamb.token_dealer.timing')


def _seconds(name, default, minimum):
    raw = os.environ.get(name)
    if raw in (None, ''):
        return float(default)
    try:
        value = float(raw)
    except ValueError:
        log.warning('%s=%r is not a number of seconds; using %s', name, raw, default)
        return float(default)
    return max(float(minimum), value)


def reconcile_seconds():
    return _seconds('TOKEN_DEALER_RECONCILE_SECONDS', 30, 1)


def ingest_seconds():
    return _seconds('TOKEN_DEALER_INGEST_SECONDS', 60, 5)


def ingest_overlap_seconds():
    return _seconds('TOKEN_DEALER_INGEST_OVERLAP_SECONDS', 600, 60)


def usage_delay_seconds():
    """Upper bound shown to teachers: one ingest interval plus the proxy's 10 to 30 s log batching."""
    return int(ingest_seconds() + 30)
