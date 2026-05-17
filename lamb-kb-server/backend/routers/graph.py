"""KG-RAG graph traceability endpoints (new KB server architecture).

These endpoints are only mounted when ``KG_RAG_ENABLED=true`` (see
``main.py``). Per-request OpenAI credentials are accepted via the
``X-OpenAI-Api-Key`` header for migration jobs that need to extract
concepts at ingest time. Falls back to the ``KG_RAG_OPENAI_API_KEY``
env var when the header is absent (ADR-4 spirit: prefer per-request
credentials but allow a server-level fallback for migration).
"""

from __future__ import annotations

from typing import Any

from database.connection import get_session
from database.models import Collection
from dependencies import verify_token
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from schemas.graph import (
    GraphAuditRequest,
    GraphAuditResponse,
    GraphChangeDetail,
    GraphChangeEvent,
    GraphConceptCurationRequest,
    GraphConceptMergeRequest,
    GraphConceptRenameRequest,
    GraphManualOperationResponse,
    GraphRelationshipCurationRequest,
    GraphRelationshipEditRequest,
    GraphRevertRequest,
    GraphRevertResponse,
    GraphSnapshotResponse,
)
from services.graph_store import get_graph_store
from sqlalchemy.orm import Session

router = APIRouter(prefix="/graph", tags=["Graph Traceability"])


def _get_collection_or_404(db: Session, collection_id: str) -> Collection:
    collection = (
        db.query(Collection).filter(Collection.id == collection_id).first()
    )
    if not collection:
        raise HTTPException(
            status_code=404, detail=f"Collection {collection_id} not found"
        )
    return collection


def _graph_store_or_503():
    graph_store = get_graph_store()
    if not graph_store.is_configured():
        raise HTTPException(status_code=503, detail="KG-RAG Neo4j is not configured")
    if not graph_store.is_available():
        raise HTTPException(status_code=503, detail="KG-RAG Neo4j is not available")
    return graph_store


def _graph_status_payload() -> dict[str, Any]:
    import config as config_module

    kg_config = config_module.get_kg_rag_config()
    graph_store = get_graph_store()
    neo4j_configured = graph_store.is_configured()
    neo4j_available = False
    if neo4j_configured:
        try:
            neo4j_available = graph_store.is_available()
        except Exception:
            neo4j_available = False

    return {
        "enabled": bool(kg_config.get("enabled")),
        "index_on_ingest": bool(kg_config.get("index_on_ingest", True)),
        "neo4j_configured": neo4j_configured,
        "neo4j_available": neo4j_available,
    }


def _collection_dict(collection: Collection) -> dict[str, Any]:
    """Adapt a new Collection ORM row to the legacy ``{id, owner, ...}``
    dict shape that graph_store internals still expect."""
    return {
        "id": collection.id,
        "name": collection.name,
        "organization_id": collection.organization_id,
        "owner": collection.organization_id,
    }


@router.get("/status", summary="Get Graph RAG feature availability")
async def get_graph_status(token: str = Depends(verify_token)):
    return _graph_status_payload()


@router.post(
    "/collections/{collection_id}/migrate",
    summary="Migrate existing collection chunks into Graph RAG",
)
async def migrate_collection_to_graph(
    collection_id: str,
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
    x_openai_api_key: str | None = Header(default=None),
):
    """Re-index a collection's existing vectors into Neo4j.

    Reads chunks from the vector backend, runs LLM concept extraction, and
    writes the resulting graph into Neo4j. Sets ``graph_enabled=True`` on
    success.
    """
    graph_status = _graph_status_payload()
    if not graph_status["enabled"]:
        raise HTTPException(status_code=503, detail="KG-RAG is disabled")

    collection = _get_collection_or_404(db, collection_id)
    _graph_store_or_503()

    # Pull chunks from ChromaDB (the only backend with a stable get-by-id
    # path right now). Qdrant migration is a TODO.
    if collection.vector_db_backend != "chromadb":
        raise HTTPException(
            status_code=400,
            detail=(
                "Graph migration currently only supports the chromadb vector "
                f"backend (collection uses '{collection.vector_db_backend}')."
            ),
        )

    from plugins.vector_db import chromadb_backend as _chroma_mod

    client = _chroma_mod._get_client(collection.storage_path)
    try:
        chroma_collection = client.get_collection(
            name=collection.backend_collection_id or collection.id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"ChromaDB collection for {collection.id} not found",
        ) from exc

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    offset = 0
    batch_size = 500

    while True:
        result = chroma_collection.get(
            include=["documents", "metadatas"],
            limit=batch_size,
            offset=offset,
        )
        result_ids = result.get("ids") or []
        documents = result.get("documents") or []
        result_metadatas = result.get("metadatas") or []
        if not result_ids:
            break

        for i, chunk_id in enumerate(result_ids):
            text = documents[i] if i < len(documents) else None
            if not text:
                continue
            metadata = (
                result_metadatas[i]
                if i < len(result_metadatas)
                and isinstance(result_metadatas[i], dict)
                else {}
            )
            ids.append(chunk_id)
            texts.append(text)
            metadatas.append(metadata)

        offset += len(result_ids)

    if not ids:
        collection.graph_enabled = True
        db.commit()
        return {
            "status": "success",
            "collection_id": collection_id,
            "graph_enabled": True,
            "indexed": False,
            "chunks": 0,
            "reason": "no_chunks_found",
        }

    # Run LLM extraction + Neo4j indexing.
    from services.graph_indexing import index_chunks_for_collection

    indexed = index_chunks_for_collection(
        collection=collection,
        ids=ids,
        texts=texts,
        metadatas=metadatas,
        openai_api_key=x_openai_api_key,
    )

    collection.graph_enabled = True
    db.commit()
    return {
        "status": "success",
        "collection_id": collection_id,
        "graph_enabled": True,
        "chunks_seen": len(ids),
        **indexed,
    }


@router.get(
    "/collections/{collection_id}/snapshot",
    response_model=GraphSnapshotResponse,
    summary="Get graph snapshot for visualization",
)
async def get_graph_snapshot(
    collection_id: str,
    concept: str | None = Query(None),
    document_id: str | None = Query(None),
    chunk_id: str | None = Query(None),
    filename: str | None = Query(None),
    include_chunks: bool = Query(True),
    limit: int = Query(60, ge=1, le=200),
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    return graph_store.get_collection_graph(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        concept=concept,
        document_id=document_id,
        chunk_id=chunk_id,
        filename=filename,
        include_chunks=include_chunks,
        limit=limit,
    )


@router.get(
    "/collections/{collection_id}/changes",
    response_model=list[GraphChangeEvent],
    summary="List graph change history",
)
async def list_graph_changes(
    collection_id: str,
    concept: str | None = Query(None),
    relationship_source: str | None = Query(None),
    relationship_target: str | None = Query(None),
    relationship_relation: str | None = Query(None),
    document_id: str | None = Query(None),
    filename: str | None = Query(None),
    operation: str | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    return graph_store.list_changes(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        concept=concept,
        relationship_source=relationship_source,
        relationship_target=relationship_target,
        relationship_relation=relationship_relation,
        document_id=document_id,
        filename=filename,
        operation=operation,
        limit=limit,
    )


@router.get(
    "/collections/{collection_id}/changes/{event_id}",
    response_model=GraphChangeDetail,
    summary="Inspect a graph change event",
)
async def get_graph_change(
    collection_id: str,
    event_id: str,
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    change = graph_store.get_change(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        event_id=event_id,
    )
    if not change:
        raise HTTPException(
            status_code=404, detail=f"Graph change {event_id} not found"
        )
    return change


@router.get(
    "/collections/{collection_id}/concepts/{concept}/changes",
    response_model=list[GraphChangeEvent],
    summary="Inspect graph changes for a concept",
)
async def list_concept_changes(
    collection_id: str,
    concept: str,
    limit: int = Query(25, ge=1, le=200),
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    return graph_store.list_changes(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        concept=concept,
        limit=limit,
    )


@router.get(
    "/collections/{collection_id}/documents/{document_id}/changes",
    response_model=list[GraphChangeEvent],
    summary="Inspect graph changes for a document",
)
async def list_document_changes(
    collection_id: str,
    document_id: str,
    limit: int = Query(25, ge=1, le=200),
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    return graph_store.list_changes(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        document_id=document_id,
        limit=limit,
    )


@router.post(
    "/collections/{collection_id}/audit-trace",
    response_model=GraphAuditResponse,
    summary="Audit a KG-RAG graph retrieval trace",
)
async def audit_graph_trace(
    collection_id: str,
    request: GraphAuditRequest,
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    trace = graph_store.expand_from_chunks(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        seed_chunk_ids=request.seed_chunk_ids,
        depth=request.graph_depth,
        limit=request.limit,
    )
    return {
        "collection_id": collection_id,
        "seed_chunk_ids": request.seed_chunk_ids,
        "trace": trace,
    }


@router.post(
    "/collections/{collection_id}/changes/{event_id}/revert",
    response_model=GraphRevertResponse,
    summary="Revert a supported graph change",
)
async def revert_graph_change(
    collection_id: str,
    event_id: str,
    request: GraphRevertRequest,
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    result = graph_store.revert_change(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        event_id=event_id,
        actor=request.actor,
        reason=request.reason,
    )
    if not result.get("reverted") and result.get("reason") == "change_not_found":
        raise HTTPException(
            status_code=404, detail=f"Graph change {event_id} not found"
        )
    if not result.get("reverted"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.patch(
    "/collections/{collection_id}/concepts/{concept}/rename",
    response_model=GraphManualOperationResponse,
    summary="Rename a graph concept in a collection",
)
async def rename_graph_concept(
    collection_id: str,
    concept: str,
    request: GraphConceptRenameRequest,
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    result = graph_store.rename_concept(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        old_name=concept,
        new_name=request.new_name,
        actor=request.actor,
        reason=request.reason,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post(
    "/collections/{collection_id}/concepts/merge",
    response_model=GraphManualOperationResponse,
    summary="Merge graph concepts in a collection",
)
async def merge_graph_concepts(
    collection_id: str,
    request: GraphConceptMergeRequest,
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    result = graph_store.merge_concepts(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        source_names=request.source_names,
        target_name=request.target_name,
        actor=request.actor,
        reason=request.reason,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.patch(
    "/collections/{collection_id}/concepts/{concept}/curation",
    response_model=GraphManualOperationResponse,
    summary="Update graph concept curation metadata",
)
async def curate_graph_concept(
    collection_id: str,
    concept: str,
    request: GraphConceptCurationRequest,
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    result = graph_store.update_concept_curation(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        concept_name=concept,
        notes=request.notes,
        tags=request.tags,
        verification_state=request.verification_state,
        actor=request.actor,
        reason=request.reason,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.patch(
    "/collections/{collection_id}/relationships",
    response_model=GraphManualOperationResponse,
    summary="Edit graph relationship type or weight",
)
async def edit_graph_relationship(
    collection_id: str,
    request: GraphRelationshipEditRequest,
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    result = graph_store.edit_relationship(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        source_name=request.source_concept,
        target_name=request.target_concept,
        relation=request.relation,
        new_relation=request.new_relation,
        weight=request.weight,
        description=request.description,
        evidence=request.evidence,
        notes=request.notes,
        tags=request.tags,
        verification_state=request.verification_state,
        actor=request.actor,
        reason=request.reason,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.patch(
    "/collections/{collection_id}/relationships/curation",
    response_model=GraphManualOperationResponse,
    summary="Update graph relationship curation metadata",
)
async def curate_graph_relationship(
    collection_id: str,
    request: GraphRelationshipCurationRequest,
    token: str = Depends(verify_token),
    db: Session = Depends(get_session),
):
    collection = _get_collection_or_404(db, collection_id)
    graph_store = _graph_store_or_503()
    result = graph_store.edit_relationship(
        collection_id=collection_id,
        org_id=str(collection.organization_id),
        source_name=request.source_concept,
        target_name=request.target_concept,
        relation=request.relation,
        notes=request.notes,
        tags=request.tags,
        verification_state=request.verification_state,
        actor=request.actor,
        reason=request.reason,
        operation="manual_curate_relationship",
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result
