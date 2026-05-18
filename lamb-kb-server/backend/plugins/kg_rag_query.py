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

        # Question-entity seeding: extract named-entity-like tokens from
        # the question itself and let the graph contribute chunks that
        # MENTION them, even if vector retrieval missed those chunks.
        # This is the ``local search'' pattern from Microsoft GraphRAG.
        # The expansion is intentionally limited (a few chunks per
        # entity, only specific entities with ≤25 mentions) to avoid
        # flooding the candidate set with chunks that mention common
        # nouns.
        question_entities = self._extract_question_entities(query_text, collection)
        question_expansion: dict[str, Any] = {}
        if question_entities:
            try:
                question_expansion = graph_store.expand_from_concept_names(
                    collection_id=str(collection.id),
                    org_id=str(collection.organization_id),
                    concept_names=question_entities,
                    depth=graph_depth,
                    limit=max(top_k, 2 * top_k),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Question-entity expansion failed: %s", exc)

        # Decide which expansion arms contribute. Chunk-seeded
        # expansion can be useful when the question is short and
        # ambiguous, but it tends to inflate noise on
        # encyclopedic / Wikipedia-style corpora because shared
        # high-frequency entities (``World War II``, ``United
        # States``) connect unrelated chunks. Toggleable via
        # ``params.use_chunk_expansion``.
        use_chunk_expansion = self._as_bool(
            params.get("use_chunk_expansion", False)
        )

        merged_entry_concepts = list(
            dict.fromkeys(
                question_expansion.get("entry_concepts", [])
                + (expansion.get("entry_concepts", []) if use_chunk_expansion else [])
            )
        )
        # Question-entity expansion ranks first: those chunks were
        # reached via question-derived concepts, so their precision is
        # higher than the chunk-seeded expansion which can drift via
        # generic shared entities.
        merged_expanded_ids = list(
            dict.fromkeys(
                question_expansion.get("expanded_chunk_ids", [])
                + (expansion.get("expanded_chunk_ids", []) if use_chunk_expansion else [])
            )
        )

        trace.update(
            {
                "graph_expanded": bool(merged_expanded_ids),
                "entry_concepts": merged_entry_concepts,
                "traversed_edges": expansion.get("traversed_edges", []),
                "expanded_chunk_ids": merged_expanded_ids,
                "latest_changes": expansion.get("latest_changes", []),
                "question_entities": question_entities,
                "graph_latency_ms": expansion.get(
                    "graph_latency_ms",
                    (time.perf_counter() - graph_start) * 1000,
                )
                + question_expansion.get("graph_latency_ms", 0.0),
            }
        )

        expanded_ids = [
            cid for cid in merged_expanded_ids if cid not in seed_chunk_ids
        ]
        expanded_results = self._fetch_expanded_results(
            backend=backend,
            collection=collection,
            embedding_function=embedding_function,
            expanded_ids=expanded_ids,
            return_parent_context=return_parent_context,
        )

        merged = self._rrf_merge(
            baseline_results=baseline_results,
            expanded_results=expanded_results,
            top_k=top_k,
            rrf_k=int(params.get("rrf_k", 40) or 40),
            graph_weight=float(params.get("graph_weight", 0.5) or 0.5),
        )
        if not expanded_results and not trace["graph_expanded"]:
            trace["warnings"].append("Graph returned no additional chunks")
        return self._attach_trace(merged, trace, include_trace)

    # ------------------------------------------------------------------
    # Question-entity extraction (LLM-based)
    # ------------------------------------------------------------------
    #
    # Pulling named entities from a free-text question is the exact kind
    # of short, structured task small LLMs handle reliably. The previous
    # regex-based heuristic missed lowercased multi-word entities
    # (``unsupervised learning``, ``parent-child chunking``) and accepted
    # any capitalized token as if it were a name. A single small-model
    # call with a JSON-schema prompt is more accurate, costs cents per
    # thousand queries on ``gpt-4o-mini``, and finishes in well under
    # 500~ms, comparable to the embedding round-trip.
    #
    # The call is cached per-question text inside this process so
    # benchmark re-runs and identical user queries don't pay the round
    # trip twice. The cache is bounded by ``_QUESTION_CACHE_SIZE`` and
    # uses simple FIFO eviction.

    _QUESTION_CACHE_SIZE = 512
    _question_cache: dict[str, list[str]] = {}

    @classmethod
    def _extract_question_entities(
        cls, question: str, collection: Collection
    ) -> list[str]:
        """Use an LLM to extract named entities from the question.

        Uses the same vendor / model / endpoint configured for the
        collection's build-time extraction (``extraction_vendor`` /
        ``extraction_model`` / ``extraction_endpoint``). Keeping the
        question extractor in lockstep with the build extractor means
        the entity names produced at query time match the canonical
        form stored in the graph — different models can normalize
        entity names differently, and a mismatch silently zeroes the
        question-entity seeding path.

        Falls back to the server-level KG-RAG defaults (then OpenAI
        gpt-4o-mini) when the collection has no per-collection
        extraction config — preserves back-compat for collections
        created before the picker existed.

        Returns an empty list if the backend isn't available or the
        call fails — the graph expansion silently degrades to the
        baseline-seeded path in that case.
        """
        question = (question or "").strip()
        if not question:
            return []

        import config as config_module  # noqa: PLC0415

        kg = config_module.get_kg_rag_config()
        coll_vendor = getattr(collection, "extraction_vendor", None)
        coll_model = getattr(collection, "extraction_model", None)
        coll_endpoint = getattr(collection, "extraction_endpoint", None)
        vendor = coll_vendor or "openai"
        model = coll_model or kg.get("chat_model") or "gpt-4o-mini"
        endpoint = coll_endpoint or ""

        # Cache keyed by (vendor, model, question) so different
        # collections sharing the same question text don't poison each
        # other when they use different models.
        cache_key = f"{vendor}::{model}::{question}"
        if cache_key in cls._question_cache:
            return cls._question_cache[cache_key]

        api_key = ""
        if vendor == "openai":
            api_key = (kg.get("openai_api_key") or "").strip()
            if not api_key:
                return []

        from plugins.base import LLMExtractionRegistry  # noqa: PLC0415

        try:
            backend = LLMExtractionRegistry.build(
                vendor,
                model=model,
                api_key=api_key,
                api_endpoint=endpoint,
                timeout_seconds=15.0,
            )
        except ValueError as exc:
            logger.debug("Question-entity backend %s unavailable: %s", vendor, exc)
            return []

        system = (
            "Extract every named entity from the user question. "
            "Return STRICT JSON of the form {\"entities\": [\"...\", \"...\"]}. "
            "Keep multi-word names whole. Lowercase common nouns are fine if "
            "they would plausibly identify a knowledge-graph concept (e.g. "
            "'parent-child chunking', 'reciprocal rank fusion'). "
            "Do not output entity types, descriptions or explanations — only "
            "the surface strings."
        )

        parsed = backend.chat_json(system=system, user=question)
        entities_raw = parsed.get("entities") if isinstance(parsed, dict) else None
        if not isinstance(entities_raw, list):
            entities_raw = []
        entities = [str(e).strip() for e in entities_raw if str(e).strip()]

        # FIFO cache eviction
        if len(cls._question_cache) >= cls._QUESTION_CACHE_SIZE:
            try:
                cls._question_cache.pop(next(iter(cls._question_cache)))
            except StopIteration:
                pass
        cls._question_cache[cache_key] = entities
        return entities

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

    def _rrf_merge(
        self,
        *,
        baseline_results: list[dict[str, Any]],
        expanded_results: list[dict[str, Any]],
        top_k: int,
        rrf_k: int = 60,
        graph_weight: float = 0.6,
    ) -> list[dict[str, Any]]:
        """Reciprocal Rank Fusion of the vector baseline and the graph expansion.

        Standard RRF assigns each item a score of ``1/(rrf_k + rank)`` per
        ranked list it appears in, and sums across lists. Items appearing
        in *both* the vector list and the graph-expanded list get boosted
        (the graph confirms the vector signal), which is exactly the
        regime where KG-RAG should beat the baseline.

        The graph list contributes with a smaller weight (``graph_weight``)
        because chunks in the expanded list have no semantic similarity
        score against the query --- they were reached via concept
        traversal. The weight prevents pure-graph hits from displacing
        the highest-rank vector hits when the vector signal is already
        unambiguous.

        Each result's ``similarity`` field is replaced with the fused
        score so downstream merging / sorting remains consistent.
        """
        rankings: dict[str, dict[str, Any]] = {}

        def _accumulate(items, weight, list_name):
            for rank, item in enumerate(items, start=1):
                chunk_id = self._result_chunk_id(item) or str(item.get("data", ""))[:120]
                entry = rankings.setdefault(
                    chunk_id,
                    {
                        "item": item,
                        "score": 0.0,
                        "lists": set(),
                    },
                )
                entry["score"] += weight * (1.0 / (rrf_k + rank))
                entry["lists"].add(list_name)
                if list_name == "baseline" or "item" not in entry:
                    entry["item"] = item

        _accumulate(baseline_results, weight=1.0, list_name="baseline")
        _accumulate(expanded_results, weight=graph_weight, list_name="graph")

        ordered = sorted(rankings.values(), key=lambda e: e["score"], reverse=True)
        merged: list[dict[str, Any]] = []
        for entry in ordered[: max(top_k, 1) + 3]:
            item = dict(entry["item"])
            # Preserve the original similarity for trace transparency but
            # surface the fused RRF score in a separate field.
            item["rrf_score"] = entry["score"]
            item["fusion_lists"] = sorted(entry["lists"])
            merged.append(item)
        return merged

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
