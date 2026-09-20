"""Workshop routers — restricted creator routes for students building assistants.

Students get a virtual principal scoped to their activity. They can create an
assistant and submit their work — but CANNOT publish, share, access other
tenants' data, or touch other students' work.

Document/KB attachment is real: the backend acts as the activity instructor's
creator identity to create/ingest/query the KB server, so students never call
``/creator/*`` directly.

- GET  /sessions/{session_id}          — restore build progress after reload
- POST /sessions/{session_id}/assistant/{assistant_id}/doc — multipart upload
- GET  /sessions/{session_id}/doc/status — ingestion job polling
- POST /sessions/{session_id}/assistant/{assistant_id}/kb — probe retrieval
- POST /sessions/{session_id}/assistant/{assistant_id}/kb/query — KB query
- POST /sessions/{session_id}/assistant/{assistant_id}/chat — streamed chat
  with observability + tool_event SSE frames (same SSE dialect the rest of
  LAMB emits).
- POST /sessions/{session_id}/submit    — persist chat + reflection
- POST /sessions/{session_id}/evaluate  — rubric-based formative feedback
- GET  /sessions/{session_id}/evaluation — restore generated feedback
"""

import json
import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Header, Form, Request, File, UploadFile, Query
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from lamb.completions.tools.definitions import WORKSHOP_TOOLS
from lamb.database_manager import LambDatabaseManager
from lamb.lamb_classes import Assistant
from lamb.modules.workshop import kb as workshop_kb

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
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10 MB upload cap



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


def _apply_rag_defaults(
    api_callback: Any, rag_collections: Any
) -> tuple[str, str]:
    """Return (api_callback, rag_collections) with sane RAG wiring.

    ``rag_collections`` is normalized to a comma-separated string (``simple_rag``
    does not parse JSON arrays). When a collection is present, the metadata's
    ``rag_processor`` defaults to ``simple_rag`` unless already set.
    """
    collections = rag_collections
    if isinstance(collections, str):
        stripped = collections.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, (list, tuple)):
                    collections = parsed
            except (json.JSONDecodeError, TypeError):
                pass
    if isinstance(collections, (list, tuple)):
        collections = ",".join(str(c) for c in collections)
    collections = (collections or "").strip()
    if collections in ("[]", "null"):
        collections = ""

    try:
        metadata = json.loads(api_callback) if api_callback else {}
    except (json.JSONDecodeError, TypeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}

    if collections and not metadata.get("rag_processor"):
        metadata["rag_processor"] = "simple_rag"

    return json.dumps(metadata), collections


def _session_activity(session: Dict[str, Any]) -> Dict[str, Any]:
    """Load the LTI activity a workshop session belongs to, or raise 404."""
    activity = _db_manager.get_lti_activity_by_id(session.get("activity_id"))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


def _raise_kb_error(e: Exception) -> None:
    """Translate KB helper failures into clean HTTP responses."""
    if isinstance(e, HTTPException):
        raise e
    detail = str(e)
    if "not found" in detail.lower():
        raise HTTPException(status_code=404, detail=detail)
    raise HTTPException(status_code=502, detail=f"Knowledge base error: {detail}")


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
        "kb_id": session.get("kb_id"),
        "document_file_id": session.get("document_file_id"),
        "document_name": session.get("document_name"),
        "document_status": session.get("document_status"),
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

    api_callback, rag_collections = _apply_rag_defaults(
        body.get("api_callback", "{}"), body.get("rag_collections", ""))

    assistant = Assistant(
        name=body.get("name", "My AI Assistant"),
        description=body.get("description", ""),
        owner=owner_email,
        api_callback=api_callback,
        system_prompt=body.get("system_prompt", ""),
        prompt_template=body.get("prompt_template", ""),
        organization_id=principal.get("organization_id"),
        # Deprecated fields — always empty strings, kept for DB compatibility
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=body.get("rag_top_k", 3),
        RAG_collections=rag_collections,
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

    api_callback, rag_collections = _apply_rag_defaults(
        body.get("api_callback", existing.metadata),
        body.get("rag_collections", existing.RAG_collections),
    )

    updated = Assistant(
        name=body.get("name", existing.name),
        description=body.get("description", existing.description),
        owner=existing.owner,
        api_callback=api_callback,
        system_prompt=body.get("system_prompt", existing.system_prompt),
        prompt_template=body.get("prompt_template", existing.prompt_template),
        organization_id=existing.organization_id,
        # Deprecated fields — always empty strings, kept for DB compatibility.
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=body.get("rag_top_k", existing.RAG_Top_k),
        RAG_collections=rag_collections,
    )
    if not _db_manager.update_assistant(assistant_id, updated):
        raise HTTPException(status_code=500, detail="Failed to update assistant")

    return {"success": True, "assistant_id": assistant_id}


@router.post("/sessions/{session_id}/assistant/{assistant_id}/doc")
async def attach_workshop_document(
    session_id: str,
    assistant_id: int,
    file: UploadFile = File(...),
    token: str = Header(...),
):
    """Student attaches a document to their assistant (multipart upload).

    Real ingestion: ensures a session KB, uploads the file to the KB server,
    records the ingestion job on the session, and wires the KB into the
    assistant's RAG config. Ingestion is async on the KB server; the client
    polls ``GET .../doc/status?job_id=``.
    """
    principal = _verify_workshop_principal(session_id, token)
    _verify_assistant_ownership(assistant_id, principal)

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Quota (Lean MVP: one document per session). Failed jobs may be retried.
    if session.get("document_file_id") and session.get("document_status") != "failed":
        raise HTTPException(status_code=429, detail="Document already attached")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    activity = _session_activity(session)
    try:
        kb_id = await workshop_kb.ensure_session_kb(activity, session)
        result = await workshop_kb.ingest_document(
            kb_id,
            file.filename or "document.txt",
            content,
            activity,
            file.content_type or "application/octet-stream",
        )
    except Exception as e:
        _raise_kb_error(e)

    _db_manager.update_workshop_session_kb(
        session_id,
        kb_id=kb_id,
        document_file_id=result.get("file_registry_id"),
        document_name=result.get("original_filename") or file.filename,
        document_status=result.get("status", "processing"),
    )
    workshop_kb.link_kb_to_assistant(assistant_id, kb_id)

    return {
        "success": True,
        "kb_id": kb_id,
        "file_registry_id": result.get("file_registry_id"),
        "status": result.get("status", "processing"),
    }


@router.get("/sessions/{session_id}/doc/status")
async def get_workshop_document_status(
    session_id: str,
    job_id: str = Query(...),
    token: str = Header(...),
):
    """Proxy the KB server's ingestion job status for the session's document."""
    _verify_workshop_principal(session_id, token)

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    kb_id = session.get("kb_id")
    if not kb_id:
        raise HTTPException(status_code=404, detail="No knowledge base for this session")

    activity = _session_activity(session)
    try:
        result = await workshop_kb.get_ingestion_status(kb_id, job_id, activity)
    except Exception as e:
        _raise_kb_error(e)
    _db_manager.update_workshop_session_kb(
        session_id, document_status=result.get("status"))

    return {"success": True, "kb_id": kb_id, **result}


@router.post("/sessions/{session_id}/assistant/{assistant_id}/kb")
async def connect_workshop_kb(
    session_id: str,
    assistant_id: int,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Connect the session KB and run a real probe query.

    Returns the matched excerpts + similarity so the student sees exactly what
    the assistant can retrieve. Also wires the KB into the assistant's RAG.
    """
    principal = _verify_workshop_principal(session_id, token)
    _verify_assistant_ownership(assistant_id, principal)

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    activity = _session_activity(session)
    kb_id = body.get("kb_id") or session.get("kb_id")
    try:
        if not kb_id:
            kb_id = await workshop_kb.ensure_session_kb(activity, session)

        query_text = (body.get("query") or "").strip() or "What is this document about?"
        top_k = int(body.get("top_k") or body.get("rag_top_k") or 3)
        result = await workshop_kb.query_session_kb(kb_id, query_text, top_k, activity)
    except Exception as e:
        _raise_kb_error(e)

    workshop_kb.link_kb_to_assistant(assistant_id, kb_id)

    return {
        "success": True,
        "kb_id": kb_id,
        "query": query_text,
        "results": result.get("results", []),
        "count": result.get("count", 0),
    }


@router.post("/sessions/{session_id}/assistant/{assistant_id}/kb/query")
async def query_workshop_kb(
    session_id: str,
    assistant_id: int,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Real KB query against the session's collection (student/tool path)."""
    principal = _verify_workshop_principal(session_id, token)
    _verify_assistant_ownership(assistant_id, principal)

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    kb_id = body.get("kb_id") or session.get("kb_id")
    if not kb_id:
        raise HTTPException(status_code=400, detail="No knowledge base connected")

    query_text = (body.get("query") or "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="No query provided")

    activity = _session_activity(session)
    top_k = int(body.get("top_k") or body.get("rag_top_k") or 3)
    try:
        result = await workshop_kb.query_session_kb(
            kb_id, query_text, top_k, activity)
    except Exception as e:
        _raise_kb_error(e)

    return {
        "success": True,
        "kb_id": kb_id,
        "query": query_text,
        "results": result.get("results", []),
        "count": result.get("count", 0),
    }


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


@router.post("/sessions/{session_id}/evaluate")
async def evaluate_workshop_session(
    session_id: str,
    body: Dict[str, Any],
    token: str = Header(...),
):
    """Generate rubric-based formative feedback for a submitted session.

    Triggered by the student after submit (and retryable). When the activity
    has no rubric attached, returns ``{"configured": false}`` without calling
    any LLM. The feedback is advisory — it never writes a grade.
    """
    from lamb.modules.workshop.evaluation import evaluate_session

    _verify_workshop_principal(session_id, token)

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    activity = _session_activity(session)
    result = await evaluate_session(
        session, activity, rubric_id=body.get("rubric_id"))
    return result


@router.get("/sessions/{session_id}/evaluation")
async def get_workshop_evaluation(
    session_id: str,
    token: str = Header(...),
):
    """Return the stored evaluation for a session (page-reload restore)."""
    _verify_workshop_principal(session_id, token)

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    activity = _session_activity(session)
    evaluation = _db_manager.get_workshop_evaluation(session_id)
    configured = bool(activity.get("rubric_id")) or evaluation is not None

    return {"configured": configured, "evaluation": evaluation}


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