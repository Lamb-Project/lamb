"""Workshop routers — restricted creator routes for students building assistants.

Students get a virtual principal scoped to their activity. They can create an
assistant and submit their work — but CANNOT publish, share, access other
tenants' data, or touch other students' work.

Document/KB attachment (content ingestion) is wired in a later phase; those
routes validate scope + quota and return an accepted reference.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Header

from lamb.database_manager import LambDatabaseManager
from lamb.lamb_classes import Assistant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workshop", tags=["workshop"])

_db_manager = LambDatabaseManager()

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
        raise HTTPException(status_code=500, detail="Failed to create assistant")

    _db_manager.update_workshop_session_assistant(session_id, assistant_id)

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
    return {"success": True, "document_id": None, "status": "pending_phase4"}


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
    return {"success": True, "kb_id": body.get("kb_id"), "status": "pending_phase4"}


@router.post("/sessions/{session_id}/submit")
async def submit_workshop(
    session_id: str,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Submit the workshop — serialize session + reflection (Phase 5 consumes)."""
    _verify_workshop_principal(session_id, token)

    _db_manager.submit_workshop_session(
        session_id=session_id,
        saved_chat=body.get("saved_chat"),
        reflection=body.get("reflection"),
    )
    return {"success": True, "status": "submitted"}


@router.post("/consent")
async def consent_submit(body: Dict[str, Any], token: str = Header(...)):
    """Record student consent then proceed to the wizard."""
    from lamb import auth as lamb_auth

    data = lamb_auth.decode_token(token)
    if not data or data.get("scope") != "workshop_student":
        raise HTTPException(status_code=401, detail="Invalid workshop token")

    activity_id = data.get("activity_id")
    email = data.get("email")
    if activity_id and email:
        _db_manager.record_student_consent(activity_id, email)

    return {"success": True}
