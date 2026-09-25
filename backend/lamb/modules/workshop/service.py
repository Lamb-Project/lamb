"""Workshop service — student workspace initialization.

Reuses the chat activity's student-identity pattern (OWI user + group +
lti_activity_users) but does NOT redirect the student to OWI chat. Instead it
creates a restricted-creator principal scoped to the activity and returns a
redirect into the workshop build wizard.
"""

import logging
import secrets
import time
from typing import Any, Dict, Optional

from lamb.database_manager import LambDatabaseManager
from lamb.lti_activity_manager import LtiActivityManager
from lamb.lamb_classes import Assistant

logger = logging.getLogger(__name__)

WORKSHOP_TOKEN_TTL = 1800  # 30 minutes (student workshop session token)

_db_manager = LambDatabaseManager()


def initialize_workshop_workspace(ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Initialize a student's workshop workspace after LTI launch.

    ctx keys:
        activity (dict): The LTI activity record.
        username (str): LMS username.
        display_name (str): Student display name.
        lms_user_id (str, optional): LMS user id.
        public_base (str, optional): Public-facing base URL for redirects.

    Returns:
        dict with redirect target, session, and principal, or None on failure.
    """
    manager = LtiActivityManager()
    activity = ctx["activity"]
    public_base = ctx.get("public_base", "")

    # 1. Reuse student identity creation (OWI user + group + lti_activity_users)
    owi_token = manager.handle_student_launch(
        activity=activity,
        username=ctx["username"],
        display_name=ctx["display_name"],
        lms_user_id=ctx.get("lms_user_id"),
    )
    if not owi_token:
        logger.error("Workshop: failed to create student identity")
        return None

    # 2. Ensure a workshop session exists for this activity_user
    email = manager.generate_student_email(
        ctx["username"], activity["resource_link_id"])

    activity_user = _db_manager.get_activity_user(
        activity_id=activity["id"], user_email=email)
    if not activity_user:
        logger.error("Workshop: lti_activity_user not found after launch")
        return None

    session = _db_manager.get_or_create_workshop_session(
        activity_id=activity["id"],
        activity_user_id=activity_user.get("id"),
        owi_user_id=activity_user.get("owi_user_id"),
    )
    if not session:
        logger.error("Workshop: failed to create workshop session")
        return None

    # 3. Build a restricted creator principal for this student (virtual
    #    principal — no Creator_users row; scope bound to this activity).
    principal = {
        "type": "workshop_student",
        "activity_id": activity["id"],
        "activity_user_id": activity_user.get("id"),
        "owi_user_id": activity_user.get("owi_user_id"),
        "email": email,
        "organization_id": activity.get("organization_id"),
        "session_id": session.get("id"),
    }

    # Redirect target for the workshop build wizard (a static SPA serves this).
    token = _create_workshop_token(principal)

    # Consent gate: first visit sends the student to the consent page; once
    # consent_given_at is set (POST /workshop/consent) they skip straight in.
    if not activity_user.get("consent_given_at"):
        consent_url = (
            f"{public_base}/lamb/v1/workshop/consent?token={token}"
            if public_base
            else f"/lamb/v1/workshop/consent?token={token}"
        )
        return {
            "redirect": consent_url,
            "consent_required": True,
            "session": session,
            "principal": principal,
            "token": token,
        }

    redirect = (
        f"{public_base}/m/workshop/{activity['id']}?token={token}"
        if public_base
        else f"/m/workshop/{activity['id']}?token={token}"
    )

    return {
        "redirect": redirect,
        "session": session,
        "principal": principal,
        "token": token,
    }


def _create_workshop_token(principal: Dict[str, Any]) -> str:
    """Create a short-lived signed token for the workshop student."""
    from lamb import auth as lamb_auth
    from datetime import datetime, timedelta

    payload = {**principal, "scope": "workshop_student"}
    return lamb_auth.create_token(
        payload, expires_delta=timedelta(seconds=WORKSHOP_TOKEN_TTL))
