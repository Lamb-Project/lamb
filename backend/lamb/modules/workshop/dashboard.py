"""Workshop dashboard — instructor-facing reuse.

Phase 3 aligns the interface; Phase 6 details the teacher dashboard UI.
"""

import logging
from typing import Any, Dict

from lamb.database_manager import LambDatabaseManager

logger = logging.getLogger(__name__)

_db_manager = LambDatabaseManager()


def workshop_dashboard_stats(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Return basic workshop dashboard stats for an activity."""
    activity_id = activity.get("id")
    if not activity_id:
        return {"error": "Missing activity id"}

    try:
        students = _db_manager.get_activity_students(activity_id, page=1, per_page=1)
        total_students = students.get("total", 0)
    except Exception as e:
        logger.warning(f"Could not fetch workshop dashboard stats: {e}")
        total_students = 0

    return {
        "activity_id": activity_id,
        "total_students": total_students,
        "type": "workshop",
    }
