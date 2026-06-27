"""Creator-Interface proxy for KG-RAG / semantic-graph endpoints.

Routes mount at ``/creator/knowledge-stores/{ks_id}/graph/...``. Each call
resolves the per-org KB Server URL/token through ``KnowledgeStoreClient``
and proxies to the new KB Server's ``/graph`` router.

Benchmark runs are no longer exposed through the UI — they live as
standalone scripts that hit the KB Server's ``/benchmarks`` router
directly (see ``memoria/run_*_bench.py``). The KB Server only exposes
the graph router when ``KG_RAG_ENABLED=true``; if the flag is off the
proxy will return 503. The frontend uses ``/graph/status`` to gate its
UI accordingly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from lamb.auth_context import AuthContext, get_auth_context
from lamb.database_manager import LambDatabaseManager

from .knowledge_store_client import KnowledgeStoreClient

logger = logging.getLogger(__name__)

router = APIRouter()
_client = KnowledgeStoreClient()
_db = LambDatabaseManager()


def _assert_ks_access(ks_id: str, auth: AuthContext) -> Dict[str, Any]:
    """Load the Knowledge Store row and check the caller can use it.

    Mirrors the access checks in ``knowledge_store_router`` — owner or a
    shared store within the same org. Raises 404/403 on failure.
    """
    ks = _db.get_knowledge_store(ks_id)
    if not ks:
        raise HTTPException(status_code=404, detail="Knowledge Store not found")
    if (
        ks.get("owner_user_id") != auth.user.get("id")
        and not ks.get("is_shared")
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    if ks.get("organization_id") != auth.organization.get("id"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return ks


# ----------------------------------------------------------------------
# Status / migration
# ----------------------------------------------------------------------


@router.get("/graph/status")
async def get_graph_status(auth: AuthContext = Depends(get_auth_context)):
    """Get KG-RAG feature flag + Neo4j availability from the KB Server.

    The frontend reads this on the Knowledge Stores page so it knows
    whether to show Graph / Benchmark tabs at all.
    """
    return await _client.get_graph_status(creator_user=auth.user)


class MigrateRequest(BaseModel):
    openai_api_key: str = Field(
        default="",
        description=(
            "Per-request OpenAI key for concept extraction. Preferred over "
            "the KB server's permanent KG_RAG_OPENAI_API_KEY."
        ),
    )


@router.post("/{ks_id}/graph/migrate")
async def migrate_knowledge_store_to_graph(
    ks_id: str,
    body: MigrateRequest = Body(default_factory=MigrateRequest),
    auth: AuthContext = Depends(get_auth_context),
):
    """Run KG-RAG migration for an existing Knowledge Store.

    Resolves the OpenAI key from (1) the explicit per-request body,
    (2) the org's ``providers.openai.api_key``, or fails to use the KB
    server-level fallback if both are empty.
    """
    _assert_ks_access(ks_id, auth)

    api_key = (body.openai_api_key or "").strip()
    if not api_key:
        from lamb.completions.org_config_resolver import OrganizationConfigResolver
        resolver = OrganizationConfigResolver(auth.user.get("email"))
        try:
            api_key = resolver.get_provider_api_key("openai") or ""
        except Exception:  # noqa: BLE001 — org config may be missing
            api_key = ""

    return await _client.migrate_collection_to_graph(
        knowledge_store_id=ks_id,
        openai_api_key=api_key,
        creator_user=auth.user,
    )


# ----------------------------------------------------------------------
# Read endpoints
# ----------------------------------------------------------------------


@router.get("/{ks_id}/graph/snapshot")
async def get_graph_snapshot(
    ks_id: str,
    concept: Optional[str] = Query(default=None),
    document_id: Optional[str] = Query(default=None),
    chunk_id: Optional[str] = Query(default=None),
    filename: Optional[str] = Query(default=None),
    include_chunks: bool = Query(default=True),
    limit: int = Query(default=60, ge=1, le=10000),
    auth: AuthContext = Depends(get_auth_context),
):
    _assert_ks_access(ks_id, auth)
    params = {
        "include_chunks": str(include_chunks).lower(),
        "limit": limit,
    }
    if concept:
        params["concept"] = concept
    if document_id:
        params["document_id"] = document_id
    if chunk_id:
        params["chunk_id"] = chunk_id
    if filename:
        params["filename"] = filename
    return await _client.get_graph_snapshot(
        knowledge_store_id=ks_id, params=params, creator_user=auth.user,
    )


@router.get("/{ks_id}/graph/changes")
async def list_graph_changes(
    ks_id: str,
    concept: Optional[str] = Query(default=None),
    document_id: Optional[str] = Query(default=None),
    filename: Optional[str] = Query(default=None),
    operation: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    auth: AuthContext = Depends(get_auth_context),
):
    _assert_ks_access(ks_id, auth)
    params: Dict[str, Any] = {"limit": limit}
    if concept:
        params["concept"] = concept
    if document_id:
        params["document_id"] = document_id
    if filename:
        params["filename"] = filename
    if operation:
        params["operation"] = operation
    return await _client.list_graph_changes(
        knowledge_store_id=ks_id, params=params, creator_user=auth.user,
    )


# ----------------------------------------------------------------------
# Curation
# ----------------------------------------------------------------------


class ConceptRenameRequest(BaseModel):
    new_name: str = Field(..., min_length=1)
    actor: str = "graph-curation-api"
    reason: str = ""


class ConceptMergeRequest(BaseModel):
    source_names: List[str] = Field(..., min_length=1)
    target_name: str = Field(..., min_length=1)
    actor: str = "graph-curation-api"
    reason: str = ""


class ConceptCurationRequest(BaseModel):
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    verification_state: Optional[str] = None
    actor: str = "graph-curation-api"
    reason: str = ""


class RelationshipEditRequest(BaseModel):
    source_concept: str
    target_concept: str
    relation: str
    new_relation: Optional[str] = None
    weight: Optional[float] = None
    description: Optional[str] = None
    evidence: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    verification_state: Optional[str] = None
    actor: str = "graph-curation-api"
    reason: str = ""


class RelationshipCurationRequest(BaseModel):
    source_concept: str
    target_concept: str
    relation: str
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    verification_state: Optional[str] = None
    actor: str = "graph-curation-api"
    reason: str = ""


@router.patch("/{ks_id}/graph/concepts/{concept}/rename")
async def rename_concept(
    ks_id: str,
    concept: str,
    body: ConceptRenameRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    _assert_ks_access(ks_id, auth)
    return await _client.graph_concept_rename(
        knowledge_store_id=ks_id, concept=concept,
        body=body.model_dump(), creator_user=auth.user,
    )


@router.post("/{ks_id}/graph/concepts/merge")
async def merge_concepts(
    ks_id: str,
    body: ConceptMergeRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    _assert_ks_access(ks_id, auth)
    return await _client.graph_concepts_merge(
        knowledge_store_id=ks_id, body=body.model_dump(),
        creator_user=auth.user,
    )


@router.patch("/{ks_id}/graph/concepts/{concept}/curation")
async def curate_concept(
    ks_id: str,
    concept: str,
    body: ConceptCurationRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    _assert_ks_access(ks_id, auth)
    return await _client.graph_concept_curation(
        knowledge_store_id=ks_id, concept=concept,
        body=body.model_dump(), creator_user=auth.user,
    )


@router.patch("/{ks_id}/graph/relationships")
async def edit_relationship(
    ks_id: str,
    body: RelationshipEditRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    _assert_ks_access(ks_id, auth)
    return await _client.graph_relationship_edit(
        knowledge_store_id=ks_id, body=body.model_dump(),
        creator_user=auth.user,
    )


@router.patch("/{ks_id}/graph/relationships/curation")
async def curate_relationship(
    ks_id: str,
    body: RelationshipCurationRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    _assert_ks_access(ks_id, auth)
    return await _client.graph_relationship_curation(
        knowledge_store_id=ks_id, body=body.model_dump(),
        creator_user=auth.user,
    )




