"""Workshop data retention — per-category lifetimes (decision C9).

Retention is deliberately **not** one aggressive switch. Three data categories
age differently:

* **Conversations and reflections** — the student's own words. When the
  retention window closes they are only *reported* (``expiring_soon`` on the
  teacher dashboard); nothing is deleted silently, because that is the work
  being assessed.
* **Knowledge-base material** (the uploaded document + its collection) — the
  original file follows the session's lifetime and **is** deleted by the sweep,
  because keeping source documents forever is the actual privacy liability.
* **Assistants** — never deleted automatically: the assistant *is* the student's
  work product, and the C-group roadmap (portfolio / export) depends on it
  surviving.

Automatic deletion is off unless a deployment opts in: ``WORKSHOP_RETENTION_DAYS``
sets the instance-wide window and the org feature ``workshop_retention_days``
overrides it per organization. Unset means "no automatic deletion at all".
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Org feature / env names.
RETENTION_DAYS_FEATURE = "workshop_retention_days"
RETENTION_DAYS_ENV = "WORKSHOP_RETENTION_DAYS"
RETENTION_ENABLED_ENV = "WORKSHOP_RETENTION_ENABLED"

# Recommended starting point for a deployment that enables retention (the plan
# suggests 180 days); only used in documentation/hints, never as a silent
# default, so nothing is ever deleted without an explicit configuration.
RECOMMENDED_RETENTION_DAYS = 180


def _positive_int(value: Any) -> Optional[int]:
    """Coerce a config value to a positive int, or None."""
    if value is None or value == "":
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def retention_days(activity: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """Effective retention window in days, or None when disabled.

    Resolution order: org feature ``workshop_retention_days`` →
    ``WORKSHOP_RETENTION_DAYS`` env → None (no automatic deletion).
    """
    owner = (activity or {}).get("owner_email") or (
        activity or {}).get("configured_by_email")
    if owner:
        try:
            from lamb.completions.org_config_resolver import (
                OrganizationConfigResolver,
            )

            org_value = OrganizationConfigResolver(owner).get_feature_value(
                RETENTION_DAYS_FEATURE, None)
            resolved = _positive_int(org_value)
            if resolved:
                return resolved
        except Exception as e:  # pragma: no cover - config lookup best effort
            logger.debug("Retention org feature unavailable (%s)", e)

    return _positive_int(os.getenv(RETENTION_DAYS_ENV))


def retention_cutoff(now: Optional[int] = None,
                     days: Optional[int] = None) -> Optional[int]:
    """Epoch-seconds cutoff: rows last touched before it are expired."""
    if days is None:
        days = retention_days()
    if not days:
        return None
    import time

    reference = int(now if now is not None else time.time())
    return reference - days * 86400