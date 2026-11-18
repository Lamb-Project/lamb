"""
Unified LTI Router

Single LTI endpoint that supports:
- Instructor-configured activities with multiple assistants
- Student launch into configured activities
- Instructor dashboard with usage stats, student log, and chat transcripts
- Identity linking for instructor identification

Session management:
- Instructor flows use LAMB JWTs (via lamb.auth) with lti_type claims
- Students launch directly into the activity module; a chat activity whose teachers can read
  transcripts shows a one-time notice first (modules/chat/notice.py)

Endpoint: POST /lamb/v1/lti/launch
"""

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from lamb import auth as lamb_auth, lti_access
from lamb.lti_activity_manager import LtiActivityManager
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger
from lamb.modules import get_all_modules, get_module
import os
import json
import time
from datetime import timedelta
from lamb.modules.base import LTIContext
from lamb.lti13 import is_scoped
from lamb.lti13.store import Store
from lamb.lti13.protocol import browser_response, validate_launch
from lamb.lti13.router import router as lti13_router
from lamb import lti_onboarding, activity_access

logger = get_logger(__name__, component="LTI_UNIFIED")

router = APIRouter()
router.include_router(lti13_router)
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
# LAMB JWT helpers for instructor sessions
# =============================================================================


def _create_dashboard_jwt(activity, instructor_user, lms_user_id: str,
                           lms_email: str = "", username: str = "", lms_instance: str = "",
                           launched_at: int = 0, creator_user_id: int = None) -> str:
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
        "lti_lms_instance": lms_instance,
        **({'activity_creator_id': creator_user_id} if creator_user_id is not None else {}),
        **({"lti_launched_at": int(launched_at)} if launched_at else {}),
    }, expires_delta=timedelta(hours=1) if creator_user_id is not None else LTI_DASHBOARD_JWT_EXPIRY)


def _create_setup_jwt(creator_users, lms_user_id: str, lms_email: str,
                       resource_link_id: str, context_id: str = "",
                       context_title: str = "", lms_instance: str = "",
                       username: str = "", display_name: str = "", launched_at: int = 0) -> str:
    """Issue a LAMB JWT for instructor setup flow."""
    return lamb_auth.create_token({
        "lti_type": "setup",
        "lti_resource_link_id": resource_link_id,
        "lti_context_id": context_id,
        "lti_context_title": context_title,
        "lti_lms_user_id": lms_user_id,
        "lti_lms_email": lms_email,
        "lti_lms_instance": lms_instance,
        "lti_username": username,
        "lti_display_name": display_name,
        **({"lti_launched_at": int(launched_at)} if launched_at else {}),
        "lti_creator_user_ids": [cu['id'] for cu in creator_users],
    }, expires_delta=LTI_SETUP_JWT_EXPIRY)


def _validate_lti_jwt(token: str, expected_type: str) -> dict | None:
    """Decode a LAMB JWT and verify it has the expected lti_type claim."""
    payload = lamb_auth.decode_token(token)
    if not payload:
        return None
    if payload.get("lti_type") != expected_type or not activity_access.valid_creator_token(db_manager, payload):
        return None
    return payload

# =============================================================================

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
    1. Validate LTI 1.1 OAuth or the bound LTI 1.3 OIDC transaction
    2. Is there a configured activity for this resource_link_id?
       YES + instructor -> module.on_instructor_launch() (dashboard)
       YES + student    -> module.on_student_launch() (direct launch)
       NO  + instructor -> identify as Creator user -> setup (LAMB JWT)
       NO  + student    -> "not configured yet" page
    """
    try:
        form_data = await request.form()
        post_data = dict(form_data)

        if any(len(form_data.getlist(key)) != 1 for key in form_data):
            raise HTTPException(400, "Duplicate launch parameter")
        is_lti13 = any(key in post_data for key in ("id_token", "state", "browser_proof"))
        if is_lti13:
            if any(key.startswith("oauth_") for key in post_data):
                raise HTTPException(400, "Mixed LTI launch protocols")
            try:
                if "browser_proof" not in post_data:
                    return browser_response(post_data.get("id_token"), post_data.get("state"))
                verified = await run_in_threadpool(validate_launch, post_data)
                ctx = LTIContext(**verified)
            except ValueError as exc:
                raise HTTPException(401, str(exc)) from exc
            resource_link_id, lms_user_id = ctx.resource_link_id, ctx.lms_user_id
            lms_email, username, display_name = ctx.lms_email, ctx.username, ctx.display_name
            roles, context_id, context_title = ctx.roles, ctx.context_id, ctx.context_title
            lis_result_sourcedid, lis_outcome_service_url = None, ""
            lms_instance = ""  # the scoped identity already names the registration and deployment
            Store().save_grade_target(resource_link_id, lms_user_id,
                manager.generate_student_email(username, resource_link_id), verified['grade_endpoint'])
        else:
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
            _raw_sourced = (post_data.get("lis_result_sourcedid") or "").strip()
            lis_result_sourcedid = _raw_sourced or None

            if any(is_scoped(v) for v in (resource_link_id, lms_user_id, context_id, username)):
                raise HTTPException(400, "Reserved LTI identifier")
            # Stored as the LMS sends it. Compared only where an administrator enabled a check.
            lms_instance = lti_access.instance_id(post_data)
            try:
                lti_access.require_global(db_manager, lms_instance)
            except ValueError as exc:
                raise HTTPException(403, str(exc)) from exc
            ctx = LTIContext(
                resource_link_id=resource_link_id, lms_user_id=lms_user_id, lms_email=lms_email,
                username=username, display_name=display_name, roles=roles,
                is_instructor=manager.is_instructor(roles), context_id=context_id,
                context_title=context_title, lis_result_sourcedid=lis_result_sourcedid,
                lms_instance=lms_instance)

        logger.info(f"LTI launch: resource_link={resource_link_id}, user={username}, roles={roles}")
        launched_at = int(time.time())   # the four hours of moving between the activity and Creator start now
        ctx.launched_at = launched_at

        activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)

        if activity:
            try:
                if is_lti13:
                    Store().assert_org(resource_link_id, activity['organization_id'])
                else:
                    lti_access.require_organization(db_manager, db_manager.get_organization_by_id(activity['organization_id']), lms_instance)
            except ValueError as exc:
                raise HTTPException(403, str(exc)) from exc

        if activity:
            activity_access.record_launch(db_manager, activity, {
                "lti_lms_user_id": lms_user_id, "lti_lms_instance": lms_instance,
                "lti_context_id": context_id, "lti_context_title": context_title,
            }, instructor=ctx.is_instructor)

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

            module = _get_activity_module(activity)
            # The hooks call Open WebUI over HTTP (the chat module requests a
            # sign-in token). Open WebUI calls LAMB back on every chat turn from
            # its single event loop, so a hook running on LAMB's event loop can
            # leave each service waiting for the other. Worker thread instead.
            if ctx.is_instructor:
                return await run_in_threadpool(module.on_instructor_launch, ctx)
            return await run_in_threadpool(module.on_student_launch, ctx)

        # -- NOT CONFIGURED --
        if not ctx.is_instructor:
            logger.info(f"Student arrived at unconfigured activity {resource_link_id}")
            return templates.TemplateResponse("lti_waiting.html", {
                "request": request,
                "context_title": context_title or "this course",
            })

        # -- INSTRUCTOR at unconfigured activity -> Setup flow --
        logger.info(f"Instructor setup flow for {resource_link_id}")
        # Who the instructor is: the LMS user (and instance), never the email (15 November 2026).
        creator_users = manager.identify_instructor(lms_user_id=lms_user_id, lms_instance=lms_instance)

        if not creator_users:
            # No LAMB account for this instructor (#467, #562): the launch itself returns the
            # creator-code page, with a ticket that carries what the LMS just asserted.
            logger.info(f"Instructor {lms_user_id} has no Creator account - showing the creator-code page")
            ticket = lti_onboarding.issue_ticket(
                lms_user_id=lms_user_id, lms_email=lms_email, display_name=display_name,
                resource_link_id=resource_link_id, context_id=context_id, context_title=context_title,
                protocol="1.3" if is_lti13 else "1.1", lms_instance=lms_instance,
                username=username, launched_at=launched_at)
            return await run_in_threadpool(_onboarding_page, request, ticket)

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
            lms_instance=lms_instance,
            username=username, display_name=display_name, launched_at=launched_at,
        )

        public_base = manager.get_public_base_url(request)
        redirect_url = f"{public_base}/m/chat/setup?token={setup_token}"
        
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

    existing = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if existing:
        activity_access.require_owner(db_manager, existing, data)
    creator_users = _creator_users_for(data)

    if not creator_users:
        return JSONResponse({"detail": "Could not identify your Creator account."}, status_code=403)

    if existing:
        creator_users = [c for c in creator_users if c['organization_id'] == existing['organization_id']]
    orgs_with_assistants = manager.get_published_assistants_for_instructor(creator_users)
    # Every organization where the instructor is a creator is offered, also one with nothing
    # published yet: the page names it, says what is missing and leads to LAMB Creator (#562).
    for cu in creator_users:
        orgs_with_assistants.setdefault(cu['organization_id'], [])
    # The kinds of activity this teacher can create, organization by organization: the list
    # follows the organization's settings and the creator user in it (Marc, 15 November 2026).
    # A kind that cannot be created is not offered at all.
    org_modules = {
        org_id: [m.name for m in get_all_modules()
                 if m.unavailable_reason(org_id, assistants, _teacher_email(data, creator_users, org_id)) is None]
        for org_id, assistants in orgs_with_assistants.items()
    }
    if existing:
        org_modules = {existing['organization_id']: [existing.get('activity_type') or 'chat']}
    offered = {name for names in org_modules.values() for name in names}
    offered_modules = [m for m in get_all_modules() if m.name in offered]

    org_names, org_slugs = {}, {}
    for org_id in orgs_with_assistants:
        org = db_manager.get_organization_by_id(org_id)
        if org:
            org_names[org_id] = org.get('name', f'Organization {org_id}')
            org_slugs[org_id] = org.get('slug', '')
    # Two organizations with the same name cannot be told apart in the chooser: add the slug.
    name_counts = {n: list(org_names.values()).count(n) for n in org_names.values()}
    for org_id, name in list(org_names.items()):
        if org_slugs.get(org_id) and name_counts[name] > 1:
            org_names[org_id] = f"{name} ({org_slugs[org_id]})"

    needs_org_selection = len(orgs_with_assistants) > 1

    def _field_to_json(f):
        row = {"name": f.name, "label": f.label, "type": f.field_type, "required": f.required}
        if f.field_type in ("select", "radio") and getattr(f, "options", None):
            row["options"] = [{"value": o["value"], "label": o["label"]} for o in f.options]
        return row

    return JSONResponse({
        "existing_activity": ({**activity_access.context(db_manager, existing),
            'organization_id': existing['organization_id'], 'activity_type': existing.get('activity_type') or 'chat',
            'assistant_ids': [a['id'] for a in db_manager.get_activity_assistants(existing['id'])],
            'setup_config': json.loads(existing.get('setup_config') or '{}'),
            'chat_visibility_enabled': bool(existing.get('chat_visibility_enabled'))} if existing else None),
        "resource_link_id": resource_link_id,
        "context_title": data.get("lti_context_title", ""),
        "creator_session": data.get("activity_creator_id") is not None,
        "needs_org_selection": needs_org_selection,
        "creator_access": [] if data.get("activity_creator_id") else lti_onboarding.creator_access(db_manager, manager, data),
        "can_add_organization": data.get("lti_type") == "setup" and lti_onboarding.within_session(data),
        "org_names": org_names,
        "orgs_with_assistants": orgs_with_assistants,
        "org_modules": org_modules,
        "modules": [{"name": m.name, "display_name": getattr(m, 'display_name', m.name),
                     "description": getattr(m, 'description', ''),
                     "requires_assistants": getattr(m, 'requires_assistants', True)} for m in offered_modules],
        "modules_fields": {
            m.name: [_field_to_json(f) for f in m.get_setup_fields()]
            for m in offered_modules
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
        data = _validate_lti_jwt(token, "setup") or _validate_lti_jwt(token, "dashboard")
        if not data:
            return JSONResponse({"detail": "Session expired"}, status_code=403)

        organization_id = int(payload.get("organization_id", 0))
        if is_scoped(data.get("lti_resource_link_id")):
            try:
                Store().assert_org(data["lti_resource_link_id"], organization_id)
            except ValueError as exc:
                raise HTTPException(403, str(exc)) from exc
        assistant_ids_raw = payload.get("assistant_ids", [])
        assistant_ids = [int(x) for x in assistant_ids_raw if x]
        activity_type = payload.get("activity_type", "chat")
        chat_visibility_enabled = bool(payload.get("chat_visibility_enabled"))

        if not organization_id:
            return JSONResponse({"detail": "No organization selected"}, status_code=400)
        requested_module = get_module(activity_type)
        if not requested_module or not requested_module.enabled_for_org(organization_id):
            return JSONResponse({"detail": f"Activity type '{activity_type}' is not available"}, status_code=400)
        if not assistant_ids and getattr(requested_module, 'requires_assistants', True):
            return JSONResponse({"detail": "Please select at least one assistant"}, status_code=400)

        # File-evaluation specific validation
        if activity_type == "file_evaluation":
            fe_title = (payload.get("title") or "").strip()
            if not fe_title:
                return JSONResponse({"detail": "Activity title is required"}, status_code=400)
            fe_deadline = (payload.get("deadline") or "").strip()
            if not fe_deadline:
                return JSONResponse({"detail": "Deadline is required"}, status_code=400)
            fe_sub_type = payload.get("submission_type", "individual")
            if fe_sub_type == "group":
                try:
                    fe_group_size = int(payload.get("max_group_size", 0))
                except (TypeError, ValueError):
                    fe_group_size = 0
                if not (2 <= fe_group_size <= 20):
                    return JSONResponse(
                        {"detail": "Max group size must be between 2 and 20"},
                        status_code=400,
                    )

        # File-evaluation: every selected assistant must have a rubric configured
        if activity_type == "file_evaluation":
            for aid in assistant_ids:
                assistant = db_manager.get_assistant_by_id(aid)
                if not assistant:
                    return JSONResponse(
                        {"detail": f"Assistant {aid} not found"},
                        status_code=400,
                    )
                if not db_manager.assistant_has_rubric_for_eval(assistant.api_callback):
                    return JSONResponse(
                        {"detail": f"Assistant '{assistant.name}' does not have a rubric configured for evaluation"},
                        status_code=400,
                    )

        # The instructor's account in that organization, identified again from the launch the
        # token stands for (never trust form data for identity).
        creator_user = next((cu for cu in _creator_users_for(data) if cu["organization_id"] == organization_id), None)

        if not creator_user:
            return JSONResponse({"detail": "You don't have access to this organization"}, status_code=403)

        allowed = db_manager.get_published_assistants_for_org_user(
            organization_id, creator_user["id"], creator_user["user_email"]
        )
        allowed_ids = {a["id"] for a in allowed}
        invalid = [aid for aid in assistant_ids if aid not in allowed_ids]
        if invalid:
            return JSONResponse(
                {"detail": f"Assistants not available in this organization: {invalid}"},
                status_code=400,
            )

        resource_link_id = data.get("lti_resource_link_id")
        context_id = data.get("lti_context_id", "")
        context_title = data.get("lti_context_title", "")

        # Use instructor-provided title when available (file_evaluation),
        # falling back to LMS course title or resource_link_id.
        instructor_title = (payload.get("title") or "").strip()
        resolved_activity_name = instructor_title or context_title or resource_link_id

        # Check if activity already exists (reconfiguration case)
        existing_activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)

        # The page offers only the kinds this teacher can create in this organization; the
        # server holds the same line for a new activity, whatever the page sent.
        if not existing_activity and requested_module.unavailable_reason(
                organization_id, allowed, _teacher_email(data, [creator_user], organization_id)):
            return JSONResponse(
                {"detail": f"Activity type '{activity_type}' is not available to you in this organization"},
                status_code=400)

        reserved = {"token", "organization_id", "assistant_ids", "activity_type",
                    "chat_visibility_enabled", "resource_link_id", "configured_by_email",
                    "lms_email", "activity_name"}
        extras = {k: v for k, v in payload.items() if k not in reserved}

        if existing_activity:
            activity_access.require_owner(db_manager, existing_activity, data)
            if existing_activity['organization_id'] != organization_id or existing_activity.get('activity_type', 'chat') != activity_type:
                raise HTTPException(400, 'The activity organization and type cannot be changed')
            if bool(existing_activity.get('chat_visibility_enabled')) != chat_visibility_enabled:
                raise HTTPException(400, 'Chat visibility is fixed when the activity is created')
        if activity_type == 'file_evaluation':
            evaluator_id = payload.get('evaluator_id') or assistant_ids[0]
            activity_access.validate_assistants(db_manager, {'organization_id': organization_id}, creator_user,
                                               [evaluator_id], evaluator=True)

        if existing_activity:
            activity_access.record_launch(db_manager, existing_activity, data)
            # Reconfigure existing activity
            logger.info(f"Activity {resource_link_id} already exists, reconfiguring")
            added_ids, removed_ids = manager.reconfigure_activity(existing_activity, assistant_ids)
            activity = existing_activity
            module = _get_activity_module(activity)
            module.on_activity_reconfigured(activity, added_ids, removed_ids)
        else:
            # Phase 1: create DB record (owi fields empty at this point)
            activity = manager.configure_activity(
                resource_link_id=resource_link_id,
                organization_id=organization_id,
                assistant_ids=assistant_ids,
                configured_by_email=creator_user["user_email"],
                configured_by_name=creator_user.get("user_name"),
                context_id=context_id,
                context_title=context_title,
                activity_name=resolved_activity_name,
                chat_visibility_enabled=chat_visibility_enabled,
                activity_type=activity_type,
            )

            if not activity:
                logger.error(f"Failed to configure activity {resource_link_id}")
                return JSONResponse({"detail": "Failed to configure activity"}, status_code=500)

            module = _get_activity_module(activity)

        setup_data = {
            "resource_link_id": resource_link_id,
            "assistant_ids": assistant_ids,
            "configured_by_email": creator_user["user_email"],
            "lms_email": data.get("lti_lms_email", ""),   # lamb-0.8: the teacher's real email, for allowances
            "activity_name": resolved_activity_name,
            "chat_visibility_enabled": chat_visibility_enabled,
            **extras,
        }
        try:
            if not existing_activity:
                activity_access.record_launch(db_manager, activity, data)
            # Reconfiguring a chat must retain its group and enrolled students.
            if not existing_activity or activity_type != 'chat':
                module.on_activity_configured(activity['id'], setup_data)
        except Exception:
            if not existing_activity:
                # lamb-0.8: do not leave a half-configured link behind; the instructor can retry
                db_manager.delete_lti_activity(activity['id'])
            raise

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
            activity, instructor_user, lms_user_id, lms_email, username=username,
            lms_instance=data.get("lti_lms_instance", ""), launched_at=lti_onboarding.launched_at(data) or 0,
            creator_user_id=data.get('activity_creator_id'))

        public_base = manager.get_public_base_url(request)
        at = activity.get("activity_type") or "chat"
        if at == 'llm_access' and data.get('activity_creator_id') is not None:
            from lamb.token_dealer import lti as td_pages, wiring as td_wiring
            td = td_wiring.store().get_activity_by_resource_link(resource_link_id)
            td_token = td_pages.make_token({**data, 'type': 'manage', 'activity_id': td['id']})
            return JSONResponse({'status': 'success', 'redirect_url': f'{public_base}{td_pages.PREFIX}/manage?token={td_token}'})
        module_redirect = module.configured_redirect(public_base, activity, lms_user_id, lms_email,
            lms_instance=data.get('lti_lms_instance', ''))
        if module_redirect:
            return JSONResponse({"status": "success", "redirect_url": module_redirect})
        if at == "file_evaluation":
            fe_lang = str(payload.get("language", "en")).lower()
            if fe_lang not in ("en", "es", "ca", "eu"):
                fe_lang = "en"
            redirect_url = (
                f"{public_base}/m/file-eval/grading?activity_id={activity['id']}"
                f"&lang={fe_lang}&token={dashboard_token}"
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
# Creator codes, LAMB Creator and the way back to the activity (#467 / #562)
# =============================================================================

def _setup_jwt_from(claims: dict, creator_users) -> str:
    """A setup token for the same launch as `claims` (a ticket, a setup token or a return token)."""
    return _create_setup_jwt(
        creator_users=creator_users, lms_user_id=claims["lti_lms_user_id"], lms_email=claims.get("lti_lms_email", ""),
        resource_link_id=claims["lti_resource_link_id"], context_id=claims.get("lti_context_id", ""),
        context_title=claims.get("lti_context_title", ""), lms_instance=claims.get("lti_lms_instance", ""),
        username=claims.get("lti_username", ""), display_name=claims.get("lti_display_name", ""),
        launched_at=lti_onboarding.launched_at(claims) or 0)


def _teacher_email(claims: dict, creator_users, organization_id: int) -> str:
    """The email that identifies the teacher to a module: the one the LMS sends (allowances follow
    it), else the email of the teacher's account in that organization."""
    lms_email = (claims.get("lti_lms_email") or "").strip().lower()
    if lms_email:
        return lms_email
    return next((cu.get("user_email") or "" for cu in creator_users if cu.get("organization_id") == organization_id), "")


def _creator_users_for(claims: dict):
    """The instructor's LTI creator accounts, identified from the LMS user and instance a launch
    token carries (a ticket, a setup, dashboard or return token). Read again each time: an
    organization just added is there, a disabled account is not."""
    if 'activity_creator_id' in claims:
        return activity_access.creators_for_payload(db_manager, claims)
    try:
        found = manager.identify_instructor(lms_user_id=claims.get("lti_lms_user_id") or "",
                                            lms_instance=claims.get("lti_lms_instance") or "")
    except ValueError:
        found = []
    return [{"id": cu["id"], "organization_id": cu["organization_id"],
             "user_email": cu["user_email"], "user_name": cu["user_name"]} for cu in found]


def _creator_url(request: Request, claims: dict, creator_user_id: int):
    """Address of LAMB Creator for one of the instructor's LTI creator accounts, with the way back
    to the activity; None when that account may not be entered from this launch."""
    session = lti_onboarding.creator_session(db_manager, manager, claims, creator_user_id)
    if not session:
        return None
    return f"{manager.get_public_base_url(request)}/assistants?token={session}&activity={lti_onboarding.issue_return(claims)}"


def _onboarding_page(request: Request, ticket_token: str, reason: str = "", organization=None, status_code: int = 200):
    """Render the page a verified instructor launch returns when LAMB has no account for the instructor,
    and the same page when an instructor adds an organization."""
    ticket = lti_onboarding.read_ticket(ticket_token)
    if not ticket:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)
    try:
        allowed = lti_onboarding.allowed_organizations(db_manager, ticket)
        accounts = _creator_users_for(ticket)
    except ValueError:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)
    back_url = ""
    if accounts:
        # Already a creator somewhere: this is "add an organization", with the way back to the choice.
        back_url = f"/m/chat/setup?token={_setup_jwt_from(ticket, accounts)}"
    organization_text = ""
    if reason in lti_onboarding.SHOW_ORGANIZATION_TEXT and organization:
        organization_text = lti_onboarding.own_page_text(organization)
    return templates.TemplateResponse("lti_onboarding.html", {
        "request": request,
        "ticket": ticket_token,
        "page_text": lti_onboarding.page_text(db_manager, allowed or ()),
        "error": lti_onboarding.MESSAGES.get(reason, "") if reason else "",
        "organization_text": organization_text,
        "can_retry": reason != "rate_limited",
        "back_url": back_url,
        "context_title": ticket.get("lti_context_title") or "",
    }, status_code=status_code)


@router.get("/onboarding")
async def lti_onboarding_add_organization(request: Request, token: str = ""):
    """An instructor who is already a creator adds an organization with a creator code.
    Reached from the activity setup with its own token, within four hours of the launch."""
    data = _validate_lti_jwt(token, "setup")
    if not data or not lti_onboarding.within_session(data):
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)
    lms_user_id = data.get("lti_lms_user_id", "")
    ticket = lti_onboarding.issue_ticket(
        lms_user_id=lms_user_id, lms_email=data.get("lti_lms_email", ""), display_name=data.get("lti_display_name", ""),
        resource_link_id=data.get("lti_resource_link_id", ""), context_id=data.get("lti_context_id", ""),
        context_title=data.get("lti_context_title", ""), protocol="1.3" if is_scoped(lms_user_id) else "1.1",
        lms_instance=data.get("lti_lms_instance", ""), username=data.get("lti_username", ""),
        launched_at=lti_onboarding.launched_at(data))
    return await run_in_threadpool(_onboarding_page, request, ticket)


@router.post("/onboarding")
async def lti_onboarding_redeem(request: Request):
    """Redeem a creator code. Reachable only with the ticket of a verified instructor launch.

    A person with no account before the code goes on to LAMB Creator: there is nothing to set
    an activity up with yet. A creator adding an organization goes back to the choice of
    organization, with the new one chosen.
    """
    form_data = await request.form()
    ticket_token = str(form_data.get("ticket", ""))
    ticket = lti_onboarding.read_ticket(ticket_token)
    if not ticket:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)
    result = await run_in_threadpool(lti_onboarding.redeem, db_manager, manager, ticket, str(form_data.get("code", "")))
    if not result.ok:
        return await run_in_threadpool(
            _onboarding_page, request, ticket_token, result.reason, result.organization,
            429 if result.reason == "rate_limited" else 400)
    creator = result.creator_user
    if result.first_account:
        url = await run_in_threadpool(_creator_url, request, ticket, creator["id"])
        if url:
            return RedirectResponse(url=url, status_code=303)
    accounts = await run_in_threadpool(_creator_users_for, ticket)
    setup_token = _setup_jwt_from(ticket, accounts or [creator])
    return RedirectResponse(
        url=f"{manager.get_public_base_url(request)}/m/chat/setup?token={setup_token}&org={creator['organization_id']}",
        status_code=303)


@router.post("/creator-session")
async def lti_creator_session(request: Request):
    """Address of LAMB Creator for one of the instructor's LTI creator accounts.

    LTI creators have no password and reach Creator only through the LMS. The setup or
    dashboard token of a launch made in the last four hours may ask for it; the address
    carries the way back to the activity. Regular creators sign in on the login page.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    token = str(body.get("token", ""))
    data = _validate_lti_jwt(token, "setup") or _validate_lti_jwt(token, "dashboard")
    try:
        creator_user_id = int(body.get("creator_user_id"))
    except (TypeError, ValueError):
        creator_user_id = None
    url = None
    if data and creator_user_id is not None:
        url = await run_in_threadpool(_creator_url, request, data, creator_user_id)
    if not url:
        return JSONResponse({"detail": "Open the activity from your LMS again to enter LAMB Creator."}, status_code=403)
    return JSONResponse({"url": url})


@router.get("/return")
async def lti_return_to_activity(request: Request, token: str = ""):
    """Back from LAMB Creator to the activity the person came from, within four hours of the launch:
    its dashboard when it is set up, else the choice of organization and the setup."""
    data = lti_onboarding.read_return(token)
    if not data:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)
    lms_user_id = data["lti_lms_user_id"]
    try:
        activity = db_manager.get_lti_activity_by_resource_link(data["lti_resource_link_id"])
        if activity and activity['status'] == 'active':
            ctx = LTIContext(
                resource_link_id=data["lti_resource_link_id"], lms_user_id=lms_user_id, lms_email=data.get("lti_lms_email", ""),
                username=data.get("lti_username") or lms_user_id, display_name=data.get("lti_display_name") or "Instructor",
                roles="Instructor", is_instructor=True, context_id=data.get("lti_context_id", ""),
                context_title=data.get("lti_context_title", ""), lms_instance=data.get("lti_lms_instance", ""),
                launched_at=lti_onboarding.launched_at(data) or 0,
                lti_version="1.3" if is_scoped(lms_user_id) else "1.1",
                registration_id=data.get("lti13_registration_id"), deployment_id=data.get("lti13_deployment_id"))
            return await run_in_threadpool(_get_activity_module(activity).on_instructor_launch, ctx)
        accounts = await run_in_threadpool(_creator_users_for, data)
    except ValueError:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)
    if not accounts:
        return HTMLResponse(SESSION_EXPIRED_HTML, status_code=403)
    return RedirectResponse(
        url=f"{manager.get_public_base_url(request)}/m/chat/setup?token={_setup_jwt_from(data, accounts)}", status_code=303)


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

        creator = activity_access.require_owner(db_manager, activity, data)

        assistant_ids_str = form_data.getlist("assistant_ids")
        assistant_ids = [int(x) for x in assistant_ids_str if x]
        if not assistant_ids:
            return HTMLResponse("<h2>Error</h2><p>Please select at least one assistant.</p>", status_code=400)

        activity_access.validate_assistants(db_manager, activity, creator, assistant_ids,
                                           evaluator=activity.get('activity_type') == 'file_evaluation')

        # Chat transcript visibility is fixed at initial configuration time.
        chat_visibility_str = form_data.get("chat_visibility_enabled")
        if chat_visibility_str is not None:
            new_chat_vis = 1 if chat_visibility_str == "1" else 0
            if new_chat_vis != activity.get('chat_visibility_enabled', 0):
                return HTMLResponse(
                    "<h2>Invalid request</h2><p>Chat transcript visibility can only be set when the activity is first configured.</p>",
                    status_code=400
                )

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

    except HTTPException:
        raise
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

    is_owner = bool(activity_access.owner_for_payload(db_manager, activity, data))

    org = db_manager.get_organization_by_id(activity['organization_id'])
    org_name = org.get('name', 'Unknown') if org else 'Unknown'

    return JSONResponse({
        **activity_access.context(db_manager, activity),
        "activity_name": activity.get('activity_name', 'LTI Activity'),
        "context_title": activity.get('context_title', ''),
        "org_name": org_name,
        "owner_name": activity.get('owner_name') or activity.get('owner_email'),
        "created_at": activity.get('created_at'),
        "chat_visibility_enabled": bool(activity.get('chat_visibility_enabled')),
        "is_owner": is_owner,
        "creator_access": [] if data.get("activity_creator_id") else lti_onboarding.creator_access(db_manager, manager, data),
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

    if data.get("lti_resource_link_id") != resource_link_id:
        raise HTTPException(status_code=403, detail="Resource link does not match token")

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    module = _get_activity_module(activity)
    return JSONResponse(module.get_dashboard_stats(activity))


@router.get("/dashboard/students")
async def lti_dashboard_students(resource_link_id: str = "", token: str = "",
                                  page: int = 1, per_page: int = 20):
    """Return student list as JSON."""
    data = _validate_lti_jwt(token, "dashboard")
    if not data:
        raise HTTPException(status_code=403, detail="Invalid token")

    if data.get("lti_resource_link_id") != resource_link_id:
        raise HTTPException(status_code=403, detail="Resource link does not match token")

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    return JSONResponse(manager.get_dashboard_students(activity['id'], page, per_page))


@router.get("/dashboard/chats")
async def lti_dashboard_chats(resource_link_id: str = "", token: str = "",
                               assistant_id: int = None,
                               page: int = 1, per_page: int = 20):
    """Return chat list as JSON. Requires chat_visibility enabled."""
    data = _validate_lti_jwt(token, "dashboard")
    if not data:
        raise HTTPException(status_code=403, detail="Invalid token")

    if data.get("lti_resource_link_id") != resource_link_id:
        raise HTTPException(status_code=403, detail="Resource link does not match token")

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

    if data.get("lti_resource_link_id") != resource_link_id:
        raise HTTPException(status_code=403, detail="Resource link does not match token")

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

    if data.get("lti_resource_link_id") != resource_link_id:
        return HTMLResponse("<h2>Invalid request.</h2>", status_code=403)

    activity = db_manager.get_lti_activity_by_resource_link(resource_link_id)
    if not activity:
        return HTMLResponse("<h2>Activity not found.</h2>", status_code=404)

    display_name = data.get("lti_display_name", "Instructor")
    lms_user_id = data.get("lti_lms_user_id", "")
    username = data.get("lti_username", lms_user_id)

    module = _get_activity_module(activity)
    redirect_url = await run_in_threadpool(
        module.launch_user,
        activity=activity,
        username=username,
        display_name=display_name,
        lms_user_id=lms_user_id,
        is_instructor=True,
    )

    if not redirect_url:
        return HTMLResponse("<h2>Error</h2><p>Failed to access chat. Please try again.</p>", status_code=500)

    return RedirectResponse(url=redirect_url, status_code=303)
