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


def _db():
    """Late-bound db manager (keeps module import side-effect free)."""
    from lamb.database_manager import LambDatabaseManager

    return LambDatabaseManager()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def retention_enabled() -> bool:
    """Whether the automatic sweep runs at all (default: off).

    Deletion is opt-in: an operator sets ``WORKSHOP_RETENTION_ENABLED=1`` *and*
    a retention window before anything is ever removed automatically.
    """
    return _truthy(os.getenv(RETENTION_ENABLED_ENV))


# ─────────────────────────────────────────────────────────────────────────────
# Manual deletion: two levels (decision C18)
# ─────────────────────────────────────────────────────────────────────────────

async def erase_session_content(
    session: Dict[str, Any], activity: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Erase level: remove what the student produced, keep the assistant.

    Clears the conversation, reflection and build state, drops the stored
    evaluation, deletes the session's KB collection **and** its files, and
    clears the assistant's RAG binding. The assistant row and the roster entry
    survive — a document attached by mistake should not cost the student the
    assistant they built (C18).

    Remote work happens first: if the KB server is unavailable the local
    content is left untouched, so the operation never half-completes and the
    next attempt (or sweep) can retry.
    """
    from lamb.modules.workshop import kb as workshop_kb

    db = _db()
    session_id = (session or {}).get("id")
    if not session_id:
        return {"success": False, "detail": "Missing session"}

    kb_id = session.get("kb_id")
    kb_result: Dict[str, Any] = {"deleted": False, "detail": "no collection"}

    if kb_id:
        if activity is None:
            activity = db.get_lti_activity_by_id(session.get("activity_id"))
        if not activity:
            return {"success": False, "detail": "Activity not found"}
        try:
            kb_result = await workshop_kb.delete_session_kb(activity, str(kb_id))
        except Exception as e:
            logger.error(
                "Workshop erase: KB deletion failed for session %s: %s",
                session_id, e)
            return {
                "success": False,
                "detail": f"Knowledge base deletion failed: {e}",
                "kb": {"deleted": False, "detail": str(e)},
            }

    erased = db.erase_workshop_session_content(session_id)
    assistant_id = session.get("assistant_id")
    if assistant_id:
        db.clear_assistant_rag_collections(assistant_id)

    logger.info(
        "Workshop erase: session %s content erased (kb=%s)",
        session_id, kb_result.get("detail"))
    return {
        "success": bool(erased),
        "level": "erase",
        "session_id": session_id,
        "assistant_preserved": bool(assistant_id),
        "kb": kb_result,
    }


async def purge_session(
    session: Dict[str, Any], activity: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Purge level: erase everything *and* delete the assistant row.

    Used when the student or teacher wants the data actually gone rather than
    merely emptied (C18). The session row stays — it is the teacher's record
    that the work existed — but loses its ``assistant_id`` so nothing dangles.
    """
    db = _db()
    session_id = (session or {}).get("id")
    if not session_id:
        return {"success": False, "detail": "Missing session"}

    assistant_id = session.get("assistant_id")
    result = await erase_session_content(session, activity)
    if not result.get("success"):
        return result

    removed = None
    if assistant_id:
        assistant = db.get_assistant_by_id(assistant_id)
        owner = getattr(assistant, "owner", None) if assistant else None
        if assistant and owner:
            removed = db.delete_assistant(assistant_id, owner)
        else:
            logger.warning(
                "Workshop purge: assistant %s not found for session %s",
                assistant_id, session_id)

    db.detach_workshop_session_assistant(session_id)

    logger.info(
        "Workshop purge: session %s purged (assistant=%s removed=%s)",
        session_id, assistant_id, removed)
    return {
        "success": True,
        "level": "purge",
        "session_id": session_id,
        "assistant_deleted": bool(removed),
        "kb": result.get("kb"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Automatic sweep (decision C9 — per-category behaviour)
# ─────────────────────────────────────────────────────────────────────────────

async def purge_expired_sessions(now: Optional[int] = None) -> Dict[str, Any]:
    """Sweep expired workshop sessions, honouring the per-category rules.

    * **Knowledge-base material** → deleted (the source document is the real
      liability, and it follows the session's lifetime).
    * **Conversations / reflections** → only reported (``expiring``); they are
      the assessed work and are never removed behind the student's back.
    * **Assistants** → never touched. The C-group roadmap (portfolio, export)
      depends on the work product surviving.

    Returns a summary dict; never raises, so a scheduled loop cannot die.
    """
    if not retention_enabled():
        return {"enabled": False, "reason": "WORKSHOP_RETENTION_ENABLED is off"}

    cutoff = retention_cutoff(now)
    if cutoff is None:
        return {"enabled": False, "reason": "No retention window configured"}

    db = _db()
    try:
        sessions = db.list_workshop_sessions_for_retention(cutoff)
    except Exception as e:  # pragma: no cover - defensive
        logger.error("Workshop retention: session query failed: %s", e)
        return {"enabled": True, "error": str(e)}

    summary: Dict[str, Any] = {
        "enabled": True,
        "cutoff": cutoff,
        "candidates": len(sessions),
        "kb_deleted": [],
        "kb_failed": [],
        "expiring": [],
        "assistants_preserved": 0,
    }

    for session in sessions:
        session_id = session.get("id")
        activity = None
        try:
            activity = db.get_lti_activity_by_id(session.get("activity_id"))
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(
                "Workshop retention: activity lookup failed for %s: %s",
                session_id, e)

        # Conversations/reflections are reported, never silently removed.
        if session.get("saved_chat") or session.get("reflection"):
            summary["expiring"].append(session_id)

        # Assistants are never auto-deleted; count them for the log line.
        if session.get("assistant_id"):
            summary["assistants_preserved"] += 1

        kb_id = session.get("kb_id")
        if not kb_id or not activity:
            continue
        try:
            await _delete_kb_only(activity, str(kb_id), session_id)
            summary["kb_deleted"].append({"session_id": session_id, "kb_id": kb_id})
        except Exception as e:
            logger.error(
                "Workshop retention: KB deletion failed for session %s: %s",
                session_id, e)
            summary["kb_failed"].append(
                {"session_id": session_id, "kb_id": kb_id, "error": str(e)})

    if summary["candidates"]:
        logger.info(
            "Workshop retention sweep: %d candidate(s), %d KB deleted, "
            "%d KB failures, %d expiring conversation(s), "
            "%d assistant(s) preserved",
            summary["candidates"], len(summary["kb_deleted"]),
            len(summary["kb_failed"]), len(summary["expiring"]),
            summary["assistants_preserved"])
    return summary


async def _delete_kb_only(
    activity: Dict[str, Any], kb_id: str, session_id: str
) -> None:
    """Delete a collection and forget the session's binding to it."""
    from lamb.modules.workshop import kb as workshop_kb

    await workshop_kb.delete_session_kb(activity, kb_id)
    # Only the KB columns: the sweep must not touch conversations.
    _db().update_workshop_session_kb(
        session_id, kb_id="", document_file_id="", document_status="deleted")
