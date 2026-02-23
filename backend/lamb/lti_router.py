"""
Unified LTI Router

Single LTI endpoint that supports:
- Instructor-configured activities with multiple assistants
- Student launch into configured activities (with optional consent)
- Instructor dashboard with usage stats, student log, and anonymized chat transcripts
- Identity linking for instructor identification

Endpoint: POST /lamb/v1/lti/launch
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from lamb.lti_activity_manager import LtiActivityManager
from lamb.database_manager import LambDatabaseManager
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.logging_config import get_logger
import os
import json
import time
import secrets
from datetime import datetime

logger = get_logger(__name__, component="LTI_UNIFIED")

router = APIRouter()
manager = LtiActivityManager()
db_manager = LambDatabaseManager()

templates = Jinja2Templates(directory=[
    os.path.abspath("lamb/templates"),
])


# =============================================================================
# Token store — short-lived tokens for setup, dashboard, and consent flows
# In-memory store (cleared on restart, which is fine)
# =============================================================================
_tokens: dict = {}
SETUP_TOKEN_TTL = 600       # 10 minutes (setup / reconfigure)
DASHBOARD_TOKEN_TTL = 1800  # 30 minutes (dashboard)
CONSENT_TOKEN_TTL = 600     # 10 minutes (consent flow)


def _create_token(data: dict, ttl: int = SETUP_TOKEN_TTL) -> str:
    """Create a short-lived token."""
    token = secrets.token_urlsafe(32)
    _tokens[token] = {**data, "expires": time.time() + ttl}
    # Prune expired tokens occasionally
    now = time.time()
    expired = [k for k, v in _tokens.items() if v["expires"] < now]
    for k in expired:
        del _tokens[k]
    return token


def _validate_token(token: str) -> dict | None:
    """Validate a token (does NOT consume it). Returns data or None."""
    data = _tokens.get(token)
    if not data:
        return None
    if time.time() > data["expires"]:
        del _tokens[token]
        return None
    return data


def _consume_token(token: str):
    """Remove a token from the store."""
    _tokens.pop(token, None)


# Backward compatibility aliases
def _create_setup_token(data: dict) -> str:
    return _create_token(data, SETUP_TOKEN_TTL)

def _validate_setup_token(token: str) -> dict | None:
    return _validate_token(token)


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
       YES → launch user into OWI (student flow)
       NO  → is the user an instructor?
             YES → identify as Creator user → show setup
             NO  → show "not configured yet" page
    """
    try:
        form_data = await request.form()
        post_data = dict(form_data)

        # Validate we have a consumer key
        consumer_key = post_data.get("oauth_consumer_key")
        expected_key, _ = manager.get_lti_credentials()
        if not expected_key:
            logger.error("No LTI credentials configured")
            raise HTTPException(status_code=500, detail="LTI not configured")
        if consumer_key != expected_key:
            logger.error(f"Consumer key mismatch: got '{consumer_key}', expected '{expected_key}'")
            raise HTTPException(status_code=401, detail="Invalid consumer key")

        # Validate OAuth signature
        base_url = manager.build_base_url(request)
        if not manager.validate_oauth_signature(post_data, "POST", base_url):
            raise HTTPException(status_code=401, detail="Invalid OAuth signature")

        # Extract key LTI parameters
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

        # Check if activity is already configured
        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)

        if activity and activity['status'] == 'active':
            public_base = manager.get_public_base_url(request)

            # ── CONFIGURED: Is this an instructor? → Dashboard ──
            if manager.is_instructor(roles):
                logger.info(f"Instructor accessing configured activity {resource_link_id} → dashboard")
                is_owner = (lms_email and lms_email == activity.get('owner_email'))
                dashboard_token = _create_token({
                    "type": "dashboard",
                    "resource_link_id": resource_link_id,
                    "lms_user_id": lms_user_id,
                    "lms_email": lms_email,
                    "username": username,
                    "display_name": display_name,
                    "is_owner": is_owner,
                }, ttl=DASHBOARD_TOKEN_TTL)
                return RedirectResponse(
                    url=f"{public_base}/lamb/v1/lti/dashboard?resource_link_id={resource_link_id}&token={dashboard_token}",
                    status_code=303
                )

            # ── CONFIGURED: Student flow ──
            # Check if consent is needed
            student_email = manager.generate_student_email(username, resource_link_id)
            if manager.check_student_consent(activity, student_email):
                logger.info(f"Student {student_email} needs consent for activity {resource_link_id}")
                consent_token = _create_token({
                    "type": "consent",
                    "resource_link_id": resource_link_id,
                    "username": username,
                    "display_name": display_name,
                    "lms_user_id": lms_user_id,
                    "student_email": student_email,
                }, ttl=CONSENT_TOKEN_TTL)
                return RedirectResponse(
                    url=f"{public_base}/lamb/v1/lti/consent?token={consent_token}",
                    status_code=303
                )

            # No consent needed — launch into OWI
            owi_token = manager.handle_student_launch(
                activity=activity,
                username=username,
                display_name=display_name,
                lms_user_id=lms_user_id
            )
            if not owi_token:
                raise HTTPException(status_code=500, detail="Failed to process launch")

            redirect_url = manager.get_owi_redirect_url(owi_token)
            logger.info(f"Redirecting student to OWI: {redirect_url}")
            return RedirectResponse(url=redirect_url, status_code=303)

        # ── NOT CONFIGURED ──
        if not manager.is_instructor(roles):
            # Student at unconfigured activity
            logger.info(f"Student arrived at unconfigured activity {resource_link_id}")
            return templates.TemplateResponse("lti_waiting.html", {
                "request": request,
                "context_title": context_title or "this course",
            })

        # ── INSTRUCTOR at unconfigured activity → Setup flow ──
        logger.info(f"Instructor setup flow for {resource_link_id}")

        # Identify instructor
        creator_users = manager.identify_instructor(
            lms_user_id=lms_user_id,
            lms_email=lms_email
        )

        if not creator_users:
            # Instructor has no associated Creator account → show contact-admin page
            logger.info(f"Instructor {lms_user_id} has no Creator account — showing contact-admin page")
            return templates.TemplateResponse("lti_contact_admin.html", {
                "request": request,
            })

        # Instructor identified — create setup token and redirect to setup page
        setup_token = _create_setup_token({
            "creator_users": [
                {"id": cu["id"], "organization_id": cu["organization_id"],
                 "user_email": cu["user_email"], "user_name": cu["user_name"]}
                for cu in creator_users
            ],
            "lms_user_id": lms_user_id,
            "lms_email": lms_email,
            "resource_link_id": resource_link_id,
            "context_id": context_id,
            "context_title": context_title,
        })

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
    Requires a valid setup token from the launch flow.
    """
    data = _validate_setup_token(token)
    if not data:
        return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link in your LMS again.</p>", status_code=403)

    creator_users = data["creator_users"]
    resource_link_id = data["resource_link_id"]

    # Get organizations the instructor belongs to
    orgs_with_assistants = manager.get_published_assistants_for_instructor(creator_users)

    # Get org names for display
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
        "context_title": data.get("context_title", ""),
        "needs_org_selection": needs_org_selection,
        "orgs_with_assistants": orgs_with_assistants,
        "org_names": org_names,
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
    Then launches the instructor into OWI as the first user.
    """
    try:
        form_data = await request.form()
        token = form_data.get("token", "")
        data = _validate_setup_token(token)
        if not data:
            return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link in your LMS again.</p>", status_code=403)

        organization_id = int(form_data.get("organization_id", 0))
        assistant_ids_str = form_data.getlist("assistant_ids")
        assistant_ids = [int(x) for x in assistant_ids_str if x]
        chat_visibility_enabled = form_data.get("chat_visibility_enabled") == "1"

        if not organization_id:
            return HTMLResponse("<h2>Error</h2><p>No organization selected.</p>", status_code=400)
        if not assistant_ids:
            return HTMLResponse("<h2>Error</h2><p>Please select at least one assistant.</p>", status_code=400)

        # Find the creator user for this org
        creator_users = data["creator_users"]
        creator_user = next((cu for cu in creator_users if cu["organization_id"] == organization_id), None)
        if not creator_user:
            return HTMLResponse("<h2>Error</h2><p>You don't have access to this organization.</p>", status_code=403)

        resource_link_id = data["resource_link_id"]
        context_id = data.get("context_id", "")
        context_title = data.get("context_title", "")

        # Configure the activity
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
        )

        if not activity:
            logger.error(f"Failed to configure activity {resource_link_id}")
            return HTMLResponse("<h2>Error</h2><p>Failed to configure activity. Please try again.</p>", status_code=500)

        logger.info(f"Activity {resource_link_id} configured with {len(assistant_ids)} assistants, chat_visibility={chat_visibility_enabled}")

        # Consume the setup token
        _consume_token(token)

        # Redirect instructor to the dashboard
        dashboard_token = _create_token({
            "type": "dashboard",
            "resource_link_id": resource_link_id,
            "lms_user_id": data.get("lms_user_id", ""),
            "lms_email": creator_user["user_email"],
            "username": data.get("lms_user_id", "instructor"),
            "display_name": creator_user.get("user_name", "Instructor"),
            "is_owner": True,
        }, ttl=DASHBOARD_TOKEN_TTL)

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
    data = _validate_setup_token(token)
    if not data:
        return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link in your LMS again.</p>", status_code=403)

    return templates.TemplateResponse("lti_link_account.html", {
        "request": request,
        "token": token,
        "error": "",
    })


@router.post("/link-account")
async def lti_link_account_submit(request: Request):
    """
    Process the account-linking form.
    Verifies credentials, creates the identity link, then redirects to setup.
    """
    try:
        form_data = await request.form()
        token = form_data.get("token", "")
        email = form_data.get("email", "").strip()
        password = form_data.get("password", "")

        data = _validate_setup_token(token)
        if not data:
            return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link again.</p>", status_code=403)

        if not email or not password:
            return templates.TemplateResponse("lti_link_account.html", {
                "request": request,
                "token": token,
                "error": "Please enter your email and password.",
            })

        # Verify credentials
        creator_user = manager.verify_creator_credentials(email, password)
        if not creator_user:
            return templates.TemplateResponse("lti_link_account.html", {
                "request": request,
                "token": token,
                "error": "Invalid credentials. Please check your LAMB Creator email and password.",
            })

        # Create identity link
        lms_user_id = data.get("lms_user_id", "")
        lms_email = data.get("lms_email", "")
        manager.link_identity(
            lms_user_id=lms_user_id,
            creator_user_id=creator_user["id"],
            lms_email=lms_email
        )

        logger.info(f"Linked LMS user {lms_user_id} to Creator user {creator_user['user_email']}")

        # Update setup token with the identified creator user
        data["creator_users"] = [{
            "id": creator_user["id"],
            "organization_id": creator_user["organization_id"],
            "user_email": creator_user["user_email"],
            "user_name": creator_user["user_name"],
        }]

        # Redirect to setup page with same token
        public_base = manager.get_public_base_url(request)
        return RedirectResponse(
            url=f"{public_base}/lamb/v1/lti/setup?token={token}",
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
        data = _validate_token(token)
        if not data:
            return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link again.</p>", status_code=403)

        resource_link_id = data.get("resource_link_id")
        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
        if not activity:
            return HTMLResponse("<h2>Error</h2><p>Activity not found.</p>", status_code=404)

        # Owner check
        if not data.get("is_owner"):
            return HTMLResponse("<h2>Access Denied</h2><p>Only the activity owner can reconfigure assistants.</p>", status_code=403)

        assistant_ids_str = form_data.getlist("assistant_ids")
        assistant_ids = [int(x) for x in assistant_ids_str if x]
        if not assistant_ids:
            return HTMLResponse("<h2>Error</h2><p>Please select at least one assistant.</p>", status_code=400)

        # Handle chat_visibility toggle
        chat_visibility_str = form_data.get("chat_visibility_enabled")
        if chat_visibility_str is not None:
            new_chat_vis = 1 if chat_visibility_str == "1" else 0
            if new_chat_vis != activity.get('chat_visibility_enabled', 0):
                db_manager.update_lti_activity(activity['id'], chat_visibility_enabled=new_chat_vis)

        success = manager.reconfigure_activity(activity, assistant_ids)
        if not success:
            return HTMLResponse("<h2>Error</h2><p>Failed to reconfigure.</p>", status_code=500)

        # Redirect back to dashboard
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
# Student Consent
# =============================================================================

@router.get("/consent")
async def lti_consent_page(request: Request, token: str = ""):
    """Show the student consent page for chat visibility."""
    data = _validate_token(token)
    if not data or data.get("type") != "consent":
        return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link in your LMS again.</p>", status_code=403)

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
        data = _validate_token(token)
        if not data or data.get("type") != "consent":
            return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link again.</p>", status_code=403)

        resource_link_id = data["resource_link_id"]
        student_email = data["student_email"]
        username = data["username"]
        display_name = data["display_name"]
        lms_user_id = data.get("lms_user_id")

        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
        if not activity:
            return HTMLResponse("<h2>Error</h2><p>Activity not found.</p>", status_code=404)

        # Record consent (need to ensure user record exists first)
        db_manager.create_lti_activity_user(
            activity_id=activity['id'],
            user_email=student_email,
            user_name=username,
            user_display_name=display_name,
            lms_user_id=lms_user_id
        )
        db_manager.record_student_consent(activity['id'], student_email)
        logger.info(f"Student {student_email} gave consent for activity {resource_link_id}")

        # Now launch into OWI
        owi_token = manager.handle_student_launch(
            activity=activity,
            username=username,
            display_name=display_name,
            lms_user_id=lms_user_id
        )

        _consume_token(token)

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
    data = _validate_token(token)
    if not data or data.get("type") != "dashboard":
        return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link in your LMS again.</p>", status_code=403)

    if data.get("resource_link_id") != resource_link_id:
        return HTMLResponse("<h2>Invalid request.</h2>", status_code=400)

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        return HTMLResponse("<h2>Activity not found.</h2>", status_code=404)

    is_owner = data.get("is_owner", False)

    # Get org name
    org = db_manager.get_organization_by_id(activity['organization_id'])
    org_name = org.get('name', 'Unknown') if org else 'Unknown'

    # Get dashboard data
    stats = manager.get_dashboard_stats(activity)
    students = manager.get_dashboard_students(activity['id'])

    # Get chats if chat_visibility enabled
    chats = {"chats": [], "total": 0}
    if activity.get('chat_visibility_enabled'):
        chats = manager.get_dashboard_chats(activity)

    # Format created date
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
    data = _validate_token(token)
    if not data or data.get("type") != "dashboard":
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
    data = _validate_token(token)
    if not data or data.get("type") != "dashboard":
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
    data = _validate_token(token)
    if not data or data.get("type") != "dashboard":
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
    data = _validate_token(token)
    if not data or data.get("type") != "dashboard":
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
    Creates/gets OWI user, adds to activity group, redirects.
    """
    data = _validate_token(token)
    if not data or data.get("type") != "dashboard":
        return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link again.</p>", status_code=403)

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        return HTMLResponse("<h2>Activity not found.</h2>", status_code=404)

    username = data.get("username", data.get("lms_user_id", "instructor"))
    display_name = data.get("display_name", "Instructor")
    lms_user_id = data.get("lms_user_id")

    owi_token = manager.handle_student_launch(
        activity=activity,
        username=username,
        display_name=display_name,
        lms_user_id=lms_user_id
    )

    if not owi_token:
        return HTMLResponse("<h2>Error</h2><p>Failed to access chat. Please try again.</p>", status_code=500)

    redirect_url = manager.get_owi_redirect_url(owi_token)
    return RedirectResponse(url=redirect_url, status_code=303)
