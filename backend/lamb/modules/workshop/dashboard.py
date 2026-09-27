"""Workshop dashboard — instructor-facing stats and student progress.

Consumed by the workshop teacher view (``lti_router`` `/workshop/dashboard*`).
All data comes from the activity roster, the workshop session table and the
formative evaluations; tool usage is derived from the persisted chat trace
(``saved_chat``) rather than a dedicated observability table (Lean MVP).
"""

import json
import logging
from typing import Any, Dict, List

from lamb.database_manager import LambDatabaseManager

logger = logging.getLogger(__name__)

_db_manager = LambDatabaseManager()

# Organization feature flag that enables the "teacher pilot first" gate.
WORKSHOP_TEACHER_PILOT_FLAG = "workshop_teacher_pilot"


# ─────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _as_list(value: Any) -> List[Any]:
    """Best-effort parse of a JSON string / list into a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _as_dict(value: Any) -> Dict[str, Any]:
    """Best-effort parse of a JSON string / dict into a dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def summarize_tool_usage(saved_chat_json: Any) -> Dict[str, int]:
    """Count tool calls by function name from a serialized chat.

    Tool invocations live as ``tool_calls`` entries inside the persisted
    conversation; ordinary user/assistant messages carry none and are ignored.
    """
    counts: Dict[str, int] = {}
    for message in _as_list(saved_chat_json):
        if not isinstance(message, dict):
            continue
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            name = (call.get("function") or {}).get("name")
            if not name:
                continue
            counts[name] = counts.get(name, 0) + 1
    return counts


def _aggregate_tool_usage(sessions: List[Dict[str, Any]]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for session in sessions or []:
        for name, count in summarize_tool_usage(session.get("saved_chat")).items():
            totals[name] = totals.get(name, 0) + count
    return totals


# ─────────────────────────────────────────────────────────────────────────────
# Teacher pilot gate (default off)
# ─────────────────────────────────────────────────────────────────────────────

def is_teacher_pilot_required(activity: Dict[str, Any]) -> bool:
    """Whether the org requires a teacher to complete a workshop before launch.

    Reads ``features.workshop_teacher_pilot`` from the activity owner's org
    config. Defaults to ``False`` (gate disabled) so the MVP is never blocked.
    """
    activity = activity or {}
    owner = activity.get("owner_email") or activity.get("configured_by_email")
    if not owner:
        return False
    try:
        from lamb.completions.org_config_resolver import OrganizationConfigResolver
        resolver = OrganizationConfigResolver(owner)
        return bool(resolver.get_feature_flag(WORKSHOP_TEACHER_PILOT_FLAG))
    except Exception as e:
        logger.debug(f"Teacher pilot flag unavailable for {owner}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Launch redirect
# ─────────────────────────────────────────────────────────────────────────────

def get_dashboard_url(
    activity: Dict[str, Any],
    public_base: str = "",
    dashboard_token: str = "",
) -> str:
    """Build the workshop teacher dashboard URL for an activity."""
    resource_link_id = (activity or {}).get("resource_link_id", "")
    return (
        f"{public_base}/lamb/v1/lti/workshop/dashboard"
        f"?resource_link_id={resource_link_id}&token={dashboard_token}"
    )


def instructor_launch_redirect(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Contract entry point for ``on_instructor_launch``.

    Returns the redirect target so ``lti_router`` can send the instructor to
    the workshop view instead of the chat dashboard.
    """
    ctx = ctx or {}
    activity = ctx.get("activity") or {}
    return {
        "redirect": get_dashboard_url(
            activity, ctx.get("public_base", ""), ctx.get("dashboard_token", "")),
        "activity_id": activity.get("id"),
        "type": "workshop_dashboard",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Stats / students / session detail
# ─────────────────────────────────────────────────────────────────────────────

def workshop_dashboard_stats(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Return aggregate workshop stats for an activity's teacher view."""
    activity_id = (activity or {}).get("id")
    if not activity_id:
        return {"error": "Missing activity id"}

    try:
        roster = _db_manager.get_activity_students(activity_id, page=1, per_page=1)
        total_students = roster.get("total", 0)
    except Exception as e:
        logger.warning(f"Could not fetch workshop roster: {e}")
        total_students = 0

    try:
        sessions = _db_manager.get_workshop_sessions_by_activity(activity_id)
    except Exception as e:
        logger.warning(f"Could not fetch workshop sessions: {e}")
        sessions = []

    try:
        evaluations = _db_manager.get_workshop_evaluations_by_activity(activity_id)
    except Exception as e:
        logger.warning(f"Could not fetch workshop evaluations: {e}")
        evaluations = []

    in_progress = sum(
        1 for s in sessions
        if (s.get("status") or "in_progress") == "in_progress"
    )
    submitted = sum(1 for s in sessions if s.get("status") == "submitted")
    evaluated = len({
        e.get("session_id") for e in evaluations
        if e.get("status") == "completed" and e.get("session_id")
    })

    reflections = [
        s.get("reflection") for s in sessions if s.get("reflection")
    ]
    avg_reflection_length = (
        round(sum(len(r) for r in reflections) / len(reflections), 1)
        if reflections else 0
    )

    tool_calls = _aggregate_tool_usage(sessions)

    return {
        "activity_id": activity_id,
        "type": "workshop",
        "total_students": total_students,
        "in_progress": in_progress,
        "submitted": submitted,
        "evaluated": evaluated,
        "tool_calls": tool_calls,
        "tool_calls_total": sum(tool_calls.values()),
        "avg_reflection_length": avg_reflection_length,
        "teacher_pilot_required": is_teacher_pilot_required(activity),
    }


def _reflection_excerpt(reflection: str, limit: int = 200) -> str:
    reflection = reflection or ""
    if len(reflection) <= limit:
        return reflection
    return reflection[:limit].rstrip() + "…"


def workshop_dashboard_students(activity: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per-student progress rows for the workshop teacher view."""
    activity_id = (activity or {}).get("id")
    if not activity_id:
        return []

    try:
        rows = _db_manager.get_activity_students_with_sessions(activity_id)
    except Exception as e:
        logger.warning(f"Could not fetch workshop student progress: {e}")
        return []

    try:
        evaluations = _db_manager.get_workshop_evaluations_by_activity(activity_id)
    except Exception as e:
        logger.warning(f"Could not fetch workshop evaluations: {e}")
        evaluations = []

    evaluation_by_session = {
        e.get("session_id"): e for e in evaluations if e.get("session_id")
    }

    students: List[Dict[str, Any]] = []
    for row in rows:
        session_id = row.get("session_id")
        evaluation = evaluation_by_session.get(session_id) if session_id else None
        tool_counts = summarize_tool_usage(row.get("session_saved_chat"))
        reflection = row.get("session_reflection") or ""

        students.append({
            "name": (
                row.get("user_display_name")
                or row.get("user_name")
                or row.get("user_email")
            ),
            "username": row.get("user_name") or row.get("user_email"),
            "email": row.get("user_email"),
            "session_id": session_id,
            "session_status": row.get("session_status") or "not_started",
            "assistant_id": row.get("session_assistant_id"),
            "tools_used": sorted(tool_counts.keys()),
            "tool_calls": tool_counts,
            "evaluation_status": (
                evaluation.get("status") if evaluation else "not_evaluated"
            ),
            "reflection_excerpt": _reflection_excerpt(reflection),
            "reflection_length": len(reflection),
            "last_access": row.get("last_access_at") or row.get("session_updated_at"),
            "access_count": row.get("access_count", 0),
        })
    return students


def workshop_dashboard_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Full detail for one workshop session (teacher drill-down)."""
    session = session or {}
    session_id = session.get("id")

    try:
        evaluation = _db_manager.get_workshop_evaluation(session_id)
    except Exception as e:
        logger.warning(f"Could not fetch session evaluation: {e}")
        evaluation = None

    transcript = ""
    try:
        from lamb.modules.workshop.evaluation import build_transcript
        transcript = build_transcript(session)
    except Exception as e:
        logger.debug(f"Could not build session transcript: {e}")

    return {
        "session_id": session_id,
        "activity_id": session.get("activity_id"),
        "activity_user_id": session.get("activity_user_id"),
        "status": session.get("status"),
        "assistant_id": session.get("assistant_id"),
        "build_state": _as_dict(session.get("build_state")),
        "messages": _as_list(session.get("saved_chat")),
        "reflection": session.get("reflection") or "",
        "tool_usage": summarize_tool_usage(session.get("saved_chat")),
        "evaluation": evaluation,
        "transcript": transcript,
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }
