"""Creator Interface routes for the new KB Server (Knowledge Stores).

Mounted at ``/creator/knowledge-stores``. Distinct from the stable
``/creator/knowledgebases`` surface which keeps serving the legacy KB Server
on port 9090. Both coexist (issue #334 NFR-1).

Standard pattern per endpoint: authenticate -> check ACL -> resolve org
config -> call KB Server / Library Manager -> update LAMB DB -> audit ->
response.

A Knowledge Store is populated exclusively by linking Library items
(decision D3 of the plan) — it is the only ingestion path. The KB Server
itself accepts JSON with text + permalinks, never files.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from lamb.auth_context import AuthContext, get_auth_context
from lamb.database_manager import LambDatabaseManager

from .knowledge_store_client import KnowledgeStoreClient, KnowledgeStoreUnavailable
from .library_manager_client import LibraryManagerClient

logger = logging.getLogger(__name__)


router = APIRouter()
_client = KnowledgeStoreClient()
_library_client = LibraryManagerClient()
_db = LambDatabaseManager()


# ----------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------


class KnowledgeStoreCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    chunking_strategy: str
    chunking_params: Optional[Dict[str, Any]] = None
    embedding_vendor: str
    embedding_model: str
    embedding_endpoint: Optional[str] = None
    # Extra knobs declared by the embedding vendor's plugin schema beyond
    # ``model``/``api_endpoint``/``api_key`` (those have bespoke widgets).
    # Empty for today's openai/ollama/local vendors; future vendors that
    # declare extras pick them up automatically via PluginParamFields.
    embedding_params: Optional[Dict[str, Any]] = None
    vector_db_backend: str
    # Extra knobs declared by the vector-DB backend's plugin schema.
    # Empty for today's chromadb/qdrant backends.
    vector_db_params: Optional[Dict[str, Any]] = None


class KnowledgeStoreUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    # Chunking strategy / embedding / vector DB stay locked at creation; only
    # the strategy's PARAMETERS can be edited, and the change applies only to
    # content ingested after the update (existing chunks keep their original
    # parameters).
    chunking_params: Optional[Dict[str, Any]] = None


class KnowledgeStoreShareToggle(BaseModel):
    is_shared: bool


class AddContentRequest(BaseModel):
    library_id: str
    item_ids: List[str] = Field(..., min_length=1)


class QueryRequest(BaseModel):
    query_text: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _audit(auth: AuthContext, action: str, target_type: str, target_id: str,
           details: dict = None):
    """Write an audit log entry for the current user's action."""
    _db.write_audit_log(
        organization_id=auth.organization.get("id"),
        actor_user_id=auth.user.get("id"),
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


def _build_permalinks(org_id: int, library_id: str, item_id: str,
                      pages_count: int = 0,
                      original_filename: str = None,
                      source_url: str = None) -> Dict[str, Any]:
    """Build the permalink set sent to the KB Server for a library item.

    ``full_markdown`` always points at LAMB's /docs proxy (ACL-enforced).
    ``original`` points at the proxied original file for file imports, or the
    external source URL for web/YouTube imports.
    """
    base = f"/docs/{org_id}/{library_id}/{item_id}"
    permalinks: Dict[str, Any] = {
        "full_markdown": f"{base}/content",
    }
    if original_filename:
        permalinks["original"] = f"{base}/original/{original_filename}"
    elif source_url:
        permalinks["original"] = source_url
    if pages_count:
        permalinks["pages"] = [f"{base}/content/pages/{i + 1}" for i in range(pages_count)]
    return permalinks


def _flatten_pages(pages_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert Library Manager's pages list into KB Server PageInput shape."""
    pages = []
    for p in pages_payload.get("pages", []):
        if isinstance(p, dict):
            pages.append({
                "page_number": p.get("page_number") or p.get("number") or 0,
                "text": p.get("text") or p.get("markdown") or "",
            })
    return pages


# ======================================================================
# Static routes — registered before /{ks_id} (ADR-KS-11)
# ======================================================================


@router.get("/options")
async def get_options(auth: AuthContext = Depends(get_auth_context)):
    """Return the org's allowed chunking strategies, embedding vendors / models,
    and vector DB backends so the UI can render the create form.

    If the KB Server is unreachable or not configured, returns a structured
    503 ``{"error": "knowledge_store_unavailable", "detail": "..."}`` so the
    frontend can render an actionable retry state. There is no hardcoded
    fallback catalogue — the zero-touch plugin thesis (issue #334) requires
    that the live registries on the KB Server are the single source of
    truth for available plugins.
    """
    try:
        return await _client.get_org_options(creator_user=auth.user)
    except KnowledgeStoreUnavailable as exc:
        logger.warning(f"Knowledge Store unavailable when serving /options: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "knowledge_store_unavailable",
                "detail": str(exc),
            },
        )


# ======================================================================
# Knowledge Store CRUD
# ======================================================================


@router.post("")
async def create_knowledge_store(
    body: KnowledgeStoreCreate,
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new Knowledge Store.

    Creates the LAMB row as ``status='provisional'`` first, then calls the
    KB Server. Promotes to ``'active'`` on success; rolls back the LAMB row
    on failure so partial-failure entries never appear in user listings.
    """
    error = _client.validate_against_allow_list(
        creator_user=auth.user,
        chunking_strategy=body.chunking_strategy,
        embedding_vendor=body.embedding_vendor,
        embedding_model=body.embedding_model,
        vector_db_backend=body.vector_db_backend,
    )
    if error:
        raise HTTPException(status_code=400, detail=error)

    knowledge_store_id = str(uuid.uuid4())
    org_id = auth.organization.get("id")

    # Auto-fill embedding_endpoint from org config if the caller didn't
    # specify one. Lets Knowledge Store create work out-of-the-box for orgs
    # that have configured ``providers.{vendor}.endpoint`` (or base_url).
    resolved_endpoint = body.embedding_endpoint
    if not resolved_endpoint:
        from lamb.completions.org_config_resolver import OrganizationConfigResolver
        resolver = OrganizationConfigResolver(auth.user.get("email"))
        try:
            resolved_endpoint = resolver.get_provider_endpoint(body.embedding_vendor) or ""
        except ValueError:
            resolved_endpoint = ""

    inserted = _db.create_knowledge_store(
        knowledge_store_id=knowledge_store_id,
        name=body.name,
        owner_user_id=auth.user.get("id"),
        organization_id=org_id,
        chunking_strategy=body.chunking_strategy,
        embedding_vendor=body.embedding_vendor,
        embedding_model=body.embedding_model,
        vector_db_backend=body.vector_db_backend,
        description=body.description,
        chunking_params=body.chunking_params,
        embedding_endpoint=resolved_endpoint,
        status="provisional",
    )
    if not inserted:
        raise HTTPException(
            status_code=409,
            detail="Knowledge Store name already taken in this organization.",
        )

    try:
        await _client.create_collection(
            knowledge_store_id=knowledge_store_id,
            organization_id=org_id,
            name=body.name,
            chunking_strategy=body.chunking_strategy,
            embedding_vendor=body.embedding_vendor,
            embedding_model=body.embedding_model,
            vector_db_backend=body.vector_db_backend,
            description=body.description,
            chunking_params=body.chunking_params,
            embedding_endpoint=resolved_endpoint or "",
            embedding_params=body.embedding_params,
            vector_db_params=body.vector_db_params,
            creator_user=auth.user,
        )
    except Exception as e:
        _db.delete_knowledge_store(knowledge_store_id)
        raise HTTPException(
            status_code=502,
            detail=f"Knowledge Store server error: {e}",
        )

    _db.update_knowledge_store_status(knowledge_store_id, "active")
    _audit(auth, "knowledge_store.create", "knowledge_store", knowledge_store_id, {
        "name": body.name,
        "chunking_strategy": body.chunking_strategy,
        "embedding_vendor": body.embedding_vendor,
        "embedding_model": body.embedding_model,
        "vector_db_backend": body.vector_db_backend,
    })
    return _db.get_knowledge_store(knowledge_store_id)


@router.get("")
async def list_knowledge_stores(auth: AuthContext = Depends(get_auth_context)):
    """List Knowledge Stores accessible to the current user (owned + shared)."""
    return {
        "knowledge_stores": _db.get_accessible_knowledge_stores(
            user_id=auth.user.get("id"),
            organization_id=auth.organization.get("id"),
        )
    }


@router.get("/{ks_id}")
async def get_knowledge_store(
    ks_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Get details for a Knowledge Store, including linked content."""
    auth.require_knowledge_store_access(ks_id, level="any")
    entry = _db.get_knowledge_store(ks_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge Store not found")

    try:
        server_data = await _client.get_collection(ks_id, creator_user=auth.user)
        entry["server_status"] = server_data.get("status")
        entry["document_count"] = server_data.get("document_count", 0)
        entry["chunk_count"] = server_data.get("chunk_count", 0)
    except Exception as e:
        logger.warning(f"Could not fetch collection metadata from KB Server for {ks_id}: {e}")
        entry["server_status"] = None
        entry["document_count"] = None
        entry["chunk_count"] = None

    entry["content"] = _db.get_kb_content_links_for_ks(ks_id)
    entry["is_owner"] = entry.get("owner_user_id") == auth.user.get("id")
    return entry


@router.put("/{ks_id}")
async def update_knowledge_store(
    ks_id: str,
    body: KnowledgeStoreUpdate,
    auth: AuthContext = Depends(get_auth_context),
):
    """Update mutable fields. Strategy/embedding/vector-DB stay locked
    (ADR-KS-5); chunking parameters CAN be edited but apply only to new
    ingestions."""
    auth.require_knowledge_store_access(ks_id, level="owner")
    if body.name is None and body.description is None and body.chunking_params is None:
        raise HTTPException(status_code=400, detail="Nothing to update.")

    try:
        await _client.update_collection(
            knowledge_store_id=ks_id,
            name=body.name,
            description=body.description,
            chunking_params=body.chunking_params,
            creator_user=auth.user,
        )
    except HTTPException as e:
        if e.status_code == 404:
            pass
        else:
            raise

    success = _db.update_knowledge_store(
        ks_id,
        name=body.name,
        description=body.description,
        chunking_params=body.chunking_params,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Knowledge Store not found")

    _audit(auth, "knowledge_store.update", "knowledge_store", ks_id)
    return _db.get_knowledge_store(ks_id)


@router.delete("/{ks_id}")
async def delete_knowledge_store(
    ks_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete a Knowledge Store and all its vectors.

    Calls the KB Server first; on success or 404, deletes the LAMB row
    (cascades to ``kb_content_links``). 5xx from the KB Server preserves
    the LAMB row so the user can retry (Marc's #336 review #1).
    """
    auth.require_knowledge_store_access(ks_id, level="owner")

    try:
        await _client.delete_collection(ks_id, creator_user=auth.user)
    except HTTPException as e:
        if e.status_code == 404:
            pass
        elif e.status_code >= 500:
            raise HTTPException(
                status_code=502,
                detail=f"Knowledge Store server error during delete: {e.detail}",
            )
        else:
            raise

    _db.delete_knowledge_store(ks_id)
    _audit(auth, "knowledge_store.delete", "knowledge_store", ks_id)
    return {"message": f"Knowledge Store {ks_id} deleted."}


@router.put("/{ks_id}/share")
async def toggle_sharing(
    ks_id: str,
    body: KnowledgeStoreShareToggle,
    auth: AuthContext = Depends(get_auth_context),
):
    """Enable or disable organization-wide sharing."""
    auth.require_knowledge_store_access(ks_id, level="owner")
    _db.toggle_knowledge_store_sharing(ks_id, body.is_shared)
    action = "knowledge_store.share" if body.is_shared else "knowledge_store.unshare"
    _audit(auth, action, "knowledge_store", ks_id)
    state = "shared with organization" if body.is_shared else "private"
    return {
        "knowledge_store_id": ks_id,
        "is_shared": body.is_shared,
        "message": f"Knowledge Store is now {state}.",
    }


# ======================================================================
# Content ingestion (library item -> KS)
# ======================================================================


@router.get("/{ks_id}/content")
async def list_ks_content(
    ks_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Return a lightweight list of content links for a Knowledge Store.

    Returns only ``library_item_id`` and ``status`` fields — no KB Server
    call — so the frontend can quickly determine which items are already
    linked before the user submits a new ingestion request.
    """
    auth.require_knowledge_store_access(ks_id, level="any")
    links = _db.get_kb_content_links_for_ks(ks_id)
    return {
        "ks_id": ks_id,
        "items": [
            {"library_item_id": lnk["library_item_id"], "status": lnk["status"]}
            for lnk in links
        ],
    }


@router.post("/{ks_id}/content")
async def add_content(
    ks_id: str,
    body: AddContentRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    """Ingest one or more library items into a Knowledge Store.

    For each item: validates ACL on both KS and library, fetches markdown
    + metadata from the Library Manager, builds a permalink set against
    LAMB's /docs proxy, posts the batch to the KB Server with the org's
    embedding API key, and registers ``kb_content_links`` rows.
    """
    auth.require_knowledge_store_access(ks_id, level="any")
    auth.require_library_access(body.library_id, level="any")

    ks_entry = _db.get_knowledge_store(ks_id)
    if not ks_entry:
        raise HTTPException(status_code=404, detail="Knowledge Store not found")

    library_entry = _db.get_library(body.library_id)
    if not library_entry:
        raise HTTPException(status_code=404, detail="Library not found")
    if library_entry["organization_id"] != ks_entry["organization_id"]:
        raise HTTPException(
            status_code=403,
            detail="Library and Knowledge Store must belong to the same organization.",
        )

    org_id = ks_entry["organization_id"]
    embedding_api_key = _client.resolve_embedding_api_key(
        creator_user=auth.user,
        vendor=ks_entry["embedding_vendor"],
    )

    documents: List[Dict[str, Any]] = []
    for item_id in body.item_ids:
        existing = _db.get_kb_content_link(ks_id, item_id)
        if existing and existing.get("status") in ("pending", "processing", "ready"):
            logger.info(
                f"Skipping item {item_id}: already linked to KS {ks_id} (status={existing['status']})"
            )
            continue

        try:
            item_meta = await _library_client.get_item(
                body.library_id, item_id, creator_user=auth.user,
            )
        except HTTPException as e:
            logger.warning(f"Could not fetch item {item_id} from Library Manager: {e.detail}")
            raise HTTPException(
                status_code=400,
                detail=f"Library item {item_id} not available: {e.detail}",
            )

        item_status = item_meta.get("status") or "ready"
        if item_status != "ready":
            raise HTTPException(
                status_code=409,
                detail=f"Library item {item_id} is not ready (status={item_status}).",
            )

        try:
            content_response = await _library_client.proxy_content(
                library_id=body.library_id,
                item_id=item_id,
                subpath="content?format=markdown",
                creator_user=auth.user,
            )
            text = content_response.text if hasattr(content_response, "text") else ""
        except HTTPException as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not fetch content for item {item_id}: {e.detail}",
            )

        if not text:
            raise HTTPException(
                status_code=400,
                detail=f"Library item {item_id} has empty content.",
            )

        # Page count comes from the item's own metadata (already fetched).
        # The legacy ``/content/pages`` filename-list endpoint is shadowed
        # by the capability handler (which returns an array of
        # ``{page, markdown}`` rows), so don't re-fetch — read the count
        # the importer stored on the item record.
        try:
            pages_count = int(item_meta.get("page_count") or 0)
        except (TypeError, ValueError):
            pages_count = 0

        title = item_meta.get("title") or item_meta.get("original_filename") or item_id
        documents.append({
            "source_item_id": item_id,
            "title": title,
            "text": text,
            "permalinks": _build_permalinks(
                org_id, body.library_id, item_id, pages_count,
                original_filename=item_meta.get("original_filename"),
                source_url=item_meta.get("source_url"),
            ),
            "pages": [],
            "extra_metadata": {
                "library_id": body.library_id,
                "library_name": library_entry.get("name", ""),
            },
        })

    if not documents:
        return {
            "job_id": None,
            "status": "noop",
            "message": "No new items to ingest (all already linked).",
            "links": [],
        }

    try:
        result = await _client.add_content(
            knowledge_store_id=ks_id,
            documents=documents,
            embedding_api_key=embedding_api_key,
            embedding_api_endpoint=ks_entry.get("embedding_endpoint") or "",
            creator_user=auth.user,
        )
    except HTTPException as e:
        raise HTTPException(
            status_code=502,
            detail=f"Knowledge Store ingestion failed: {e.detail}",
        )

    job_id = result.get("job_id")
    links = []
    for doc in documents:
        link_id = _db.register_kb_content_link(
            knowledge_store_id=ks_id,
            library_id=body.library_id,
            library_item_id=doc["source_item_id"],
            organization_id=org_id,
            created_by_user_id=auth.user.get("id"),
            kb_job_id=job_id,
            status="processing",
        )
        if link_id:
            links.append({
                "id": link_id,
                "library_item_id": doc["source_item_id"],
                "kb_job_id": job_id,
                "status": "processing",
            })
        _audit(auth, "knowledge_store.add_content", "knowledge_store", ks_id, {
            "library_id": body.library_id,
            "library_item_id": doc["source_item_id"],
            "kb_job_id": job_id,
        })

    return {
        "job_id": job_id,
        "status": result.get("status", "processing"),
        "documents_total": result.get("documents_total", len(documents)),
        "links": links,
    }


@router.get("/{ks_id}/content")
async def list_content(
    ks_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """List linked library items for a Knowledge Store."""
    auth.require_knowledge_store_access(ks_id, level="any")
    return {"content": _db.get_kb_content_links_for_ks(ks_id)}


@router.get("/{ks_id}/content/{library_item_id}")
async def get_content_link(
    ks_id: str,
    library_item_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a single content link's status; sync from KB Server if processing."""
    auth.require_knowledge_store_access(ks_id, level="any")
    link = _db.get_kb_content_link(ks_id, library_item_id)
    if not link:
        raise HTTPException(status_code=404, detail="Content link not found")

    if link.get("status") in ("pending", "processing") and link.get("kb_job_id"):
        try:
            job = await _client.get_job_status(link["kb_job_id"], creator_user=auth.user)
            new_status_map = {
                "pending": "pending",
                "processing": "processing",
                "completed": "ready",
                "failed": "failed",
            }
            mapped = new_status_map.get(job.get("status"), link["status"])
            _db.update_kb_content_link_status(
                link_id=link["id"],
                status=mapped,
                chunks_created=job.get("chunks_created"),
                error_message=job.get("error_message"),
            )
            link = _db.get_kb_content_link(ks_id, library_item_id)
        except Exception as e:
            logger.warning(
                f"Could not poll KB job {link.get('kb_job_id')}: {e}"
            )

    return link


@router.delete("/{ks_id}/content/{library_item_id}")
async def remove_content(
    ks_id: str,
    library_item_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Remove a library item's vectors from a Knowledge Store.

    Does not affect the library item itself — only its presence in this KS.

    If the link is still ``pending`` / ``processing``, the in-flight
    ingestion job is cancelled first so the worker stops embedding documents
    the user is discarding. The vector-delete and job-cancel calls are
    best-effort: the LAMB-side link row is the source of truth from the
    user's perspective, so we always tear it down and return success even
    if the downstream KB Server is unreachable or the source had not yet
    produced any vectors. Without this, deleting a still-processing item
    would 502 because ``delete_by_source`` can race with the worker's
    writes and the user would be stuck with a ghost item.
    """
    auth.require_knowledge_store_access(ks_id, level="owner")
    link = _db.get_kb_content_link(ks_id, library_item_id)
    if not link:
        raise HTTPException(status_code=404, detail="Content link not found")

    in_flight = link.get("status") in ("pending", "processing")
    job_id = link.get("kb_job_id")
    if in_flight and job_id:
        try:
            await _client.cancel_job(job_id, creator_user=auth.user)
        except Exception as exc:
            logger.warning(
                f"Could not cancel KB job {job_id} for content link "
                f"{library_item_id}: {exc}"
            )

    try:
        await _client.delete_content_by_source(
            knowledge_store_id=ks_id,
            source_item_id=library_item_id,
            creator_user=auth.user,
        )
    except HTTPException as e:
        if e.status_code == 404 or e.status_code >= 500:
            logger.warning(
                f"Best-effort delete of vectors for {library_item_id} in "
                f"{ks_id} returned {e.status_code}; tearing the link down "
                f"anyway: {e.detail}"
            )
        else:
            raise

    _db.delete_kb_content_link(ks_id, library_item_id)
    _audit(auth, "knowledge_store.remove_content", "knowledge_store", ks_id, {
        "library_item_id": library_item_id,
        "cancelled_job_id": job_id if in_flight else None,
    })
    return {"message": "Content removed from Knowledge Store."}


# ======================================================================
# Query
# ======================================================================


@router.post("/{ks_id}/query")
async def query_knowledge_store(
    ks_id: str,
    body: QueryRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    """Run a similarity search; returns chunks with permalink-bearing metadata."""
    auth.require_knowledge_store_access(ks_id, level="any")
    ks_entry = _db.get_knowledge_store(ks_id)
    if not ks_entry:
        raise HTTPException(status_code=404, detail="Knowledge Store not found")

    embedding_api_key = _client.resolve_embedding_api_key(
        creator_user=auth.user,
        vendor=ks_entry["embedding_vendor"],
    )

    return await _client.query(
        knowledge_store_id=ks_id,
        query_text=body.query_text,
        top_k=body.top_k,
        embedding_api_key=embedding_api_key,
        embedding_api_endpoint=ks_entry.get("embedding_endpoint") or "",
        creator_user=auth.user,
    )


# ======================================================================
# Job polling
# ======================================================================


@router.get("/{ks_id}/jobs/{job_id}")
async def get_job_status(
    ks_id: str,
    job_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Proxy KB Server job status, syncing affected ``kb_content_links`` rows.

    Used when a single batch ingested multiple items and the caller wants
    aggregate progress.
    """
    auth.require_knowledge_store_access(ks_id, level="any")
    job = await _client.get_job_status(job_id, creator_user=auth.user)

    new_status_map = {
        "pending": "pending",
        "processing": "processing",
        "completed": "ready",
        "failed": "failed",
    }
    mapped = new_status_map.get(job.get("status"))
    if mapped:
        for link in _db.get_kb_content_links_for_ks(ks_id):
            if link.get("kb_job_id") == job_id and link.get("status") != mapped:
                _db.update_kb_content_link_status(
                    link_id=link["id"],
                    status=mapped,
                    chunks_created=job.get("chunks_created"),
                    error_message=job.get("error_message"),
                )

    return job
