"""Workshop routers — restricted creator routes for students building assistants.

Students get a virtual principal scoped to their activity. They can create an
assistant and submit their work — but CANNOT publish, share, access other
tenants' data, or touch other students' work.

Document/KB attachment (content ingestion) is wired in a later phase; those
routes validate scope + quota and return an accepted reference.

- GET /sessions/{session_id}          — restore build progress after reload
- POST /sessions/{session_id}/assistant/{assistant_id}/chat — streamed chat
  with observability + tool_event SSE frames (same SSE dialect the rest of
  LAMB emits).
"""

import json
import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Header, Form, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from lamb.completions.tools.definitions import WORKSHOP_TOOLS
from lamb.database_manager import LambDatabaseManager
from lamb.lamb_classes import Assistant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workshop", tags=["workshop"])

_db_manager = LambDatabaseManager()

# Jinja templates owned by this module (consent page).
_templates = Jinja2Templates(directory=[
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
])

# Workshop per-session quotas (Lean MVP)
MAX_DOCUMENTS_PER_SESSION = 1
MAX_KBS_PER_SESSION = 1


def _verify_workshop_principal(session_id: str, token: str) -> Dict[str, Any]:
    """Validate a workshop token and that the session belongs to the principal.

    Returns the principal dict, or raises 401/403. Authorization boundary for
    every workshop route.
    """
    from lamb import auth as lamb_auth

    data = lamb_auth.decode_token(token)
    if not data or data.get("scope") != "workshop_student":
        raise HTTPException(status_code=401, detail="Invalid workshop token")

    if data.get("session_id") != session_id:
        raise HTTPException(status_code=403, detail="Session mismatch")

    return data


def _verify_assistant_ownership(assistant_id: int, principal: Dict[str, Any]) -> None:
    """Ensure the assistant belongs to this student's activity/org scope."""
    assistant = _db_manager.get_assistant_by_id(assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    if assistant.owner != principal.get("email"):
        raise HTTPException(status_code=403, detail="Not your assistant")
    if assistant.organization_id != principal.get("organization_id"):
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")


def _resolve_tool_definitions(tools: Any) -> Any:
    """Complete name-only tool definitions against the canonical schema.
    
    Definitions that already carry a schema are passed through untouched;
    unknown tool names are dropped.
    """
    if not tools:
        return None

    resolved = []
    for tool in tools:
        fn = (tool or {}).get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        # Already fully specified — keep it as-is.
        if fn.get("parameters"):
            resolved.append(tool)
            continue
        canonical = WORKSHOP_TOOLS.get(name)
        if canonical:
            resolved.append(canonical)
    return resolved or None


@router.get("/sessions/{session_id}")
async def get_workshop_session(session_id: str, token: str = Header(...)):
    """Return the workshop session record so the frontend can restore progress.

    build_state is persisted per step; a page reload re-hydrates the
    5-step wizard from this payload instead of losing the student's work.
    """
    _verify_workshop_principal(session_id, token)

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # build_state is stored as JSON text; hand back a parsed object.
    try:
        build_state = json.loads(session.get("build_state") or "{}")
    except (json.JSONDecodeError, TypeError):
        build_state = {}

    return {
        "session_id": session.get("id"),
        "activity_id": session.get("activity_id"),
        "assistant_id": session.get("assistant_id"),
        "status": session.get("status"),
        "saved_chat": session.get("saved_chat"),
        "reflection": session.get("reflection"),
        "build_state": build_state,
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }


@router.post("/sessions/{session_id}/assistant")
async def create_workshop_assistant(
    session_id: str,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Student creates an assistant in their workspace. Restricted scope."""
    principal = _verify_workshop_principal(session_id, token)

    # Enforce per-session quota (Lean MVP: single assistant)
    existing = _db_manager.get_workshop_session_by_id(session_id)
    if existing and existing.get("assistant_id"):
        raise HTTPException(status_code=429, detail="Assistant already created")

    owner_email = principal.get("email")
    if not owner_email:
        raise HTTPException(status_code=403, detail="Missing principal email")

    assistant = Assistant(
        name=body.get("name", "My AI Assistant"),
        description=body.get("description", ""),
        owner=owner_email,
        api_callback=body.get("api_callback", "{}"),
        system_prompt=body.get("system_prompt", ""),
        prompt_template=body.get("prompt_template", ""),
        organization_id=principal.get("organization_id"),
        # Deprecated fields — always empty strings, kept for DB compatibility
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=body.get("rag_top_k", 3),
        RAG_collections=body.get("rag_collections", "[]"),
    )
    assistant_id = _db_manager.add_assistant(assistant)
    if not assistant_id:
        # UNIQUE(org, name, owner) collision: an assistant with the same name
        # already exists for this student (e.g. re-create after a timeout, or
        # parallel tabs). Be idempotent — reuse the existing assistant instead
        # of returning a 500. (#workshop-P4)
        existing = _db_manager.find_assistant_by_owner_name_org(
            owner=owner_email,
            name=assistant.name,
            org_id=principal.get("organization_id"),
        )
        if existing:
            assistant_id = existing.get("id")
        if not assistant_id:
            raise HTTPException(status_code=500, detail="Failed to create assistant")

    _db_manager.update_workshop_session_assistant(session_id, assistant_id)

    return {"success": True, "assistant_id": assistant_id}


@router.patch("/sessions/{session_id}/assistant/{assistant_id}")
async def update_workshop_assistant(
    session_id: str,
    assistant_id: int,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Update the student's workshop assistant (e.g. the step-1 instructions).

    The wizard creates the assistant on first completion of step 1, but the
    student can go back and edit the "Instructions" afterwards. With only a
    create endpoint, those edits were never persisted to ``system_prompt``, so
    the observability panel (and the LLM) saw an empty system prompt. This
    route closes that gap: it updates the fields the wizard owns on an
    assistant the student already created.
    """
    principal = _verify_workshop_principal(session_id, token)
    _verify_assistant_ownership(assistant_id, principal)

    existing = _db_manager.get_assistant_by_id(assistant_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Assistant not found")

    updated = Assistant(
        name=body.get("name", existing.name),
        description=body.get("description", existing.description),
        owner=existing.owner,
        api_callback=body.get("api_callback", existing.metadata),
        system_prompt=body.get("system_prompt", existing.system_prompt),
        prompt_template=body.get("prompt_template", existing.prompt_template),
        organization_id=existing.organization_id,
        # Deprecated fields — always empty strings, kept for DB compatibility.
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=body.get("rag_top_k", existing.RAG_Top_k),
        RAG_collections=body.get("rag_collections", existing.RAG_collections),
    )

    if not _db_manager.update_assistant(assistant_id, updated):
        raise HTTPException(status_code=500, detail="Failed to update assistant")

    return {"success": True, "assistant_id": assistant_id}


@router.post("/sessions/{session_id}/assistant/{assistant_id}/doc")
async def attach_workshop_document(
    session_id: str,
    assistant_id: int,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Student attaches a document to their assistant. Restricted scope.

    Placeholder: content ingestion is wired in a later phase. Validates scope.
    """
    principal = _verify_workshop_principal(session_id, token)
    _verify_assistant_ownership(assistant_id, principal)
    return {"success": True, "document_id": None, "status": "pending"}


@router.post("/sessions/{session_id}/assistant/{assistant_id}/kb")
async def connect_workshop_kb(
    session_id: str,
    assistant_id: int,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Student connects a knowledge base. Restricted scope.

    Placeholder: KB wiring is a later phase. Validates scope.
    """
    principal = _verify_workshop_principal(session_id, token)
    _verify_assistant_ownership(assistant_id, principal)
    return {"success": True, "kb_id": body.get("kb_id"), "status": "pending"}


@router.post("/sessions/{session_id}/assistant/{assistant_id}/chat")
async def chat_with_workshop_assistant(
    session_id: str,
    assistant_id: int,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Streamed chat with the student's workshop assistant (observability + tools).

    The student principal is verified (header token), the assistant must belong
    to this student (ownership check), then we delegate to the standard
    completion pipeline (``run_lamb_assistant``) which emits the same SSE
    dialect the rest of LAMB emits: ``choices[].delta.content`` chunks,
    ``{"type":"tool_event", ...}`` frames from the ToolLoop, and
    ``{"type":"observability", ...}`` injected right before ``[DONE]``.
    """
    principal = _verify_workshop_principal(session_id, token)
    _verify_assistant_ownership(assistant_id, principal)

    from lamb.completions.main import run_lamb_assistant

    completion_request = {
        "messages": body.get("messages", []),
        "stream": True,
        "observability": body.get("observability", True),
        "tools": _resolve_tool_definitions(body.get("tools")),
        "tool_choice": body.get("tool_choice", "auto"),
    }

    response = await run_lamb_assistant(
        request=completion_request,
        assistant=assistant_id,
        headers=None,
    )
    if isinstance(response, StreamingResponse):
        return response
    # Non-streaming fallback (shouldn't happen with stream=True) — pass through.
    return response


@router.post("/sessions/{session_id}/submit")
async def submit_workshop(
    session_id: str,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Submit the workshop — serialize session + reflection (consumed by grading)."""
    _verify_workshop_principal(session_id, token)

    _db_manager.submit_workshop_session(
        session_id=session_id,
        saved_chat=body.get("saved_chat"),
        reflection=body.get("reflection"),
    )
    return {"success": True, "status": "submitted"}


def _decode_workshop_student(token: str) -> Dict[str, Any]:
    """Decode a workshop_student token, or raise 401. No session binding check."""
    from lamb import auth as lamb_auth

    data = lamb_auth.decode_token(token)
    if not data or data.get("scope") != "workshop_student":
        raise HTTPException(status_code=401, detail="Invalid workshop token")
    return data


def _wizard_url(request: Request, activity_id: Any, token: str) -> str:
    """Build the public wizard URL for a student's workshop activity."""
    from lamb.lti_activity_manager import LtiActivityManager

    public_base = LtiActivityManager().get_public_base_url(request)
    return f"{public_base}/m/workshop/{activity_id}?token={token}"


@router.get("/consent")
async def consent_page(request: Request, token: str = ""):
    """Show the consent page on first visit; skip straight to the wizard after.

    A student who already consented (lti_activity_users.consent_given_at set) is
    redirected to the wizard instead of being asked again.
    """
    data = _decode_workshop_student(token)
    activity_id = data.get("activity_id")
    email = data.get("email")

    student = None
    if activity_id and email:
        student = _db_manager.get_activity_user(activity_id=activity_id, user_email=email)

    if student and student.get("consent_given_at"):
        return RedirectResponse(url=_wizard_url(request, activity_id, token), status_code=303)

    return _templates.TemplateResponse(request, "consent.html", {"token": token})


@router.post("/consent")
async def consent_submit(request: Request, token: str = Form(...)):
    """Record student consent then redirect to the wizard."""
    data = _decode_workshop_student(token)
    activity_id = data.get("activity_id")
    email = data.get("email")
    if activity_id and email:
        _db_manager.record_student_consent(activity_id, email)

    return RedirectResponse(url=_wizard_url(request, activity_id, token), status_code=303)