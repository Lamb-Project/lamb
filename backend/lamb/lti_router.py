"""
Unified LTI Router

Single LTI endpoint that supports:
- Instructor-configured activities with multiple assistants
- Student launch into configured activities
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

logger = get_logger(__name__, component="LTI_UNIFIED")

router = APIRouter()
manager = LtiActivityManager()
db_manager = LambDatabaseManager()

templates = Jinja2Templates(directory=[
    os.path.abspath("lamb/templates"),
])


# =============================================================================
# Setup tokens — short-lived tokens for the setup flow
# In-memory store (cleared on restart, which is fine for setup tokens)
# =============================================================================
_setup_tokens: dict = {}  # token -> {creator_users, lms_user_id, lms_email, resource_link_id, context_id, context_title, expires}
SETUP_TOKEN_TTL = 600  # 10 minutes


def _create_setup_token(data: dict) -> str:
    """Create a short-lived setup token."""
    token = secrets.token_urlsafe(32)
    _setup_tokens[token] = {**data, "expires": time.time() + SETUP_TOKEN_TTL}
    # Prune expired tokens occasionally
    now = time.time()
    expired = [k for k, v in _setup_tokens.items() if v["expires"] < now]
    for k in expired:
        del _setup_tokens[k]
    return token


def _validate_setup_token(token: str) -> dict | None:
    """Validate and consume a setup token. Returns data or None."""
    data = _setup_tokens.get(token)
    if not data:
        return None
    if time.time() > data["expires"]:
        del _setup_tokens[token]
        return None
    return data


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
            # ── CONFIGURED: Launch user into OWI ──
            token = manager.handle_student_launch(
                activity=activity,
                username=username,
                display_name=display_name,
                lms_user_id=lms_user_id
            )
            if not token:
                raise HTTPException(status_code=500, detail="Failed to process launch")

            redirect_url = manager.get_owi_redirect_url(token)
            logger.info(f"Redirecting user to OWI: {redirect_url}")
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
            # Cannot auto-identify → show link-account page
            setup_token = _create_setup_token({
                "creator_users": [],
                "lms_user_id": lms_user_id,
                "lms_email": lms_email,
                "resource_link_id": resource_link_id,
                "context_id": context_id,
                "context_title": context_title,
            })
            public_base = manager.get_public_base_url(request)
            return RedirectResponse(
                url=f"{public_base}/lamb/v1/lti/link-account?token={setup_token}",
                status_code=303
            )

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
        activity_name = form_data.get("activity_name", "").strip()
        assistant_ids_str = form_data.getlist("assistant_ids")
        assistant_ids = [int(x) for x in assistant_ids_str if x]

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
            activity_name=activity_name or context_title or f"Activity {resource_link_id[:8]}"
        )

        if not activity:
            logger.error(f"Failed to configure activity {resource_link_id}")
            return HTMLResponse("<h2>Error</h2><p>Failed to configure activity. Please try again.</p>", status_code=500)

        logger.info(f"Activity {resource_link_id} configured with {len(assistant_ids)} assistants")

        # Consume the setup token
        if token in _setup_tokens:
            del _setup_tokens[token]

        # Launch instructor into OWI as first user
        username = data.get("lms_user_id", "instructor")
        display_name = creator_user.get("user_name", "Instructor")

        owi_token = manager.handle_student_launch(
            activity=activity,
            username=username,
            display_name=display_name,
            lms_user_id=data.get("lms_user_id")
        )

        if owi_token:
            redirect_url = manager.get_owi_redirect_url(owi_token)
            return RedirectResponse(url=redirect_url, status_code=303)
        else:
            return HTMLResponse(
                "<h2>Activity configured!</h2>"
                "<p>Your activity is ready. Students can now access it from the LMS.</p>"
                "<p>You can close this tab and return to your LMS.</p>",
                status_code=200
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
    """Reconfigure an existing activity's assistant selection."""
    try:
        form_data = await request.form()
        token = form_data.get("token", "")
        data = _validate_setup_token(token)
        if not data:
            return HTMLResponse("<h2>Session expired.</h2><p>Please click the LTI link again.</p>", status_code=403)

        resource_link_id = data["resource_link_id"]
        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
        if not activity:
            return HTMLResponse("<h2>Error</h2><p>Activity not found.</p>", status_code=404)

        assistant_ids_str = form_data.getlist("assistant_ids")
        assistant_ids = [int(x) for x in assistant_ids_str if x]
        if not assistant_ids:
            return HTMLResponse("<h2>Error</h2><p>Please select at least one assistant.</p>", status_code=400)

        activity_name = form_data.get("activity_name", "").strip()
        if activity_name:
            db_manager.update_lti_activity(activity['id'], activity_name=activity_name)

        success = manager.reconfigure_activity(activity, assistant_ids)
        if not success:
            return HTMLResponse("<h2>Error</h2><p>Failed to reconfigure.</p>", status_code=500)

        # Consume token
        if token in _setup_tokens:
            del _setup_tokens[token]

        return HTMLResponse(
            "<h2>Activity updated!</h2>"
            "<p>Assistant selection has been updated. You can close this tab.</p>",
            status_code=200
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
