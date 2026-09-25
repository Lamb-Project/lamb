"""Workshop KB helper — real KB server wiring under the activity instructor's identity.

Students are virtual principals (no ``Creator_users`` row), so all KB server
operations are performed server-side under the activity owner's creator
identity. When that creator row is missing (historical dirty data) we fall back
to calling the KB server directly with the global/org KB config and warn.

The KB Server is a vendored, read-only dependency: we only talk to it over HTTP.
"""

import json
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 3
INGEST_PLUGIN = "simple_ingest"
INGEST_PARAMS = {"chunk_size": 1000, "chunk_unit": "char", "chunk_overlap": 200}
DEFAULT_EMBEDDINGS_MODEL = {
    "model": "default",
    "vendor": "default",
    "api_endpoint": "default",
    "apikey": "default",
}


def _db():
    """Late-bound db manager (keeps module import side-effect free)."""
    from lamb.database_manager import LambDatabaseManager

    return LambDatabaseManager()


def _session_kb_name(activity_id: int, activity_user_id: int) -> str:
    """Globally-unique, session-scoped collection name (Chroma names are global)."""
    return f"ws-{activity_id}-{activity_user_id}"


def _instructor_creator_user(activity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve the activity owner/configured-by email to a Creator_users row.

    Returns a dict shaped for ``KBServerManager`` (id/email/organization_id), or
    None when no creator row exists (caller falls back to a direct KB call).
    """
    email = activity.get("owner_email") or activity.get("configured_by_email")
    if not email:
        return None
    user = _db().get_creator_user_by_email(email)
    if not user:
        logger.warning(
            "Workshop KB: no Creator_users row for activity owner %s", email)
        return None
    return {
        "id": user.get("id"),
        "email": user.get("email") or email,
        "organization_id": user.get("organization_id")
        or activity.get("organization_id"),
    }


def _resolve_kb_config(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the KB server url/token for the activity's instructor (env fallback)."""
    from creator_interface.kb_server_manager import KBServerManager

    manager = KBServerManager()
    creator_user = _instructor_creator_user(activity)
    # ``_get_kb_config_for_user`` already falls back to global env config when the
    # org config cannot be resolved; passing no email forces the env path.
    config = manager._get_kb_config_for_user(creator_user or {"email": None})
    return {"manager": manager, "creator_user": creator_user, "config": config}


def _auth_headers(config: Dict[str, Any], json_content: bool = False) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {config.get('token')}"}
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


async def _find_collection_by_name(config: Dict[str, Any], name: str) -> Optional[str]:
    """Best-effort lookup of an existing collection id by name (idempotency)."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{config['url']}/collections",
                headers=_auth_headers(config),
                params={"limit": 1000},
            )
        if resp.status_code != 200:
            return None
        for item in resp.json().get("items", []):
            if item.get("name") == name:
                return str(item.get("id"))
    except httpx.RequestError as e:
        logger.warning("Workshop KB: collection lookup failed: %s", e)
    return None


async def _create_collection_direct(
    config: Dict[str, Any], name: str, owner: str
) -> str:
    """Create a collection directly (fallback path — no kb_registry entry)."""
    embedding_model = config.get("embedding_model")
    embeddings_model = (
        {
            "model": embedding_model,
            "vendor": "default",
            "api_endpoint": "default",
            "apikey": "default",
        }
        if embedding_model
        else dict(DEFAULT_EMBEDDINGS_MODEL)
    )
    payload = {
        "name": name,
        "description": "AI Workshop",
        "owner": owner,
        "visibility": "private",
        "embeddings_model": embeddings_model,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{config['url']}/collections",
            headers=_auth_headers(config, json_content=True),
            json=payload,
        )
    if resp.status_code == 201:
        return str(resp.json().get("id"))
    if resp.status_code == 409:
        existing = await _find_collection_by_name(config, name)
        if existing:
            return existing
    raise RuntimeError(
        f"KB server collection create failed ({resp.status_code}): {resp.text}")


async def ensure_session_kb(
    activity: Dict[str, Any], session: Dict[str, Any]
) -> str:
    """Create (or reuse) the session's KB collection. Returns kb_id.

    Reuses ``session['kb_id']`` when present; otherwise creates a private
    collection and persists the id on the session record.
    """
    existing = session.get("kb_id")
    if existing:
        return existing

    activity_id = activity.get("id")
    activity_user_id = session.get("activity_user_id")
    name = _session_kb_name(activity_id, activity_user_id)

    resolved = _resolve_kb_config(activity)
    manager = resolved["manager"]
    creator_user = resolved["creator_user"]
    config = resolved["config"]

    if creator_user:
        from creator_interface.knowledgebase_classes import KnowledgeBaseCreate
        from fastapi import HTTPException

        try:
            result = await manager.create_knowledge_base(
                KnowledgeBaseCreate(
                    name=name,
                    description="AI Workshop",
                    access_control="private",
                ),
                creator_user,
            )
            kb_id = str(result.get("id") or result.get("kb_id"))
        except HTTPException as e:
            if e.status_code != 409:
                raise
            # Name collision from a previous attempt that never persisted kb_id.
            kb_id = await _find_collection_by_name(config, name)
            if not kb_id:
                raise
    else:
        logger.warning(
            "Workshop KB: falling back to direct collection create for %s", name)
        owner = f"workshop:{activity_id}"
        kb_id = await _create_collection_direct(config, name, owner)

    _db().update_workshop_session_kb(session["id"], kb_id=kb_id)
    return kb_id


async def ingest_document(
    kb_id: str,
    filename: str,
    content: bytes,
    activity: Dict[str, Any],
    content_type: str = "application/octet-stream",
) -> Dict[str, Any]:
    """Upload a file to the KB. Returns {file_registry_id, status}."""
    config = _resolve_kb_config(activity)["config"]

    files = {"file": (filename, content, content_type)}
    data = {
        "collection_id": str(kb_id),
        "plugin_name": INGEST_PLUGIN,
        "plugin_params": json.dumps(INGEST_PARAMS),
    }
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{config['url']}/collections/{kb_id}/ingest-file",
            headers=_auth_headers(config),
            files=files,
            data=data,
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"KB server ingest failed ({resp.status_code}): {resp.text}")

    body = resp.json()
    file_registry_id = body.get("file_registry_id") or body.get("id")
    return {
        "file_registry_id": str(file_registry_id) if file_registry_id is not None else None,
        "status": body.get("status", "processing"),
        "original_filename": body.get("original_filename", filename),
    }


async def get_ingestion_status(
    kb_id: str, job_id: str, activity: Dict[str, Any]
) -> Dict[str, Any]:
    """Poll one ingestion job. Returns {status, progress, error_message, document_count}."""
    config = _resolve_kb_config(activity)["config"]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{config['url']}/collections/{kb_id}/ingestion-jobs/{job_id}",
            headers=_auth_headers(config),
        )
    if resp.status_code == 404:
        raise RuntimeError("Ingestion job not found")
    if resp.status_code != 200:
        raise RuntimeError(
            f"KB server status failed ({resp.status_code}): {resp.text}")

    body = resp.json()
    return {
        "status": body.get("status"),
        "progress": body.get("progress") or {},
        "error_message": body.get("error_message"),
        "document_count": body.get("document_count", 0),
    }


async def query_kb_collection(
    config: Dict[str, Any],
    kb_id: str,
    query_text: str,
    top_k: int = DEFAULT_TOP_K,
    plugin_name: str = "simple_query",
) -> Dict[str, Any]:
    """Query a single KB collection. Returns {results, count}.

    ``results`` entries carry ``similarity``, ``data`` (the chunk text) and
    ``metadata`` as returned by the KB server.
    """
    payload = {
        "query_text": query_text,
        "top_k": top_k,
        "threshold": 0.0,
        "plugin_params": {},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{config['url']}/collections/{kb_id}/query",
            headers=_auth_headers(config, json_content=True),
            params={"plugin_name": plugin_name},
            json=payload,
        )
    if resp.status_code != 200:
        raise RuntimeError(
            f"KB server query failed ({resp.status_code}): {resp.text}")

    body = resp.json()
    results = body.get("results", body.get("documents", [])) or []
    return {"results": results, "count": body.get("count", len(results))}


async def query_session_kb(
    kb_id: str, query_text: str, top_k: int, activity: Dict[str, Any]
) -> Dict[str, Any]:
    """Query the session KB under the activity instructor's KB config."""
    config = _resolve_kb_config(activity)["config"]
    return await query_kb_collection(config, kb_id, query_text, top_k)


def config_for_owner(owner_email: Optional[str]) -> Dict[str, Any]:
    """Resolve KB config for an assistant owner (org-aware, env fallback).

    Used by the ``kb_query`` tool, which only has the assistant's owner email
    (not an activity). Falls back to global env config when the owner has no
    resolvable organization.
    """
    from creator_interface.kb_server_manager import KBServerManager

    manager = KBServerManager()
    return manager._get_kb_config_for_user({"email": owner_email})


def link_kb_to_assistant(
    assistant_id: int, kb_id: str, org_id: Optional[int] = None
) -> bool:
    """Set RAG_collections=kb_id (comma-separated) + metadata.rag_processor.

    Preserves the assistant's existing connector/llm/prompt_processor and all
    non-RAG fields; only RAG wiring is touched.
    """
    from lamb.lamb_classes import Assistant

    db = _db()
    existing = db.get_assistant_by_id(assistant_id)
    if not existing:
        return False

    try:
        metadata = json.loads(existing.metadata) if existing.metadata else {}
    except (json.JSONDecodeError, TypeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["rag_processor"] = "simple_rag"

    updated = Assistant(
        name=existing.name,
        description=existing.description,
        owner=existing.owner,
        api_callback=json.dumps(metadata),
        system_prompt=existing.system_prompt,
        prompt_template=existing.prompt_template,
        organization_id=existing.organization_id,
        pre_retrieval_endpoint="",
        post_retrieval_endpoint="",
        RAG_endpoint="",
        RAG_Top_k=existing.RAG_Top_k or DEFAULT_TOP_K,
        RAG_collections=str(kb_id),
    )
    return db.update_assistant(assistant_id, updated)
