"""Shared helper that runs LLM concept extraction and writes graph data.

Used by:

* the ingestion path (``services/ingestion_service.py``) after Chroma
  insertions complete, when the collection has ``graph_enabled=true``.
* the migration endpoint (``routers/graph.py`` ``/migrate``) when an
  existing collection is opted into Graph RAG.

The function fails *open* rather than rolling back vector ingestion: if
the LLM call or Neo4j write fails, vector retrieval still works — we
just don't get the graph augmentation. Returned dict contains ``error``
when applicable so callers can surface it.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from database.models import Collection
from services.concept_extraction import ConceptExtractor, TextChunk

logger = logging.getLogger(__name__)


def _build_chunks(
    ids: list[str],
    texts: list[str],
    metadatas: list[dict[str, Any]],
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for i, chunk_id in enumerate(ids):
        if not chunk_id or i >= len(texts):
            continue
        text = texts[i] or ""
        if not text.strip():
            continue
        metadata = metadatas[i] if i < len(metadatas) else {}
        parent_text = ""
        if isinstance(metadata, dict):
            parent_text = str(metadata.get("parent_text") or "")
        chunks.append(
            TextChunk(
                chunk_id=str(chunk_id),
                text=text,
                parent_text=parent_text or text,
                metadata=dict(metadata or {}),
            )
        )
    return chunks


def index_chunks_for_collection(
    *,
    collection: Collection,
    ids: list[str],
    texts: list[str],
    metadatas: list[dict[str, Any]],
    openai_api_key: str | None = None,
    file_id: int | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Run extraction + Neo4j write for one batch of chunks.

    Args:
        collection: ORM row, used for id + organization_id.
        ids: Chunk IDs (must match what's in Chroma so KG-RAG expansion
            can look them back up).
        texts: Chunk text in the same order as ``ids``.
        metadatas: Chunk metadata in the same order. The chunk's
            ``permalink`` (when present) is preserved on the graph node.
        openai_api_key: Per-request key. Falls back to
            ``KG_RAG_OPENAI_API_KEY`` env when omitted.
        file_id: Optional integer file registry ID (kept for parity with
            the legacy graph schema; defaults to 0 in the new arch).
        filename: Optional source filename. Falls back to the first chunk
            metadata's ``filename`` / ``source_label`` / ``title``.

    Returns:
        ``{"indexed": bool, "chunks": int, "extraction_ms": float,
        "graph_ms": float, "error": str | None}``.
    """
    import config as config_module

    kg_config = config_module.get_kg_rag_config()
    if not kg_config.get("enabled"):
        return {"indexed": False, "chunks": 0, "reason": "kg_rag_disabled"}

    chunks = _build_chunks(ids, texts, metadatas)
    if not chunks:
        return {"indexed": False, "chunks": 0, "reason": "no_chunks"}

    # Resolve the extraction vendor/model/endpoint from the collection
    # (locked at creation), falling back to server-level env defaults for
    # collections created before this surface existed.
    coll_vendor = getattr(collection, "extraction_vendor", None)
    coll_model = getattr(collection, "extraction_model", None)
    coll_endpoint = getattr(collection, "extraction_endpoint", None)
    resolved_vendor = coll_vendor or "openai"

    # Per-request key handling depends on vendor: OpenAI requires a key
    # (returned-key fallback handled by the plugin); Ollama doesn't unless
    # the operator put it behind an auth proxy.
    api_key = (openai_api_key or kg_config.get("openai_api_key") or "").strip()
    if resolved_vendor == "openai" and not api_key:
        return {
            "indexed": False,
            "chunks": len(chunks),
            "reason": "no_openai_api_key",
            "error": (
                "OpenAI API key not supplied. Pass via X-OpenAI-Api-Key header "
                "or set KG_RAG_OPENAI_API_KEY in the KB server env."
            ),
        }

    extractor_config = dict(kg_config)
    extractor_config["openai_api_key"] = api_key
    extractor = ConceptExtractor(
        kg_config=extractor_config,
        vendor=resolved_vendor,
        model=coll_model,
        api_endpoint=coll_endpoint,
        api_key=api_key if resolved_vendor == "openai" else "",
    )

    extraction_start = time.perf_counter()
    try:
        extraction = extractor.extract_for_chunks(chunks)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Concept extraction failed: %s", exc)
        return {
            "indexed": False,
            "chunks": len(chunks),
            "error": f"concept_extraction_failed: {exc}",
        }
    extraction_ms = (time.perf_counter() - extraction_start) * 1000

    # Pick a filename if we weren't given one.
    if not filename:
        for ck in chunks:
            for key in ("filename", "source_label", "title"):
                value = ck.metadata.get(key)
                if value:
                    filename = str(value)
                    break
            if filename:
                break
    filename = filename or "collection_chunks"

    collection_payload = {
        "id": collection.id,
        "name": collection.name,
        "organization_id": collection.organization_id,
        "owner": collection.organization_id,
    }

    from services.graph_store import get_graph_store

    graph_store = get_graph_store()
    if not graph_store.is_configured() or not graph_store.is_available():
        return {
            "indexed": False,
            "chunks": len(chunks),
            "error": "neo4j_unavailable",
        }

    graph_start = time.perf_counter()
    try:
        graph_store.ingest_chunks(
            collection=collection_payload,
            file_id=file_id,
            filename=filename,
            chunks=chunks,
            concepts_by_chunk=extraction.concepts_by_chunk,
            entities=extraction.entities,
            relationships=extraction.relationships,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Graph write failed: %s", exc)
        return {
            "indexed": False,
            "chunks": len(chunks),
            "extraction_ms": extraction_ms,
            "error": f"graph_write_failed: {exc}",
        }
    graph_ms = (time.perf_counter() - graph_start) * 1000

    return {
        "indexed": True,
        "chunks": len(chunks),
        "entities": len(extraction.entities),
        "relationships": len(extraction.relationships),
        "extraction_ms": extraction_ms,
        "graph_ms": graph_ms,
    }
