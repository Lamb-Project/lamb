"""
Unified LTI Router

Single LTI endpoint that supports:
- Instructor-configured activities with multiple assistants
- Student launch into configured activities (with optional consent)
- Instructor dashboard with usage stats, student log, and anonymized chat transcripts
- Identity linking for instructor identification

Session management:
- Instructor flows use LAMB JWTs (via lamb.auth) with lti_type claims
- Student consent uses short-lived in-memory tokens (one-shot flow)

Endpoint: POST /lamb/v1/lti/launch
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from lamb.lti_activity_manager import LtiActivityManager
from lamb.database_manager import LambDatabaseManager
from lamb import auth as lamb_auth
from lamb.logging_config import get_logger
from lamb.modules import get_all_modules, get_module
import os
import json
import time
import secrets
from datetime import datetime, timedelta
from lamb.modules.base import LTIContext

logger = get_logger(__name__, component="LTI_UNIFIED")

router = APIRouter()
manager = LtiActivityManager()
db_manager = LambDatabaseManager()

templates = Jinja2Templates(directory=[
    os.path.abspath("lamb/templates"),
])

SESSION_EXPIRED_HTML = "<h2>Session expired.</h2><p>Please click the LTI link in your LMS again.</p>"

# LAMB JWT expiry for LTI instructor sessions
LTI_DASHBOARD_JWT_EXPIRY = timedelta(days=7)
LTI_SETUP_JWT_EXPIRY = timedelta(hours=2)


# =============================================================================
# In-memory tokens — ONLY for student consent (short one-shot flow)
# =============================================================================
_consent_tokens: dict = {}
CONSENT_TOKEN_TTL = 600  # 10 minutes


def _create_consent_token(data: dict) -> str:
    """Create a short-lived consent token for student consent flow."""
    token = secrets.token_urlsafe(32)
    _consent_tokens[token] = {**data, "expires": time.time() + CONSENT_TOKEN_TTL}
    now = time.time()
    expired = [k for k, v in _consent_tokens.items() if v["expires"] < now]
    for k in expired:
        del _consent_tokens[k]
    return token


def _validate_consent_token(token: str) -> dict | None:
    """Validate a consent token. Returns data or None."""
    data = _consent_tokens.get(token)
    if not data:
        return None
    if time.time() > data["expires"]:
        del _consent_tokens[token]
        return None
    return data


def _consume_consent_token(token: str):
    """Remove a consent token from the store."""
    _consent_tokens.pop(token, None)


# =============================================================================
# LAMB JWT helpers for instructor sessions
# =============================================================================


def _create_dashboard_jwt(activity, instructor_user, lms_user_id: str,
                           lms_email: str = "", username: str = "") -> str:
    """Issue a LAMB JWT for instructor dashboard access."""
    return lamb_auth.create_token({
        "lti_type": "dashboard",
        "lti_resource_link_id": activity['resource_link_id'],
        "lti_activity_id": activity['id'],
        "lti_user_email": instructor_user['email'],
        "lti_display_name": instructor_user['display_name'],
        "lti_username": username,
        "lti_lms_user_id": lms_user_id,
        "lti_lms_email": lms_email,
    }, expires_delta=LTI_DASHBOARD_JWT_EXPIRY)


def _create_setup_jwt(creator_users, lms_user_id: str, lms_email: str,
                       resource_link_id: str, context_id: str = "",
                       context_title: str = "") -> str:
    """Issue a LAMB JWT for instructor setup flow."""
    return lamb_auth.create_token({
        "lti_type": "setup",
        "lti_resource_link_id": resource_link_id,
        "lti_context_id": context_id,
        "lti_context_title": context_title,
        "lti_lms_user_id": lms_user_id,
        "lti_lms_email": lms_email,
        "lti_creator_user_ids": [cu['id'] for cu in creator_users],
    }, expires_delta=LTI_SETUP_JWT_EXPIRY)


def _validate_lti_jwt(token: str, expected_type: str) -> dict | None:
    """Decode a LAMB JWT and verify it has the expected lti_type claim."""
    payload = lamb_auth.decode_token(token)
    if not payload:
        return None
    if payload.get("lti_type") != expected_type:
        return None
    return payload


def _format_timestamp(ts):
    """Format a unix timestamp for display."""
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(ts).strftime("%b %d, %Y %H:%M")
    except (ValueError, OSError):
        return "—"


def _get_activity_module(activity):
    """Resolve the ActivityModule for an activity. Raises 500 if not installed."""
    activity_type = activity.get('activity_type', 'chat')
    mod = get_module(activity_type)
    if not mod:
        raise HTTPException(status_code=500, detail=f"Module '{activity_type}' is not installed.")
    return mod


# =============================================================================
# Main Launch Endpoint
# =============================================================================

@router.post("/launch")
async def lti_launch(request: Request):
    """
    Main unified LTI launch endpoint.

    Decision tree:
    1. Validate OAuth signature
    2. Is there a configured activity for this resource_link_id?
       YES + instructor -> issue LAMB JWT -> dashboard (no OWI call yet)
       YES + student    -> consent check -> consent page OR module.on_student_launch()
       NO  + instructor -> identify as Creator user -> setup (LAMB JWT)
       NO  + student    -> "not configured yet" page
    """
    try:
        form_data = await request.form()
        post_data = dict(form_data)

        consumer_key = post_data.get("oauth_consumer_key")
        expected_key, _ = manager.get_lti_credentials()
        if not expected_key:
            logger.error("No LTI credentials configured")
            raise HTTPException(status_code=500, detail="LTI not configured")
        if consumer_key != expected_key:
            logger.error(f"Consumer key mismatch: got '{consumer_key}', expected '{expected_key}'")
            raise HTTPException(status_code=401, detail="Invalid consumer key")

        # Extract and log lis_outcome_service_url for grade passback
        lis_outcome_service_url = post_data.get("lis_outcome_service_url", "")
        if lis_outcome_service_url:
            logger.info(f"LTI Outcome Service URL received: {lis_outcome_service_url[:50]}...")

        base_url = manager.build_base_url(request)
        if not manager.validate_oauth_signature(post_data, "POST", base_url):
            raise HTTPException(status_code=401, detail="Invalid OAuth signature")

        resource_link_id = post_data.get("resource_link_id")
        if not resource_link_id:
            raise HTTPException(status_code=400, detail="Missing resource_link_id")

        roles = post_data.get("roles", "")
        lms_user_id = post_data.get("user_id", "")
        lms_email = post_data.get("lis_person_contact_email_primary", "")
        username = post_data.get("ext_user_username", "") or lms_user_id
        display_name = (post_data.get("lis_person_name_full")
                        or post_data.get("ext_user_username")
                        or lms_user_id or "LTI User")
        context_id = post_data.get("context_id", "")
        context_title = post_data.get("context_title", "")

        logger.info(f"LTI launch: resource_link={resource_link_id}, user={username}, roles={roles}")

        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)

        # Persist lis_outcome_service_url if we have it and activity exists
        if activity and lis_outcome_service_url:
            current_url = activity.get('lis_outcome_service_url')
            if current_url != lis_outcome_service_url:
                db_manager.update_lti_activity(
                    activity['id'],
                    lis_outcome_service_url=lis_outcome_service_url
                )
                logger.info(f"Updated lis_outcome_service_url for activity {resource_link_id}")

        if activity and activity['status'] == 'active':
            public_base = manager.get_public_base_url(request)

            # -- CONFIGURED: Instructor -> module dispatch --
            from lamb.modules.base import LTIContext
            if manager.is_instructor(roles):
                logger.info(f"Instructor at configured activity {resource_link_id} -> module.on_instructor_launch")
                ctx = LTIContext(
                    resource_link_id=resource_link_id,
                    lms_user_id=lms_user_id,
                    lms_email=lms_email,
                    username=username,
                    display_name=display_name,
                    roles=roles,
                    is_instructor=True,
                    context_id=context_id,
                    context_title=context_title,
                )
                module = _get_activity_module(activity)
                return module.on_instructor_launch(ctx)

            # -- CONFIGURED: Student -> consent check then module dispatch --
            from lamb.modules.base import LTIContext
            student_email = manager.generate_student_email(username, resource_link_id)
            if manager.check_student_consent(activity, student_email):
                logger.info(f"Student {student_email} needs consent for activity {resource_link_id}")
                consent_token = _create_consent_token({
                    "type": "consent",
                    "resource_link_id": resource_link_id,
                    "username": username,
                    "display_name": display_name,
                    "lms_user_id": lms_user_id,
                    "student_email": student_email,
                })
                return RedirectResponse(
                    url=f"{public_base}/m/chat/consent?token={consent_token}",
                    status_code=303
                )

            ctx = LTIContext(
                resource_link_id=resource_link_id,
                lms_user_id=lms_user_id,
                lms_email=lms_email,
                username=username,
                display_name=display_name,
                roles=roles,
                is_instructor=False,
                context_id=context_id,
                context_title=context_title,
            )
            module = _get_activity_module(activity)
            logger.info(f"Student launch -> module {activity.get('activity_type', 'chat')}")
            return module.on_student_launch(ctx)

        # -- NOT CONFIGURED --
        if not manager.is_instructor(roles):
            logger.info(f"Student arrived at unconfigured activity {resource_link_id}")
            return templates.TemplateResponse("lti_waiting.html", {
                "request": request,
                "context_title": context_title or "this course",
            })

        # -- INSTRUCTOR at unconfigured activity -> Setup flow --
        logger.info(f"Instructor setup flow for {resource_link_id}")
        creator_users = manager.identify_instructor(lms_user_id=lms_user_id, lms_email=lms_email)

        if not creator_users:
            logger.info(f"Instructor {lms_user_id} has no Creator account - showing contact-admin page")
            return templates.TemplateResponse("lti_contact_admin.html", {"request": request})

        setup_token = _create_setup_jwt(
            creator_users=[
                {"id": cu["id"], "organization_id": cu["organization_id"],
                 "user_email": cu["user_email"], "user_name": cu["user_name"]}
                for cu in creator_users
            ],
            lms_user_id=lms_user_id,
            lms_email=lms_email,
            resource_link_id=resource_link_id,
            context_id=context_id,
            context_title=context_title,
        )

        public_base = manager.get_public_base_url(request)
        redirect_url = f"{public_base}/m/chat/setup?token={setup_token}"
        logger.info(f"Redirecting instructor to setup page: {redirect_url}")
        logger.info(f"  Token length: {len(setup_token)}")
        logger.info(f"  Public base URL: {public_base}")
        
        return RedirectResponse(
            url=redirect_url,
            status_code=303
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in LTI launch: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LTI launch failed: {str(e)}")


# =============================================================================
# Setup Page
# =============================================================================

@router.get("/setup/info")
async def lti_setup_info(request: Request, token: str = ""):
    """
    Return JSON data for the SvelteKit frontend to render the setup page.
    Accepts a setup JWT (first time) or dashboard JWT (reconfigure).
    """
    data = _validate_lti_jwt(token, "setup")
    if not data:
        data = _validate_lti_jwt(token, "dashboard")
    if not data:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

    resource_link_id = data.get("lti_resource_link_id")

    if data.get("lti_type") == "setup":
        # Re-fetch creator users from DB using IDs stored in JWT
        creator_user_ids = data.get("lti_creator_user_ids", [])
        creator_users = []
        for uid in creator_user_ids:
            cu = db_manager.get_creator_user_by_id(uid)
            if cu:
                creator_users.append({
                    "id": cu['id'],
                    "organization_id": cu['organization_id'],
                    "user_email": cu['user_email'],
                    "user_name": cu['user_name'],
                })
    else:
        # Dashboard JWT used for reconfigure - re-identify instructor dynamically
        lms_user_id = data.get("lti_lms_user_id", "")
        lms_email = data.get("lti_lms_email", "")
        creator_users_raw = manager.identify_instructor(lms_user_id, lms_email)
        creator_users = [
            {"id": cu["id"], "organization_id": cu["organization_id"],
             "user_email": cu["user_email"], "user_name": cu["user_name"]}
            for cu in (creator_users_raw or [])
        ]

    if not creator_users:
        return JSONResponse({"detail": "Could not identify your Creator account."}, status_code=403)

    orgs_with_assistants = manager.get_published_assistants_for_instructor(creator_users)

    org_names = {}
    for org_id in orgs_with_assistants:
        org = db_manager.get_organization_by_id(org_id)
        if org:
            org_names[org_id] = org.get('name', f'Organization {org_id}')

    needs_org_selection = len(orgs_with_assistants) > 1

    def _field_to_json(f):
        row = {"name": f.name, "label": f.label, "type": f.field_type, "required": f.required}
        if f.field_type == "select" and getattr(f, "options", None):
            row["options"] = [{"value": o["value"], "label": o["label"]} for o in f.options]
        return row

    return JSONResponse({
        "resource_link_id": resource_link_id,
        "context_title": data.get("lti_context_title", ""),
        "needs_org_selection": needs_org_selection,
        "org_names": org_names,
        "orgs_with_assistants": orgs_with_assistants,
        "modules": [{"name": m.name, "display_name": getattr(m, 'display_name', m.name), "description": getattr(m, 'description', '')} for m in get_all_modules()],
        "modules_fields": {
            m.name: [_field_to_json(f) for f in m.get_setup_fields()]
            for m in get_all_modules()
        }
    })


# =============================================================================
# Configure Activity (form submit from setup page)
# =============================================================================

@router.post("/configure")
async def lti_configure_activity(request: Request):
    """
    Process the activity configuration form. Two-phase:
    1. manager.configure_activity() - creates DB record (DB-only, owi fields empty)
    2. module.on_activity_configured() - creates external resources (OWI group, model permissions)
    Then redirects the instructor to the dashboard.
    """
    try:
        payload = await request.json()
        token = payload.get("token", "")
        data = _validate_lti_jwt(token, "setup")
        if not data:
            return JSONResponse({"detail": "Session expired"}, status_code=403)

        organization_id = int(payload.get("organization_id", 0))
        assistant_ids_raw = payload.get("assistant_ids", [])
        assistant_ids = [int(x) for x in assistant_ids_raw if x]
        activity_type = payload.get("activity_type", "chat")
        chat_visibility_enabled = bool(payload.get("chat_visibility_enabled"))

        if not organization_id:
            return JSONResponse({"detail": "No organization selected"}, status_code=400)
        if not assistant_ids:
            return JSONResponse({"detail": "Please select at least one assistant"}, status_code=400)

        # Re-fetch creator user from JWT (never trust form data for identity)
        creator_user_ids = data.get("lti_creator_user_ids", [])
        creator_user = None
        for uid in creator_user_ids:
            cu = db_manager.get_creator_user_by_id(uid)
            if cu and cu.get('organization_id') == organization_id:
                creator_user = {
                    "id": cu['id'],
                    "organization_id": cu['organization_id'],
                    "user_email": cu['user_email'],
                    "user_name": cu['user_name'],
                }
                break

        if not creator_user:
            return JSONResponse({"detail": "You don't have access to this organization"}, status_code=403)

        resource_link_id = data.get("lti_resource_link_id")
        context_id = data.get("lti_context_id", "")
        context_title = data.get("lti_context_title", "")

        # Phase 1: create DB record (owi fields empty at this point)
        activity = manager.configure_activity(
            resource_link_id=resource_link_id,
            organization_id=organization_id,
            assistant_ids=assistant_ids,
            configured_by_email=creator_user["user_email"],
            configured_by_name=creator_user.get("user_name"),
            context_id=context_id,
            context_title=context_title,
            activity_name=context_title or resource_link_id,
            chat_visibility_enabled=chat_visibility_enabled,
            activity_type=activity_type,
        )

        if not activity:
            logger.error(f"Failed to configure activity {resource_link_id}")
            return JSONResponse({"detail": "Failed to configure activity"}, status_code=500)

        # Phase 2: module hook (creates OWI group, adds model permissions, updates DB)
        module = _get_activity_module(activity)
        reserved = {"token", "organization_id", "assistant_ids", "activity_type", "chat_visibility_enabled"}
        extras = {k: v for k, v in payload.items() if k not in reserved}
        setup_data = {
            "resource_link_id": resource_link_id,
            "assistant_ids": assistant_ids,
            "configured_by_email": creator_user["user_email"],
            "activity_name": context_title or resource_link_id,
            "chat_visibility_enabled": chat_visibility_enabled,
            **extras,
        }
        module.on_activity_configured(activity['id'], setup_data)

        # Re-fetch activity: module may have filled in OWI fields
        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)

        logger.info(f"Activity {resource_link_id} configured: {len(assistant_ids)} assistants, type={activity_type}")

        # Issue dashboard JWT - OWI user is created on first "Enter Chat"
        lms_user_id = data.get("lti_lms_user_id", "")
        lms_email = data.get("lti_lms_email", "")
        username = lms_user_id or "instructor"
        instructor_email = manager.generate_student_email(username, activity['resource_link_id'])
        instructor_user = {
            "email": instructor_email,
            "display_name": creator_user.get("user_name", "Instructor"),
        }

        dashboard_token = _create_dashboard_jwt(
            activity, instructor_user, lms_user_id, lms_email, username=username)

        public_base = manager.get_public_base_url(request)
        at = activity.get("activity_type") or "chat"
        if at == "file_evaluation":
            redirect_url = (
                f"{public_base}/m/file-eval/grading?activity_id={activity['id']}&token={dashboard_token}"
            )
        else:
            redirect_url = f"{public_base}/m/chat/dashboard?resource_link_id={resource_link_id}&token={dashboard_token}"
        return JSONResponse({
            "status": "success",
            "redirect_url": redirect_url,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring activity: {str(e)}", exc_info=True)
        return JSONResponse({"detail": str(e)}, status_code=500)


# =============================================================================
# Link Account Page (fallback when instructor not auto-identified)
# =============================================================================

@router.get("/link-account")
async def lti_link_account_page(request: Request, token: str = ""):
    """Show the account-linking form for unidentified instructors."""
    data = _validate_lti_jwt(token, "setup")
    if not data:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

    return templates.TemplateResponse("lti_link_account.html", {
        "request": request,
        "token": token,
        "error": "",
    })


@router.post("/link-account")
async def lti_link_account_submit(request: Request):
    """
    Process the account-linking form.
    Verifies credentials via manager.verify_creator_credentials(), links the
    LMS identity to the Creator user, then issues a new setup JWT.
    """
    try:
        form_data = await request.form()
        token = form_data.get("token", "")
        email = form_data.get("email", "").strip()
        password = form_data.get("password", "")

        data = _validate_lti_jwt(token, "setup")
        if not data:
            return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

        if not email or not password:
            return templates.TemplateResponse("lti_link_account.html", {
                "request": request,
                "token": token,
                "error": "Please enter your email and password.",
            })

        creator_user = manager.verify_creator_credentials(email, password)
        if not creator_user:
            return templates.TemplateResponse("lti_link_account.html", {
                "request": request,
                "token": token,
                "error": "Invalid credentials. Please check your LAMB Creator email and password.",
            })

        lms_user_id = data.get("lti_lms_user_id", "")
        lms_email = data.get("lti_lms_email", "")
        manager.link_identity(
            lms_user_id=lms_user_id,
            creator_user_id=creator_user["id"],
            lms_email=lms_email
        )
        logger.info(f"Linked LMS user {lms_user_id} to Creator user {creator_user['user_email']}")

        new_token = _create_setup_jwt(
            creator_users=[{
                "id": creator_user["id"],
                "organization_id": creator_user["organization_id"],
                "user_email": creator_user["user_email"],
                "user_name": creator_user["user_name"],
            }],
            lms_user_id=lms_user_id,
            lms_email=lms_email,
            resource_link_id=data.get("lti_resource_link_id", ""),
            context_id=data.get("lti_context_id", ""),
            context_title=data.get("lti_context_title", ""),
        )

        public_base = manager.get_public_base_url(request)
        return RedirectResponse(
            url=f"{public_base}/lamb/v1/lti/setup?token={new_token}",
            status_code=303
        )

    except Exception as e:
        logger.error(f"Error linking account: {str(e)}", exc_info=True)
        return HTMLResponse(f"<h2>Error</h2><p>{str(e)}</p>", status_code=500)


# =============================================================================
# Reconfigure Activity
# =============================================================================

@router.post("/reconfigure")
async def lti_reconfigure_activity(request: Request):
    """Reconfigure an existing activity's assistant selection. Owner only."""
    try:
        form_data = await request.form()
        token = form_data.get("token", "")
        data = _validate_lti_jwt(token, "dashboard")
        if not data:
            return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

        resource_link_id = data.get("lti_resource_link_id")
        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
        if not activity:
            return HTMLResponse("<h2>Error</h2><p>Activity not found.</p>", status_code=404)

        # Dynamic owner check (resolves LMS identity -> Creator user -> compares with owner_email)
        is_owner = manager.determine_is_owner(
            activity,
            lms_user_id=data.get("lti_lms_user_id", ""),
            lms_email=data.get("lti_lms_email", "")
        )
        if not is_owner:
            return HTMLResponse(
                "<h2>Access Denied</h2><p>Only the activity owner can reconfigure assistants.</p>",
                status_code=403
            )

        assistant_ids_str = form_data.getlist("assistant_ids")
        assistant_ids = [int(x) for x in assistant_ids_str if x]
        if not assistant_ids:
            return HTMLResponse("<h2>Error</h2><p>Please select at least one assistant.</p>", status_code=400)

        chat_visibility_str = form_data.get("chat_visibility_enabled")
        if chat_visibility_str is not None:
            new_chat_vis = 1 if chat_visibility_str == "1" else 0
            if new_chat_vis != activity.get('chat_visibility_enabled', 0):
                db_manager.update_lti_activity(activity['id'], chat_visibility_enabled=new_chat_vis)

        # DB update - returns (added_ids, removed_ids)
        added_ids, removed_ids = manager.reconfigure_activity(activity, assistant_ids)

        # Module hook: update external resources (OWI model permissions)
        module = _get_activity_module(activity)
        module.on_activity_reconfigured(activity, added_ids, removed_ids)

        public_base = manager.get_public_base_url(request)
        return RedirectResponse(
            url=f"{public_base}/lamb/v1/lti/dashboard?resource_link_id={resource_link_id}&token={token}",
            status_code=303
        )

    except Exception as e:
        logger.error(f"Error reconfiguring activity: {str(e)}", exc_info=True)
        return HTMLResponse(f"<h2>Error</h2><p>{str(e)}</p>", status_code=500)


# =============================================================================
# Info endpoint
# =============================================================================

@router.get("/info")
async def lti_info():
    """Return LTI configuration info for LMS administrators."""
    consumer_key, _ = manager.get_lti_credentials()
    return JSONResponse({
        "name": "LAMB Unified LTI Tool",
        "description": "Single LTI tool for LAMB — instructors configure which assistants are available per activity",
        "launch_url": "/lamb/v1/lti/launch",
        "consumer_key": consumer_key,
        "consumer_secret": "(configured by administrator)",
        "required_parameters": [
            "oauth_consumer_key",
            "resource_link_id",
            "user_id",
            "roles"
        ],
        "optional_parameters": [
            "lis_person_contact_email_primary",
            "lis_person_name_full",
            "ext_user_username",
            "context_id",
            "context_title"
        ],
        "notes": [
            "Global consumer key/secret — one LTI tool for the entire LAMB instance",
            "Instructors configure assistant selection on first launch",
            "Activities are bound to one organization"
        ]
    })


# =============================================================================
# Student Consent (in-memory tokens — short one-shot flow)
# =============================================================================

@router.get("/consent/info")
async def lti_consent_info(request: Request, token: str = ""):
    """Return JSON data for the student consent page."""
    data = _validate_consent_token(token)
    if not data or data.get("type") != "consent":
        return JSONResponse({"detail": "Session expired"}, status_code=403)

    resource_link_id = data["resource_link_id"]
    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        return JSONResponse({"detail": "Activity not found"}, status_code=404)

    return JSONResponse({
        "activity_name": activity.get("activity_name", "LTI Activity"),
        "context_title": activity.get("context_title", ""),
    })


@router.post("/consent")
async def lti_consent_submit(request: Request):
    """Process student consent acceptance and return redirect URL."""
    try:
        payload = await request.json()
        token = payload.get("token", "")
        data = _validate_consent_token(token)
        if not data or data.get("type") != "consent":
            return JSONResponse({"detail": "Session expired"}, status_code=403)

        resource_link_id = data["resource_link_id"]
        student_email = data["student_email"]
        username = data["username"]
        display_name = data["display_name"]
        lms_user_id = data.get("lms_user_id")

        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
        if not activity:
            return JSONResponse({"detail": "Activity not found"}, status_code=404)

        # Record consent before launching
        db_manager.create_lti_activity_user(
            activity_id=activity['id'],
            user_email=student_email,
            user_name=username,
            user_display_name=display_name,
            lms_user_id=lms_user_id
        )
        db_manager.record_student_consent(activity['id'], student_email)
        logger.info(f"Student {student_email} gave consent for activity {resource_link_id}")

        _consume_consent_token(token)

        # Delegate launch to module (returns redirect URL)
        module = _get_activity_module(activity)
        redirect_url = module.launch_user(
            activity=activity,
            username=username,
            display_name=display_name,
            lms_user_id=lms_user_id,
        )

        if not redirect_url:
            return JSONResponse({"detail": "Failed to launch. Please try again."}, status_code=500)

        return JSONResponse({"status": "success", "redirect_url": redirect_url})

    except Exception as e:
        logger.error(f"Error processing consent: {str(e)}", exc_info=True)
        return JSONResponse({"detail": str(e)}, status_code=500)


# =============================================================================
# Instructor Dashboard
# =============================================================================

@router.get("/dashboard/info")
async def lti_dashboard_info(request: Request, resource_link_id: str = "", token: str = ""):
    """Return JSON data for the instructor dashboard header."""
    data = _validate_lti_jwt(token, "dashboard")
    if not data:
        return JSONResponse({"detail": "Session expired"}, status_code=403)

    if data.get("lti_resource_link_id") != resource_link_id:
        return JSONResponse({"detail": "Invalid request"}, status_code=400)

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        return JSONResponse({"detail": "Activity not found"}, status_code=404)

    is_owner = manager.determine_is_owner(
        activity,
        lms_user_id=data.get("lti_lms_user_id", ""),
        lms_email=data.get("lti_lms_email", "")
    )

    org = db_manager.get_organization_by_id(activity['organization_id'])
    org_name = org.get('name', 'Unknown') if org else 'Unknown'

    return JSONResponse({
        "activity_name": activity.get('activity_name', 'LTI Activity'),
        "context_title": activity.get('context_title', ''),
        "org_name": org_name,
        "owner_name": activity.get('owner_name') or activity.get('owner_email'),
        "created_at": activity.get('created_at'),
        "chat_visibility_enabled": bool(activity.get('chat_visibility_enabled')),
        "is_owner": is_owner
    })


# =============================================================================
# Dashboard Data API (JSON)
# =============================================================================

@router.get("/dashboard/stats")
async def lti_dashboard_stats(resource_link_id: str = "", token: str = ""):
    """Return dashboard stats as JSON."""
    data = _validate_lti_jwt(token, "dashboard")
    if not data:
        raise HTTPException(status_code=403, detail="Invalid token")

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    module = _get_activity_module(activity)
    return JSONResponse(module.get_dashboard_stats(activity))


@router.get("/dashboard/students")
async def lti_dashboard_students(resource_link_id: str = "", token: str = "",
                                  page: int = 1, per_page: int = 20):
    """Return anonymized student list as JSON."""
    data = _validate_lti_jwt(token, "dashboard")
    if not data:
        raise HTTPException(status_code=403, detail="Invalid token")

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    return JSONResponse(manager.get_dashboard_students(activity['id'], page, per_page))


@router.get("/dashboard/chats")
async def lti_dashboard_chats(resource_link_id: str = "", token: str = "",
                               assistant_id: int = None,
                               page: int = 1, per_page: int = 20):
    """Return anonymized chat list as JSON. Requires chat_visibility enabled."""
    data = _validate_lti_jwt(token, "dashboard")
    if not data:
        raise HTTPException(status_code=403, detail="Invalid token")

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if not activity.get('chat_visibility_enabled'):
        raise HTTPException(status_code=403, detail="Chat visibility not enabled")

    module = _get_activity_module(activity)
    return JSONResponse(module.get_dashboard_chats(activity, assistant_id, page, per_page))


@router.get("/dashboard/chats/{chat_id}")
async def lti_dashboard_chat_detail(chat_id: str, resource_link_id: str = "",
                                     token: str = ""):
    """Return a single chat transcript as JSON. Requires chat_visibility enabled."""
    data = _validate_lti_jwt(token, "dashboard")
    if not data:
        raise HTTPException(status_code=403, detail="Invalid token")

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if not activity.get('chat_visibility_enabled'):
        raise HTTPException(status_code=403, detail="Chat visibility not enabled")

    module = _get_activity_module(activity)
    detail = module.get_dashboard_chat_detail(activity, chat_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Chat not found")

    return JSONResponse(detail)


# =============================================================================
# Instructor -> Activity (Enter Chat)
# =============================================================================

@router.get("/enter-chat")
async def lti_enter_chat(request: Request, resource_link_id: str = "", token: str = ""):
    """
    Redirect instructor from dashboard into the activity (e.g. OWI for chat module).
    Delegates to module.launch_user(is_instructor=True) which creates/gets the OWI user.
    """
    data = _validate_lti_jwt(token, "dashboard")
    if not data:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        return HTMLResponse("<h2>Activity not found.</h2>", status_code=404)

    display_name = data.get("lti_display_name", "Instructor")
    lms_user_id = data.get("lti_lms_user_id", "")
    username = data.get("lti_username", lms_user_id)

    module = _get_activity_module(activity)
    redirect_url = module.launch_user(
        activity=activity,
        username=username,
        display_name=display_name,
        lms_user_id=lms_user_id,
        is_instructor=True,
    )

    if not redirect_url:
        return HTMLResponse("<h2>Error</h2><p>Failed to access chat. Please try again.</p>", status_code=500)

    return RedirectResponse(url=redirect_url, status_code=303)
