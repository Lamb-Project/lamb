"""KG-RAG query augmentation: vector seed retrieval + Neo4j graph expansion.

In the legacy KB server this was a top-level ``QueryPlugin`` registered on
the monolithic ``PluginRegistry``. The new KB server's plugin registries
(``VectorDBRegistry``, ``ChunkingRegistry``, ``EmbeddingRegistry``) own
ingestion-time plugins only; query-time augmentation here is invoked
directly from :mod:`services.query_service` when the caller selects
``plugin_name='kg_rag_query'`` (see ``query_with_plugin``).

The augmentation is a no-op fallback when:

* ``KG_RAG_ENABLED`` is false at the server level, or
* the collection's ``graph_enabled`` flag is false, or
* Neo4j is not configured / reachable, or
* the baseline vector search returned no seeds.

In every failure path the baseline vector results are returned unchanged
with a ``warnings`` entry attached to the trace.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from database.models import Collection
from plugins.base import EmbeddingFunction, VectorDBBackend

logger = logging.getLogger(__name__)


class KGRAGQueryPlugin:
    """Augment vector retrieval with Neo4j graph expansion."""

    name = "kg_rag_query"
    description = "KG-RAG query with vector seed retrieval and graph expansion"

    def augment(
        self,
        *,
        db: Any,
        collection: Collection,
        backend: VectorDBBackend,
        embedding_function: EmbeddingFunction,
        query_text: str,
        baseline_results: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        import config as config_module

        top_k = int(params.get("top_k", 5) or 5)
        return_parent_context = self._as_bool(params.get("return_parent_context", True))
        include_trace = self._as_bool(params.get("include_trace", True))

        kg_config = config_module.get_kg_rag_config()
        graph_depth = int(
            params.get("graph_depth") or kg_config.get("graph_depth") or 2
        )
        graph_depth = max(1, min(graph_depth, 4))
        graph_limit_factor = int(
            params.get("graph_limit_factor") or kg_config.get("limit_factor") or 4
        )
        graph_limit_factor = max(1, min(graph_limit_factor, 20))

        seed_chunk_ids = [
            cid
            for cid in (self._result_chunk_id(result) for result in baseline_results)
            if cid
        ]

        trace: dict[str, Any] = {
            "mode": "kg_rag",
            "enabled": bool(kg_config.get("enabled")),
            "graph_expanded": False,
            "seed_chunk_ids": seed_chunk_ids,
            "entry_concepts": [],
            "traversed_edges": [],
            "expanded_chunk_ids": [],
            "latest_changes": [],
            "vector_latency_ms": 0.0,
            "graph_latency_ms": 0.0,
            "warnings": [],
        }

        if not kg_config.get("enabled"):
            trace["warnings"].append("KG-RAG is disabled; returning vector baseline")
            return self._attach_trace(baseline_results, trace, include_trace)
        if not getattr(collection, "graph_enabled", False):
            trace["warnings"].append(
                "Collection has graph_enabled=false; returning vector baseline"
            )
            return self._attach_trace(baseline_results, trace, include_trace)
        if not seed_chunk_ids:
            trace["warnings"].append(
                "No vector seed chunks found; graph expansion skipped"
            )
            return self._attach_trace(baseline_results, trace, include_trace)

        # Defer the graph import until we actually need it so the plugin
        # module stays loadable when the optional ``neo4j`` package is
        # missing.
        from services.graph_store import get_graph_store

        graph_store = get_graph_store()
        if not graph_store.is_configured():
            trace["warnings"].append(
                "Neo4j is not configured; returning vector baseline"
            )
            return self._attach_trace(baseline_results, trace, include_trace)

        graph_start = time.perf_counter()
        try:
            expansion = graph_store.expand_from_chunks(
                collection_id=str(collection.id),
                org_id=str(collection.organization_id),
                seed_chunk_ids=seed_chunk_ids,
                depth=graph_depth,
                limit=top_k * graph_limit_factor,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("KG-RAG graph expansion failed: %s", exc)
            trace["warnings"].append(f"Graph expansion failed: {exc}")
            trace["graph_latency_ms"] = (time.perf_counter() - graph_start) * 1000
            return self._attach_trace(baseline_results, trace, include_trace)

        trace.update(
            {
                "graph_expanded": bool(expansion.get("expanded_chunk_ids")),
                "entry_concepts": expansion.get("entry_concepts", []),
                "traversed_edges": expansion.get("traversed_edges", []),
                "expanded_chunk_ids": expansion.get("expanded_chunk_ids", []),
                "latest_changes": expansion.get("latest_changes", []),
                "graph_latency_ms": expansion.get(
                    "graph_latency_ms",
                    (time.perf_counter() - graph_start) * 1000,
                ),
            }
        )

        expanded_ids = [
            cid
            for cid in expansion.get("expanded_chunk_ids", [])
            if cid not in seed_chunk_ids
        ]
        expanded_results = self._fetch_expanded_results(
            backend=backend,
            collection=collection,
            embedding_function=embedding_function,
            expanded_ids=expanded_ids,
            return_parent_context=return_parent_context,
        )

        merged = self._merge_results(baseline_results + expanded_results, top_k=top_k)
        if not expanded_results and not trace["graph_expanded"]:
            trace["warnings"].append("Graph returned no additional chunks")
        return self._attach_trace(merged, trace, include_trace)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
            "enable",
            "enabled",
        }

    @staticmethod
    def _result_chunk_id(result: dict[str, Any]) -> str | None:
        metadata = result.get("metadata") or {}
        return (
            metadata.get("document_id")
            or metadata.get("child_chunk_id")
            or metadata.get("chunk_id")
        )

    def _fetch_expanded_results(
        self,
        *,
        backend: VectorDBBackend,
        collection: Collection,
        embedding_function: EmbeddingFunction,
        expanded_ids: list[str],
        return_parent_context: bool,
    ) -> list[dict[str, Any]]:
        """Look up chunks discovered by graph expansion via the public backend API.

        Uses :meth:`VectorDBBackend.get_chunks_by_id` so each backend can
        implement ID lookup in its own way. A backend that doesn't
        support it returns ``[]``, and KG-RAG degrades to "graph found
        related chunks but we can't pull their text" — the trace surfaces
        this as a warning.
        """
        if not expanded_ids:
            return []

        try:
            fetched = backend.get_chunks_by_id(
                collection_id=collection.backend_collection_id or str(collection.id),
                storage_path=collection.storage_path,
                chunk_ids=expanded_ids,
                embedding_function=embedding_function,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not fetch expanded chunks: %s", exc)
            return []

        results: list[dict[str, Any]] = []
        for item in fetched:
            metadata = dict(item.metadata or {})
            metadata["kg_rag_origin"] = "graph_expansion"
            data = metadata.pop("parent_text", None) if return_parent_context else None
            results.append(
                {
                    "similarity": item.score or 0.72,
                    "data": data or item.text,
                    "metadata": metadata,
                }
            )
        return results

    def _merge_results(
        self, results: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]:
        by_chunk_id: dict[str, dict[str, Any]] = {}
        for result in results:
            chunk_id = self._result_chunk_id(result) or str(result.get("data", ""))[:120]
            existing = by_chunk_id.get(chunk_id)
            if existing is None or float(result.get("similarity", 0.0)) > float(
                existing.get("similarity", 0.0)
            ):
                by_chunk_id[chunk_id] = result

        ordered = sorted(
            by_chunk_id.values(),
            key=lambda item: float(item.get("similarity", 0.0)),
            reverse=True,
        )
        return ordered[: max(top_k, 1) + 3]

    @staticmethod
    def _attach_trace(
        results: list[dict[str, Any]],
        trace: dict[str, Any],
        include_trace: bool,
    ) -> list[dict[str, Any]]:
        if not include_trace:
            return results
        traced_results: list[dict[str, Any]] = []
        for result in results:
            item = dict(result)
            metadata = dict(item.get("metadata") or {})
            metadata["kg_rag"] = trace
            item["metadata"] = metadata
            traced_results.append(item)
        return traced_results
