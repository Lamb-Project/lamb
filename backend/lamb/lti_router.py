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
import os
import json
import time
import secrets
from datetime import datetime, timedelta
<<<<<<< HEAD
from lamb.modules import get_all_modules
=======
>>>>>>> dev

logger = get_logger(__name__, component="LTI_UNIFIED")

router = APIRouter()
manager = LtiActivityManager()
db_manager = LambDatabaseManager()

templates = Jinja2Templates(directory=[
    os.path.abspath("lamb/templates"),
])

SESSION_EXPIRED_HTML = "<h2>Session expired.</h2><p>Please click the LTI link in your LMS again.</p>"

# LAMB JWT expiry for LTI instructor sessions (dashboard, setup)
LTI_DASHBOARD_JWT_EXPIRY = timedelta(days=7)
LTI_SETUP_JWT_EXPIRY = timedelta(hours=2)
<<<<<<< HEAD

=======
>>>>>>> dev

# =============================================================================
# In-memory tokens — kept ONLY for student consent (short one-shot flow)
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

<<<<<<< HEAD

=======
>>>>>>> dev
def _create_dashboard_jwt(activity, instructor_user, lms_user_id: str,
                           lms_email: str = "",
                           username: str = "") -> str:
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
       YES + instructor → create activity user, issue LAMB JWT → dashboard
       YES + student    → consent check → OWI redirect
       NO  + instructor → identify as Creator user → setup (LAMB JWT)
       NO  + student    → "not configured yet" page
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

        if activity and activity['status'] == 'active':
            from lamb.modules import get_module
            from lamb.modules.base import LTIContext
            
            activity_type = activity.get('activity_type', 'chat')
            module = get_module(activity_type)
            if not module:
                logger.error(f"Module {activity_type} not found for activity {resource_link_id}")
                raise HTTPException(status_code=500, detail=f"Module {activity_type} is not installed.")

<<<<<<< HEAD
            ctx = LTIContext(
                resource_link_id=resource_link_id,
                lms_user_id=lms_user_id,
                lms_email=lms_email,
=======
            # ── CONFIGURED: Instructor → issue dashboard JWT (no OWI calls) ──
            if manager.is_instructor(roles):
                logger.info(f"Instructor accessing configured activity {resource_link_id} → dashboard")

                # Build instructor info from LTI params only — no OWI user
                # creation here. OWI user is created when "Enter Chat" is clicked.
                instructor_email = manager.generate_student_email(username, resource_link_id)
                instructor_user = {
                    "email": instructor_email,
                    "display_name": display_name,
                }

                dashboard_token = _create_dashboard_jwt(
                    activity, instructor_user, lms_user_id, lms_email,
                    username=username)

                return RedirectResponse(
                    url=f"{public_base}/lamb/v1/lti/dashboard?resource_link_id={resource_link_id}&token={dashboard_token}",
                    status_code=303
                )

            # ── CONFIGURED: Student flow ──
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
                    url=f"{public_base}/lamb/v1/lti/consent?token={consent_token}",
                    status_code=303
                )

            owi_token = manager.handle_student_launch(
                activity=activity,
>>>>>>> dev
                username=username,
                display_name=display_name,
                roles=roles,
                is_instructor=manager.is_instructor(roles),
                context_id=context_id,
                context_title=context_title
            )

            # ── CONFIGURED: Module Dispatch ──
            if ctx.is_instructor:
                logger.info(f"Instructor accessing configured activity {resource_link_id} → delegating to module {activity_type}")
                return module.on_instructor_launch(ctx)
            else:
                logger.info(f"Student accessing configured activity {resource_link_id} → delegating to module {activity_type}")
                # For chat (the only one right now), consent is still needed inside the router 
                # before we dispatch to the module, to avoid making every module re-implement consent checking.
                student_email = manager.generate_student_email(username, resource_link_id)
                if manager.check_student_consent(activity, student_email):
                    public_base = manager.get_public_base_url(request)
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
                        url=f"{public_base}/lamb/v1/lti/consent?token={consent_token}",
                        status_code=303
                    )
                
                return module.on_student_launch(ctx)

        # ── NOT CONFIGURED ──
        if not manager.is_instructor(roles):
            logger.info(f"Student arrived at unconfigured activity {resource_link_id}")
            return templates.TemplateResponse("lti_waiting.html", {
                "request": request,
                "context_title": context_title or "this course",
            })

        # ── INSTRUCTOR at unconfigured activity → Setup flow ──
        logger.info(f"Instructor setup flow for {resource_link_id}")

        creator_users = manager.identify_instructor(
            lms_user_id=lms_user_id,
            lms_email=lms_email
        )

        if not creator_users:
            logger.info(f"Instructor {lms_user_id} has no Creator account — showing contact-admin page")
            return templates.TemplateResponse("lti_contact_admin.html", {
                "request": request,
            })

<<<<<<< HEAD
        # Instructor identified — issue setup JWT and redirect to setup page
=======
>>>>>>> dev
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
        return RedirectResponse(
            url=f"{public_base}/lamb/v1/lti/setup?token={setup_token}",
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

@router.get("/setup")
async def lti_setup_page(request: Request, token: str = ""):
    """
    Serve the activity setup page for instructors.
    Requires a valid setup JWT or dashboard JWT (for reconfigure).
    """
    # Try setup JWT first, then dashboard JWT (for reconfigure link)
    data = _validate_lti_jwt(token, "setup")
    if not data:
        data = _validate_lti_jwt(token, "dashboard")
    if not data:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

    resource_link_id = data.get("lti_resource_link_id")

    if data.get("lti_type") == "setup":
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
        # Dashboard JWT used for reconfigure — resolve instructor identity
        lms_user_id = data.get("lti_lms_user_id", "")
        lms_email = data.get("lti_lms_email", "")
        creator_users_raw = manager.identify_instructor(lms_user_id, lms_email)
        creator_users = [
            {"id": cu["id"], "organization_id": cu["organization_id"],
             "user_email": cu["user_email"], "user_name": cu["user_name"]}
            for cu in (creator_users_raw or [])
        ]

    if not creator_users:
        return HTMLResponse("<h2>Error</h2><p>Could not identify your Creator account.</p>", status_code=403)

    orgs_with_assistants = manager.get_published_assistants_for_instructor(creator_users)

    org_names = {}
    for org_id in orgs_with_assistants:
        org = db_manager.get_organization_by_id(org_id)
        if org:
            org_names[org_id] = org.get('name', f'Organization {org_id}')

    needs_org_selection = len(orgs_with_assistants) > 1

    return templates.TemplateResponse("lti_activity_setup.html", {
        "request": request,
        "token": token,
        "resource_link_id": resource_link_id,
        "context_title": data.get("lti_context_title", ""),
        "needs_org_selection": needs_org_selection,
        "orgs_with_assistants": orgs_with_assistants,
        "org_names": org_names,
        "modules": get_all_modules(),
        "modules_json": json.dumps({
            m.name: [
                {"name": f.name, "label": f.label, "type": f.field_type, "required": f.required} 
                for f in m.get_setup_fields()
            ] for m in get_all_modules()
        }),
        "orgs_json": json.dumps({
            str(org_id): [
                {"id": a["id"], "name": a["name"], "owner": a["owner"],
                 "access_type": a.get("access_type", "owned")}
                for a in assistants
            ]
            for org_id, assistants in orgs_with_assistants.items()
        }),
    })


# =============================================================================
# Configure Activity (form submit from setup page)
# =============================================================================

@router.post("/configure")
async def lti_configure_activity(request: Request):
    """
    Process the activity configuration form.
    Creates the OWI group, adds model permissions, stores activity record.
    Then redirects the instructor to the dashboard.
    """
    try:
        form_data = await request.form()
        token = form_data.get("token", "")
        data = _validate_lti_jwt(token, "setup")
        if not data:
            return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

        organization_id = int(form_data.get("organization_id", 0))
        assistant_ids_str = form_data.getlist("assistant_ids")
        assistant_ids = [int(x) for x in assistant_ids_str if x]
        activity_type = form_data.get("activity_type", "chat")
        chat_visibility_enabled = form_data.get("chat_visibility_enabled") == "1"

        if not organization_id:
            return HTMLResponse("<h2>Error</h2><p>No organization selected.</p>", status_code=400)
        if not assistant_ids:
            return HTMLResponse("<h2>Error</h2><p>Please select at least one assistant.</p>", status_code=400)

        # Re-fetch creator users from JWT
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
            return HTMLResponse("<h2>Error</h2><p>You don't have access to this organization.</p>", status_code=403)

        resource_link_id = data.get("lti_resource_link_id")
        context_id = data.get("lti_context_id", "")
        context_title = data.get("lti_context_title", "")

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
            return HTMLResponse("<h2>Error</h2><p>Failed to configure activity. Please try again.</p>", status_code=500)

        logger.info(f"Activity {resource_link_id} configured with {len(assistant_ids)} assistants, chat_visibility={chat_visibility_enabled}")

        # Issue dashboard JWT — no OWI user creation needed here
        lms_user_id = data.get("lti_lms_user_id", "")
        lms_email = data.get("lti_lms_email", "")
        username = lms_user_id or "instructor"

        instructor_email = manager.generate_student_email(username, activity['resource_link_id'])
        instructor_user = {
            "email": instructor_email,
            "display_name": creator_user.get("user_name", "Instructor"),
        }

        dashboard_token = _create_dashboard_jwt(
            activity, instructor_user, lms_user_id, lms_email,
            username=username)

        public_base = manager.get_public_base_url(request)
        return RedirectResponse(
            url=f"{public_base}/lamb/v1/lti/dashboard?resource_link_id={resource_link_id}&token={dashboard_token}",
            status_code=303
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring activity: {str(e)}", exc_info=True)
        return HTMLResponse(f"<h2>Error</h2><p>{str(e)}</p>", status_code=500)


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
    Verifies credentials, creates the identity link, then redirects to setup
    with a new JWT that includes the linked creator user.
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

        # Issue a new setup JWT with the linked creator user
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

        # Dynamic owner check
        is_owner = manager.determine_is_owner(
            activity,
            lms_user_id=data.get("lti_lms_user_id", ""),
            lms_email=data.get("lti_lms_email", "")
        )
        if not is_owner:
            return HTMLResponse("<h2>Access Denied</h2><p>Only the activity owner can reconfigure assistants.</p>", status_code=403)

        assistant_ids_str = form_data.getlist("assistant_ids")
        assistant_ids = [int(x) for x in assistant_ids_str if x]
        if not assistant_ids:
            return HTMLResponse("<h2>Error</h2><p>Please select at least one assistant.</p>", status_code=400)

        chat_visibility_str = form_data.get("chat_visibility_enabled")
        if chat_visibility_str is not None:
            new_chat_vis = 1 if chat_visibility_str == "1" else 0
            if new_chat_vis != activity.get('chat_visibility_enabled', 0):
                db_manager.update_lti_activity(activity['id'], chat_visibility_enabled=new_chat_vis)

        success = manager.reconfigure_activity(activity, assistant_ids)
        if not success:
            return HTMLResponse("<h2>Error</h2><p>Failed to reconfigure.</p>", status_code=500)

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

@router.get("/consent")
async def lti_consent_page(request: Request, token: str = ""):
    """Show the student consent page for chat visibility."""
    data = _validate_consent_token(token)
    if not data or data.get("type") != "consent":
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

    resource_link_id = data["resource_link_id"]
    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        return HTMLResponse("<h2>Error</h2><p>Activity not found.</p>", status_code=404)

    return templates.TemplateResponse("lti_consent.html", {
        "request": request,
        "token": token,
        "activity_name": activity.get("activity_name", "LTI Activity"),
        "context_title": activity.get("context_title", ""),
    })


@router.post("/consent")
async def lti_consent_submit(request: Request):
    """Process student consent acceptance."""
    try:
        form_data = await request.form()
        token = form_data.get("token", "")
        data = _validate_consent_token(token)
        if not data or data.get("type") != "consent":
            return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

        resource_link_id = data["resource_link_id"]
        student_email = data["student_email"]
        username = data["username"]
        display_name = data["display_name"]
        lms_user_id = data.get("lms_user_id")

        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
        if not activity:
            return HTMLResponse("<h2>Error</h2><p>Activity not found.</p>", status_code=404)

        db_manager.create_lti_activity_user(
            activity_id=activity['id'],
            user_email=student_email,
            user_name=username,
            user_display_name=display_name,
            lms_user_id=lms_user_id
        )
        db_manager.record_student_consent(activity['id'], student_email)
        logger.info(f"Student {student_email} gave consent for activity {resource_link_id}")

        owi_token = manager.handle_student_launch(
            activity=activity,
            username=username,
            display_name=display_name,
            lms_user_id=lms_user_id
        )

        _consume_consent_token(token)

        if not owi_token:
            return HTMLResponse("<h2>Error</h2><p>Failed to launch. Please try again.</p>", status_code=500)

        redirect_url = manager.get_owi_redirect_url(owi_token)
        return RedirectResponse(url=redirect_url, status_code=303)

    except Exception as e:
        logger.error(f"Error processing consent: {str(e)}", exc_info=True)
        return HTMLResponse(f"<h2>Error</h2><p>{str(e)}</p>", status_code=500)


# =============================================================================
# Instructor Dashboard
# =============================================================================

@router.get("/dashboard")
async def lti_dashboard(request: Request, resource_link_id: str = "", token: str = ""):
    """Serve the instructor dashboard page."""
    data = _validate_lti_jwt(token, "dashboard")
    if not data:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)

    if data.get("lti_resource_link_id") != resource_link_id:
        return HTMLResponse("<h2>Invalid request.</h2>", status_code=400)

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        return HTMLResponse("<h2>Activity not found.</h2>", status_code=404)

    is_owner = manager.determine_is_owner(
        activity,
        lms_user_id=data.get("lti_lms_user_id", ""),
        lms_email=data.get("lti_lms_email", "")
    )

    org = db_manager.get_organization_by_id(activity['organization_id'])
    org_name = org.get('name', 'Unknown') if org else 'Unknown'

    stats = manager.get_dashboard_stats(activity)
    students = manager.get_dashboard_students(activity['id'])

    chats = {"chats": [], "total": 0}
    if activity.get('chat_visibility_enabled'):
        chats = manager.get_dashboard_chats(activity)

    created_date = _format_timestamp(activity.get('created_at'))

    return templates.TemplateResponse("lti_dashboard.html", {
        "request": request,
        "activity": activity,
        "token": token,
        "is_owner": is_owner,
        "org_name": org_name,
        "stats": stats,
        "students": students,
        "chats": chats,
        "created_date": created_date,
        "format_ts": _format_timestamp,
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

    stats = manager.get_dashboard_stats(activity)
    return JSONResponse(stats)


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

    students = manager.get_dashboard_students(activity['id'], page, per_page)
    return JSONResponse(students)


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

    chats = manager.get_dashboard_chats(activity, assistant_id, page, per_page)
    return JSONResponse(chats)


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

    detail = manager.get_dashboard_chat_detail(activity, chat_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Chat not found")

    return JSONResponse(detail)


# =============================================================================
# Instructor → OWI (Enter Chat)
# =============================================================================

@router.get("/enter-chat")
async def lti_enter_chat(request: Request, resource_link_id: str = "", token: str = ""):
    """
    Redirect instructor from dashboard to OWI.
    Creates/gets OWI user via handle_student_launch (get-or-create) and redirects.
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

    owi_token = manager.handle_student_launch(
        activity=activity,
        username=username,
        display_name=display_name,
        lms_user_id=lms_user_id,
        is_instructor=True,
    )

    if not owi_token:
        return HTMLResponse("<h2>Error</h2><p>Failed to access chat. Please try again.</p>", status_code=500)

    redirect_url = manager.get_owi_redirect_url(owi_token)
    return RedirectResponse(url=redirect_url, status_code=303)
