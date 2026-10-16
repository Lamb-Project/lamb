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
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header, Form, Request, File, UploadFile, Query
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from lamb.completions.tools.definitions import WORKSHOP_TOOLS
from lamb.database_manager import LambDatabaseManager
from lamb.lamb_classes import Assistant
from lamb.modules.workshop import kb as workshop_kb
from lamb.modules.workshop.i18n import CONSENT_VERSION

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

    An expired token is reported as ``401 detail="token_expired"`` (a machine
    readable string the frontend keys on to renew silently or to send the
    student back to the course page) instead of the generic 401, because a
    lesson outlives the 30-minute token and "invalid token" is unactionable.
    """
    from lamb import auth as lamb_auth

    data = lamb_auth.decode_token(token)
    if not data:
        if _token_is_expired(token):
            raise HTTPException(status_code=401, detail="token_expired")
        raise HTTPException(status_code=401, detail="Invalid workshop token")

    if data.get("scope") != "workshop_student":
        raise HTTPException(status_code=401, detail="Invalid workshop token")

    if data.get("session_id") != session_id:
        raise HTTPException(status_code=403, detail="Session mismatch")

    return data


def _token_is_expired(token: str) -> bool:
    """Whether a token is a well-formed, correctly signed, expired JWT."""
    from lamb import auth as lamb_auth

    _, reason = lamb_auth.decode_token_ex(token)
    return reason == "expired"


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


def _normalize_kb_id(value: Any) -> Any:
    """Normalize an incoming kb_id (str/int/None) to a string or None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "undefined"):
        return None
    return text


def _collection_ids(value: Any) -> list:
    """Parse a rag_collections value (list, JSON array or comma string).

    ``simple_rag`` persists collections as a comma-separated string, but the
    wizard and older clients may hand us a JSON array or a real list.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = [str(c) for c in value]
    else:
        text = str(value).strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            items = ([str(c) for c in parsed]
                     if isinstance(parsed, (list, tuple)) else text.split(","))
        else:
            items = text.split(",")
    return [c.strip() for c in items if c and c.strip()]


def _resolve_session_kb_id(
    session: Dict[str, Any], requested: Any
) -> Any:
    """Resolve the KB id for a session-bound route (S1, decision C1).

    The session's ``kb_id`` is the only KB a student may touch, so an incoming
    ``kb_id`` is treated as an *assertion* rather than as a choice:

    - nothing sent → the session's kb_id (possibly None)
    - value equal to the session's kb_id → that value
    - session has no KB but a value was sent → 400: the workspace is in an
      inconsistent state (e.g. after an erase), which is not an attack
    - value differs from the session's kb_id → 403 + warning: cross-session
      read attempt
    """
    requested_id = _normalize_kb_id(requested)
    if requested_id is None:
        return _normalize_kb_id(session.get("kb_id"))

    session_kb = _normalize_kb_id(session.get("kb_id"))
    if session_kb is None:
        logger.warning(
            "Workshop KB: kb_id %r sent for session %s that has no KB "
            "(state anomaly, not an attack)",
            requested_id, session.get("id"))
        raise HTTPException(
            status_code=400,
            detail=(
                "This workshop workspace has no knowledge base yet. "
                "Upload a document in step 2 first."
            ),
        )
    if requested_id != session_kb:
        logger.warning(
            "Workshop KB: rejecting foreign kb_id %r for session %s "
            "(session kb_id=%r)",
            requested_id, session.get("id"), session_kb)
        raise HTTPException(
            status_code=403, detail="kb_id does not belong to this session")
    return session_kb


def _assert_rag_collections_allowed(
    session: Dict[str, Any], rag_collections: Any
) -> str:
    """Whitelist-check a *client-supplied* rag_collections value (S1, C1/C2).

    A workshop assistant may only reference its own session KB. Empty means
    "no RAG wiring yet" and is always allowed. Anything else is either a state
    anomaly (no session KB yet → 400) or a cross-session injection (→ 403).

    Returns the normalized comma-separated collections string to persist.
    """
    requested = _collection_ids(rag_collections)
    if not requested:
        return ""

    session_kb = _normalize_kb_id(session.get("kb_id"))
    if session_kb is None:
        logger.warning(
            "Workshop assistant: rag_collections=%s supplied for session %s "
            "that has no KB (state anomaly)", requested, session.get("id"))
        raise HTTPException(
            status_code=400,
            detail=(
                "This workshop workspace has no knowledge base yet, so no "
                "collections can be attached."
            ),
        )
    if requested != [session_kb]:
        logger.warning(
            "Workshop assistant: rejecting foreign rag_collections=%s for "
            "session %s (session kb_id=%r)",
            requested, session.get("id"), session_kb)
        raise HTTPException(
            status_code=403,
            detail="rag_collections must reference this session's knowledge base",
        )
    return session_kb


def _sanitize_stored_collections(
    session: Dict[str, Any], stored: Any
) -> str:
    """Repair a *stored* rag_collections value instead of rejecting it.

    Used when a PATCH does not mention rag_collections: rewriting the whole
    assistant row must not turn pre-existing dirty data (foreign collection
    ids written before S1) into a hard failure for an unrelated edit such as
    the step-1 instructions. Foreign ids are dropped and recorded.
    """
    requested = _collection_ids(stored)
    if not requested:
        return ""

    session_kb = _normalize_kb_id(session.get("kb_id"))
    if session_kb is None:
        logger.warning(
            "Workshop assistant: clearing stored rag_collections=%s on "
            "session %s that has no KB", requested, session.get("id"))
        return ""
    if requested != [session_kb]:
        logger.warning(
            "Workshop assistant: dropping foreign stored rag_collections=%s "
            "for session %s (session kb_id=%r) — historical dirty data",
            requested, session.get("id"), session_kb)
        return session_kb
    return session_kb


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


@router.post("/sessions/{session_id}/refresh")
async def refresh_workshop_token(session_id: str, token: str = Header(...)):
    """Mint a fresh workshop token from a still-valid one (W1).

    A lesson runs longer than the 30-minute token TTL, so the wizard renews in
    the background instead of dropping the student mid-activity.

    Renewal is deliberately only possible while the current token is valid: an
    expired token can never be renewed (that is the security boundary — the
    student re-enters from the course page). The renewed token keeps the same
    scope and the same ``session_id``; only ``exp``/``iat`` move.
    """
    from lamb import auth as lamb_auth
    from lamb.modules.workshop import service as workshop_service

    data, reason = lamb_auth.decode_token_ex(token)
    if reason == "expired":
        raise HTTPException(status_code=401, detail="token_expired")
    if not data or data.get("scope") != "workshop_student":
        raise HTTPException(status_code=401, detail="Invalid workshop token")
    if data.get("session_id") != session_id:
        raise HTTPException(status_code=403, detail="Session mismatch")

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    principal = {
        key: value for key, value in data.items()
        if key not in ("exp", "iat", "scope")
    }
    principal["session_id"] = session_id
    principal["scope"] = "workshop_student"

    new_token = workshop_service._create_workshop_token(principal)
    ttl = workshop_service.workshop_token_ttl()
    logger.info(
        "Workshop token renewed for session %s (principal=%s, ttl=%ss)",
        session_id, data.get("email"), ttl)
    return {"success": True, "token": new_token, "expires_in": ttl}


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

    # S1: a student may only wire their own session KB into the assistant.
    session = existing or {"id": session_id}
    allowed_collections = _assert_rag_collections_allowed(
        session, body.get("rag_collections", ""))

    api_callback, rag_collections = _apply_rag_defaults(
        body.get("api_callback", "{}"), allowed_collections)

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

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # S1: an explicitly supplied value is validated strictly (403 on a foreign
    # collection); a stored value that PATCH never mentions is repaired instead
    # of rejected, so unrelated edits keep working on legacy rows.
    if "rag_collections" in body:
        rag_collections = _assert_rag_collections_allowed(
            session, body.get("rag_collections"))
    else:
        rag_collections = _sanitize_stored_collections(
            session, existing.RAG_collections)

    api_callback, rag_collections = _apply_rag_defaults(
        body.get("api_callback", existing.metadata),
        rag_collections,
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


@router.delete("/sessions/{session_id}/assistant/{assistant_id}/doc")
async def remove_workshop_document(
    session_id: str,
    assistant_id: int,
    token: str = Header(...),
):
    """Student removes the attached document so another can be uploaded (C22).

    Upload is capped at one document per session, so removing it only in the
    browser left the session still holding the old one and every later upload
    answered 429. This deletes the session KB (collection and files), forgets
    the document binding and unwires the assistant's RAG; the conversation,
    reflection and wizard state are untouched (that is the ``erase`` level,
    C18). The KB goes first: if the KB server is unavailable nothing local
    changes, so the student can simply try again. Idempotent.
    """
    principal = _verify_workshop_principal(session_id, token)
    _verify_assistant_ownership(assistant_id, principal)

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # kb_id is read from the session, never from the client (S1).
    kb_id = session.get("kb_id")
    if kb_id:
        activity = _session_activity(session)
        try:
            await workshop_kb.delete_session_kb(activity, str(kb_id))
        except Exception as e:
            _raise_kb_error(e)

    _db_manager.clear_workshop_session_document(session_id)
    _db_manager.clear_assistant_rag_collections(assistant_id)

    return {"success": True, "removed": bool(kb_id)}


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


@router.get("/sessions/{session_id}/doc/files")
async def get_workshop_document_files(session_id: str, token: str = Header(...)):
    """Read-only view of the session KB's file registry (D2 / C16).

    Why a proxy instead of putting this in the connect/query responses: the
    session's ``kb_id`` and the document scope are decided server-side, so the
    student can never ask for another session's registry, and the teaching
    panel gets *deterministic* facts about ingestion — how many chunks the
    document became, with which chunk size and overlap — rather than an
    inference from whichever top-k excerpts a probe happened to return.
    """
    _verify_workshop_principal(session_id, token)

    session = _db_manager.get_workshop_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    kb_id = session.get("kb_id")
    if not kb_id:
        raise HTTPException(
            status_code=404, detail="No knowledge base for this session")

    activity = _session_activity(session)
    try:
        result = await workshop_kb.list_collection_files(activity, kb_id)
    except Exception as e:
        _raise_kb_error(e)

    return {
        "success": True,
        "kb_id": kb_id,
        "document_name": session.get("document_name"),
        "document_status": session.get("document_status"),
        "files": result.get("items", []),
        "count": result.get("count", 0),
    }


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
    kb_id = _resolve_session_kb_id(session, body.get("kb_id"))
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

    kb_id = _resolve_session_kb_id(session, body.get("kb_id"))
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

    rag_mode = (str(body.get("rag_mode") or "on")).strip().lower()
    if rag_mode not in ("on", "off"):
        raise HTTPException(status_code=400, detail="rag_mode must be 'on' or 'off'")

    tools = _resolve_tool_definitions(body.get("tools"))
    if rag_mode == "off":
        # Turning RAG off must *also* remove the retrieval tool: leaving
        # `kb_query` in place would let the model fetch the very material the
        # experiment is meant to withhold, and the two runs would look
        # identical (decision C10).
        tools = [
            t for t in (tools or [])
            if ((t or {}).get("function") or {}).get("name") != "kb_query"
        ] or None

    completion_request = {
        "messages": body.get("messages", []),
        "stream": True,
        "observability": body.get("observability", True),
        "tools": tools,
        "tool_choice": body.get("tool_choice", "auto"),
    }
    if rag_mode == "off":
        # Namespaced private key: read by `run_lamb_assistant`, stripped from
        # anything that arrives through the public completion proxy.
        completion_request["_workshop_disable_rag"] = True

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
        build_state=body.get("build_state"),
    )

    # A submitted *pilot* is what opens the activity for students: the teacher
    # has now seen the whole flow from the student's side (decision C13).
    session = _db_manager.get_workshop_session_by_id(session_id)
    if session and session.get("is_pilot"):
        _db_manager.mark_workshop_pilot_completed(session.get("activity_id"))
        logger.info(
            "Workshop pilot completed for activity %s (session %s)",
            session.get("activity_id"), session_id)
        return {
            "success": True,
            "status": "submitted",
            "pilot_completed": True,
        }

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
    if not data:
        if _token_is_expired(token):
            raise HTTPException(status_code=401, detail="token_expired")
        raise HTTPException(status_code=401, detail="Invalid workshop token")
    if data.get("scope") != "workshop_student":
        raise HTTPException(status_code=401, detail="Invalid workshop token")
    return data


def _wizard_url(
    request: Request, activity_id: Any, token: str, locale: str = ""
) -> str:
    """Build the public wizard URL for a student's workshop activity."""
    from lamb.lti_activity_manager import LtiActivityManager

    public_base = LtiActivityManager().get_public_base_url(request)
    url = f"{public_base}/m/workshop/{activity_id}?token={token}"
    if locale:
        url += f"&lang={locale}"
    return url


# ─────────────────────────────────────────────────────────────────────────────
# Consent scope disclosure (decision C17)
# ─────────────────────────────────────────────────────────────────────────────

# Providers that are, by construction, external services. Anything else is
# classified from its configured base URL (see ``classify_model_class``).
_EXTERNAL_PROVIDERS = {"openai", "anthropic", "google", "gemini"}
# Providers that never leave the deployment (no third party sees the data).
_LOCAL_PROVIDERS = {"ollama", "bypass"}


def classify_model_class(connector: str, base_url: str = "") -> str:
    """Classify a resolved connector as ``local``, ``external`` or ``unknown``.

    The consent page must not claim a model setup the deployment does not have,
    so this reads the *resolved* provider rather than a hard-coded sentence. A
    self-hosted OpenAI-compatible endpoint (``llm``) is judged by its URL:
    a loopback/private host stays local, anything else is external.
    """
    provider = (connector or "").strip().lower()
    if provider in _LOCAL_PROVIDERS:
        return "local"
    if provider in _EXTERNAL_PROVIDERS:
        return "external"
    if not provider:
        return "unknown"

    url = (base_url or "").strip().lower()
    if not url:
        # An unknown provider with no endpoint we can inspect: assume it leaves
        # the deployment. Over-disclosing is the safe direction.
        return "external"
    if any(token in url for token in (
            "localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal",
            "://10.", "://192.168.", "://172.1", "://172.2", "://172.3")):
        return "local"
    return "external"


def resolve_consent_model_info(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Which model actually sees student work, via the real resolution chain.

    Reuses ``OrganizationConfigResolver.resolve_model_for_completion`` — the
    same call the completion pipeline makes — so the disclosure cannot drift
    from the deployment's real configuration. Returns
    ``{"model_class", "model", "connector"}``.
    """
    owner = (activity or {}).get("owner_email") or (
        activity or {}).get("configured_by_email")
    if not owner:
        return {"model_class": "unknown", "model": "", "connector": ""}

    try:
        from lamb.completions.main import load_plugins
        from lamb.completions.org_config_resolver import OrganizationConfigResolver

        resolver = OrganizationConfigResolver(owner)
        resolved = resolver.resolve_model_for_completion(
            None, None, available_providers=set(load_plugins("connectors")))
        connector = resolved.get("provider") or ""
        model = resolved.get("model") or ""
        provider_config = {}
        try:
            provider_config = resolver.get_provider_config(connector) or {}
        except Exception:  # pragma: no cover - config lookup is best effort
            provider_config = {}
        model_class = classify_model_class(
            connector, provider_config.get("base_url") or "")
    except Exception as e:
        logger.info(
            "Workshop consent: model resolution unavailable for %s: %s",
            owner, e)
        return {"model_class": "unknown", "model": "", "connector": ""}

    return {"model_class": model_class, "model": model, "connector": connector}


def resolve_consent_model_info_for_token(token: str) -> Dict[str, Any]:
    """``consent/info`` payload for a workshop token (see the route)."""
    data = _decode_workshop_student(token)
    activity_id = data.get("activity_id")
    activity = (
        _db_manager.get_lti_activity_by_id(activity_id) if activity_id else None)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    from lamb.modules.workshop.retention import retention_days

    info = resolve_consent_model_info(activity)
    info["retention_days"] = retention_days(activity)
    info["consent_version"] = CONSENT_VERSION
    return info


def _reconsent_required(activity: Optional[Dict[str, Any]]) -> bool:
    """Whether a notice-version change forces students to accept again.

    Activity/org level switch ``require_reconsent_on_version_change``; defaults
    to **on** (C20) because the new notice materially widens what is disclosed.
    """
    if not activity:
        return True
    owner = activity.get("owner_email") or activity.get("configured_by_email")
    if not owner:
        return True
    try:
        from lamb.completions.org_config_resolver import OrganizationConfigResolver

        value = OrganizationConfigResolver(owner).get_feature_value(
            "require_reconsent_on_version_change", 1)
        if isinstance(value, str):
            return value.strip().lower() not in ("0", "false", "no", "off")
        return bool(value)
    except Exception as e:
        logger.debug("Reconsent flag unavailable (%s) — defaulting to on", e)
        return True


def _needs_reconsent(
    activity: Optional[Dict[str, Any]], student: Dict[str, Any]
) -> bool:
    """Whether a returning student must accept the current notice again."""
    if not _reconsent_required(activity):
        return False
    return (student.get("consent_version") or "") != CONSENT_VERSION


def _consent_context(
    request: Request,
    activity: Optional[Dict[str, Any]],
    locale: str,
    token: str,
) -> Dict[str, Any]:
    """Template context for the consent page (localized + truthful)."""
    from lamb.modules.workshop import i18n as workshop_i18n
    from lamb.modules.workshop.retention import retention_days

    strings = workshop_i18n.consent_strings(locale)
    model_info = (
        resolve_consent_model_info(activity) if activity
        else {"model_class": "unknown", "model": ""})
    days = retention_days(activity) if activity else None

    return {
        "request": request,
        "token": token,
        "lang": strings.get("lang", locale),
        "s": strings,
        "model_class": model_info.get("model_class", "unknown"),
        "model_name": model_info.get("model", ""),
        "retention_days": days,
        "retention_note": (
            strings.get("retentionDays", "").format(days=days) if days else ""
        ),
    }


@router.get("/consent")
async def consent_page(request: Request, token: str = "", lang: str = ""):
    """Show the consent page on first visit; skip straight to the wizard after.

    A student who already consented *to the current notice version*
    (``lti_activity_users.consent_given_at`` + ``consent_version``) is
    redirected to the wizard instead of being asked again. The page language
    follows the same chain as the wizard (``?lang=`` → Accept-Language → en).
    """
    from lamb.modules.workshop import i18n as workshop_i18n

    data = _decode_workshop_student(token)
    activity_id = data.get("activity_id")
    email = data.get("email")

    activity = (
        _db_manager.get_lti_activity_by_id(activity_id) if activity_id else None)
    locale = workshop_i18n.resolve_locale(request, activity, url_lang=lang)

    student = None
    if activity_id and email:
        student = _db_manager.get_activity_user(activity_id=activity_id, user_email=email)

    if student and student.get("consent_given_at") and not _needs_reconsent(
            activity, student):
        return RedirectResponse(
            url=_wizard_url(request, activity_id, token, locale), status_code=303)

    context = _consent_context(request, activity, locale, token)
    return _templates.TemplateResponse(request, "consent.html", context)


@router.get("/consent/info")
async def consent_info(token: str = ""):
    """What the consent page must disclose, resolved from the live config (C17).

    Returns ``{model_class, model, retention_days, consent_version}``. The
    classification comes from the same resolution chain the completion pipeline
    uses, so the page cannot describe a model setup the deployment lacks.

    Also usable by the SPA (same token contract) to render the disclosure
    outside the server-rendered consent page.
    """
    return resolve_consent_model_info_for_token(token)


@router.post("/consent")
async def consent_submit(request: Request, token: str = Form(...)):
    """Record student consent then redirect to the wizard."""
    data = _decode_workshop_student(token)
    activity_id = data.get("activity_id")
    email = data.get("email")
    if activity_id and email:
        _db_manager.record_student_consent(
            activity_id, email, consent_version=CONSENT_VERSION)

    return RedirectResponse(
        url=_wizard_url(request, activity_id, token, data.get("locale")),
        status_code=303)
