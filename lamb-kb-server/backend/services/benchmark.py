"""Benchmark service for comparing vector RAG and KG-RAG retrieval."""

from __future__ import annotations

from pathlib import PurePosixPath
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence

from fastapi import HTTPException

from schemas.benchmark import (
    BenchmarkComparison,
    BenchmarkDataset,
    BenchmarkDatasetSummary,
    BenchmarkMetrics,
    BenchmarkQuestion,
    BenchmarkQueryResult,
    BenchmarkQueryScore,
    BenchmarkRunAllResponse,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
)

_DATASETS: Dict[str, Dict[str, Any]] = {
    "educational": {
        "name": "LAMB KG-RAG educational QA starter set",
        "description": "Starter benchmark for comparing classic vector RAG and KG-RAG on LAMB-style educational retrieval questions.",
        "expected_behavior": "mixed: single-hop parity, multi-hop KG-RAG may improve recall",
        "recommended_top_k": 5,
        "recommended_graph_depth": 2,
        "questions": [
            {
                "id": "q1",
                "question": "What does the current LAMB-style baseline use ChromaDB for?",
                "expected_answer": "It stores semantic vectors for chunks and retrieves similar fragments.",
                "relevant_files": ["rag_basics.md", "lamb_kb_server.md"],
                "expected_concepts": ["chromadb", "vector rag", "embeddings"],
                "kind": "single-hop",
            },
            {
                "id": "q2",
                "question": "Why can a knowledge graph improve questions that require information from multiple course documents?",
                "expected_answer": "It traverses related concepts and can recover evidence that is conceptually connected even when it is not the closest vector match.",
                "relevant_files": ["rag_basics.md", "knowledge_graphs.md"],
                "expected_concepts": [
                    "multi-hop retrieval",
                    "knowledge graph",
                    "vector search",
                ],
                "kind": "multi-hop",
            },
            {
                "id": "q3",
                "question": "Why does traceability matter when educators rename or merge concepts?",
                "expected_answer": "Traceability records ChangeEvent nodes with operation, actor, timestamp, affected concepts, and payload so graph edits can be audited.",
                "relevant_files": [
                    "traceability_and_curation.md",
                    "knowledge_graphs.md",
                ],
                "expected_concepts": ["changeevent", "manual curation", "traceability"],
                "kind": "multi-hop",
            },
            {
                "id": "q4",
                "question": "Which technologies does the prototype replicate from the LAMB kb-server architecture?",
                "expected_answer": "FastAPI, SQLite, ChromaDB, Markdown ingestion, parent-child chunking, and chat completion.",
                "relevant_files": ["lamb_kb_server.md", "rag_basics.md"],
                "expected_concepts": [
                    "fastapi",
                    "sqlite",
                    "chromadb",
                    "parent-child chunking",
                ],
                "kind": "single-hop",
            },
            {
                "id": "q5",
                "question": "How should graph expansion latency be evaluated in the project?",
                "expected_answer": "Benchmark vector retrieval latency, graph expansion latency, and total retrieval latency, with a target of keeping graph expansion below 50 ms when possible.",
                "relevant_files": ["evaluation_metrics.md", "knowledge_graphs.md"],
                "expected_concepts": ["latency", "cypher", "graph expansion"],
                "kind": "multi-hop",
            },
            {
                "id": "q6",
                "question": "What is the purpose of parent-child chunking in a LAMB-style retrieval pipeline?",
                "expected_answer": "Small child chunks improve semantic search while larger parent chunks give the language model enough context.",
                "relevant_files": ["rag_basics.md"],
                "expected_concepts": [
                    "parent-child chunking",
                    "child chunks",
                    "parent chunks",
                ],
                "kind": "single-hop",
            },
            {
                "id": "q7",
                "question": "How does the prototype keep the real LAMB repository untouched while still imitating its behavior?",
                "expected_answer": "It runs in an isolated prototype folder and reimplements only the relevant collection, ingestion, retrieval, and chat behavior.",
                "relevant_files": ["lamb_kb_server.md"],
                "expected_concepts": ["prototype", "lamb", "kb-server"],
                "kind": "single-hop",
            },
            {
                "id": "q8",
                "question": "Which metric rewards placing the first relevant source as early as possible?",
                "expected_answer": "Mean Reciprocal Rank rewards the first relevant result appearing early in the ranking.",
                "relevant_files": ["evaluation_metrics.md"],
                "expected_concepts": ["mean reciprocal rank", "mrr"],
                "kind": "single-hop",
            },
            {
                "id": "q9",
                "question": "What should the KG-RAG UI show to make retrieval less opaque?",
                "expected_answer": "It should show entry concepts, traversed relationships, expanded chunks, and recent ChangeEvent metadata.",
                "relevant_files": [
                    "knowledge_graphs.md",
                    "traceability_and_curation.md",
                ],
                "expected_concepts": [
                    "entry concepts",
                    "traversed relationships",
                    "changeevent",
                ],
                "kind": "multi-hop",
            },
            {
                "id": "q10",
                "question": "Why is recall important for multi-hop educational questions?",
                "expected_answer": "Recall measures whether all expected relevant sources were recovered, which matters when a correct answer needs evidence from multiple files.",
                "relevant_files": ["evaluation_metrics.md", "rag_basics.md"],
                "expected_concepts": ["recall", "multi-hop", "relevant sources"],
                "kind": "multi-hop",
            },
        ],
    },
    "control": {
        "name": "Control benchmark with no inter-document connections",
        "description": "Single-document questions where every answer is contained in one standalone profile. KG-RAG should not materially outperform vector RAG.",
        "expected_behavior": "parity: KG-RAG should be the same or nearly the same as vector baseline",
        "recommended_top_k": 1,
        "recommended_graph_depth": 1,
        "questions": [
            {
                "id": "c1",
                "question": "What owner and inspection cadence are listed for Solar Kiln?",
                "expected_answer": "Solar Kiln is owned by the Thermal Lab Desk and has an inspection cadence of every 14 days.",
                "relevant_files": ["solar_kiln_profile.md"],
                "expected_concepts": ["solar kiln", "thermal lab desk", "sk-14"],
                "kind": "control-single-doc",
            },
            {
                "id": "c2",
                "question": "What checksum code and owner are listed for Iris Archive?",
                "expected_answer": "Iris Archive has checksum code IA-72 and is owned by the Records Integrity Desk.",
                "relevant_files": ["iris_archive_profile.md"],
                "expected_concepts": [
                    "iris archive",
                    "ia-72",
                    "records integrity desk",
                ],
                "kind": "control-single-doc",
            },
            {
                "id": "c3",
                "question": "What route code and inspection cadence are listed for Delta Ferry?",
                "expected_answer": "Delta Ferry has route code DF-08 and an inspection cadence of every 9 days.",
                "relevant_files": ["delta_ferry_profile.md"],
                "expected_concepts": ["delta ferry", "df-08", "coastal transit desk"],
                "kind": "control-single-doc",
            },
            {
                "id": "c4",
                "question": "What protocol code and owner are listed for Orchid Lab?",
                "expected_answer": "Orchid Lab has protocol code OL-31 and is owned by the Botanical Methods Desk.",
                "relevant_files": ["orchid_lab_profile.md"],
                "expected_concepts": ["orchid lab", "ol-31", "botanical methods desk"],
                "kind": "control-single-doc",
            },
        ],
    },
    "paper": {
        "name": "Paper-style MultiHop-RAG benchmark",
        "description": "Small news-style benchmark inspired by MultiHop-RAG, HotpotQA, and MuSiQue. Questions require evidence across separated documents.",
        "expected_behavior": "improvement: KG-RAG should improve recall and MRR on multi-hop chains",
        "recommended_top_k": 5,
        "recommended_graph_depth": 4,
        "questions": [
            {
                "id": "p1",
                "question": "After the Aurora Port outage, which agency owns the project that mitigated the root failure?",
                "expected_answer": "The Aurora Port outage was caused by TideNet router failure, which is mitigated by Harbor Battery Deployment; that project is owned by the Port Resilience Office.",
                "relevant_files": [
                    "city_incident_digest.md",
                    "failure_to_project_map.md",
                    "agency_directory.md",
                ],
                "expected_concepts": [
                    "aurora port outage",
                    "tidenet router failure",
                    "harbor battery deployment",
                    "port resilience office",
                ],
                "kind": "paper-inference",
            },
            {
                "id": "p2",
                "question": "Which mitigation had the larger budget: the project for the Aurora Port outage or the project for the Lantern Bridge closure?",
                "expected_answer": "Aurora Port maps to Harbor Battery Deployment at 18.4 million euros, while Lantern Bridge maps to Eastbank Shuttle Loop at 12.1 million euros, so Harbor Battery Deployment is larger.",
                "relevant_files": [
                    "city_incident_digest.md",
                    "failure_to_project_map.md",
                    "budget_register.md",
                ],
                "expected_concepts": [
                    "aurora port outage",
                    "lantern bridge closure",
                    "harbor battery deployment",
                    "eastbank shuttle loop",
                ],
                "kind": "paper-comparison",
            },
            {
                "id": "p3",
                "question": "Which was completed earlier: the mitigation for the Lantern Bridge closure or the mitigation for the Cobalt Clinic evacuation?",
                "expected_answer": "Lantern Bridge maps to Eastbank Shuttle Loop, completed on 2025-07-02. Cobalt Clinic maps to Clinic Microgrid Retrofit, completed on 2025-10-20. Eastbank Shuttle Loop was completed earlier.",
                "relevant_files": [
                    "city_incident_digest.md",
                    "failure_to_project_map.md",
                    "schedule_updates.md",
                ],
                "expected_concepts": [
                    "lantern bridge closure",
                    "cobalt clinic evacuation",
                    "eastbank shuttle loop",
                    "clinic microgrid retrofit",
                ],
                "kind": "paper-temporal",
            },
            {
                "id": "p4",
                "question": "What budget and owner correspond to the project that mitigated the MercyWing generator fault?",
                "expected_answer": "MercyWing generator fault maps to Clinic Microgrid Retrofit, which has a budget of 9.6 million euros and is owned by the Health Facilities Bureau.",
                "relevant_files": [
                    "failure_to_project_map.md",
                    "budget_register.md",
                    "agency_directory.md",
                ],
                "expected_concepts": [
                    "mercywing generator fault",
                    "clinic microgrid retrofit",
                    "health facilities bureau",
                ],
                "kind": "paper-inference",
            },
            {
                "id": "p5",
                "question": "The Harbor Aquarium flood appears in a query. Which mitigation project, budget, and owner should be returned?",
                "expected_answer": "No mitigation project, budget, or owner should be returned because the Harbor Aquarium flood is not connected to a registered mitigation project in this corpus.",
                "relevant_files": ["null_registry.md"],
                "expected_concepts": ["harbor aquarium flood"],
                "kind": "paper-null",
                "answerable": False,
            },
            {
                "id": "p6",
                "question": "Which owner agency is responsible for the mitigation project that has the emergency mobility budget category?",
                "expected_answer": "The emergency mobility budget category belongs to Eastbank Shuttle Loop, which is owned by the Transit Continuity Unit.",
                "relevant_files": ["budget_register.md", "agency_directory.md"],
                "expected_concepts": [
                    "emergency mobility",
                    "eastbank shuttle loop",
                    "transit continuity unit",
                ],
                "kind": "paper-bridge",
            },
        ],
    },
    "extreme": {
        "name": "Extreme KG-RAG multi-hop benchmark",
        "description": "Adversarial questions where the surface clue lives in one file and the decisive answer lives several graph hops away.",
        "expected_behavior": "improvement: adversarial multi-hop cases should favor KG-RAG over vector baseline",
        "recommended_top_k": 6,
        "recommended_graph_depth": 4,
        "questions": [
            {
                "id": "x1",
                "question": "Case Orion-17 needs closure. What exact closure sequence should be applied?",
                "expected_answer": "Follow protocol Glass Harbor: disable the quartz bypass, replace the cerulean latch, and run the cold-start assay.",
                "relevant_files": [
                    "anomaly_bridge_extreme.md",
                    "protocol_index_extreme.md",
                    "remediation_playbook_extreme.md",
                ],
                "expected_concepts": [
                    "orion-17",
                    "aster valve drift",
                    "m-41",
                    "glass harbor",
                ],
                "kind": "extreme-multi-hop",
            },
            {
                "id": "x2",
                "question": "Case Vega-03 needs closure. What exact closure sequence should be applied?",
                "expected_answer": "Vega-03 has Lumen shard bloom, which maps to Q-Delta and then Night Orchard: isolate the amber bus, reseed the clock lattice, and run the midnight parity check.",
                "relevant_files": [
                    "anomaly_bridge_extreme.md",
                    "protocol_index_extreme.md",
                    "remediation_playbook_extreme.md",
                ],
                "expected_concepts": [
                    "vega-03",
                    "lumen shard bloom",
                    "q-delta",
                    "night orchard",
                ],
                "kind": "extreme-multi-hop",
            },
            {
                "id": "x3",
                "question": "Case Mira-22 needs closure. What exact closure sequence should be applied?",
                "expected_answer": "Mira-22 has Sable checksum echo, which maps to R-9 and then Blue Thread: rotate the ivory token, rebuild the relay ledger, and run the archive handshake.",
                "relevant_files": [
                    "anomaly_bridge_extreme.md",
                    "protocol_index_extreme.md",
                    "remediation_playbook_extreme.md",
                ],
                "expected_concepts": [
                    "mira-22",
                    "sable checksum echo",
                    "r-9",
                    "blue thread",
                ],
                "kind": "extreme-multi-hop",
            },
            {
                "id": "x4",
                "question": "A HelioForge report only says Aster valve drift. What closure sequence follows from the chain?",
                "expected_answer": "Aster valve drift indicates M-41; M-41 is governed by Glass Harbor; Glass Harbor requires disabling the quartz bypass, replacing the cerulean latch, and running the cold-start assay.",
                "relevant_files": [
                    "anomaly_bridge_extreme.md",
                    "protocol_index_extreme.md",
                    "remediation_playbook_extreme.md",
                ],
                "expected_concepts": ["aster valve drift", "m-41", "glass harbor"],
                "kind": "extreme-multi-hop",
            },
            {
                "id": "x5",
                "question": "A North Atrium report only says Lumen shard bloom. What closure sequence follows from the chain?",
                "expected_answer": "Lumen shard bloom indicates Q-Delta; Q-Delta is governed by Night Orchard; Night Orchard requires isolating the amber bus, reseeding the clock lattice, and running the midnight parity check.",
                "relevant_files": [
                    "anomaly_bridge_extreme.md",
                    "protocol_index_extreme.md",
                    "remediation_playbook_extreme.md",
                ],
                "expected_concepts": ["lumen shard bloom", "q-delta", "night orchard"],
                "kind": "extreme-multi-hop",
            },
            {
                "id": "x6",
                "question": "An Archive Relay report only says Sable checksum echo. What closure sequence follows from the chain?",
                "expected_answer": "Sable checksum echo indicates R-9; R-9 is governed by Blue Thread; Blue Thread requires rotating the ivory token, rebuilding the relay ledger, and running the archive handshake.",
                "relevant_files": [
                    "anomaly_bridge_extreme.md",
                    "protocol_index_extreme.md",
                    "remediation_playbook_extreme.md",
                ],
                "expected_concepts": ["sable checksum echo", "r-9", "blue thread"],
                "kind": "extreme-multi-hop",
            },
        ],
    },
}

_ALIASES = {
    "default": "educational",
    "sample": "educational",
    "education": "educational",
    "multihop": "paper",
    "multi-hop": "paper",
    "paper-multihop": "paper",
    "adversarial": "extreme",
    "no-connections": "control",
    "no_connections": "control",
}


class BenchmarkService:
    """Run retrieval benchmarks against an existing LAMB collection."""

    @classmethod
    def list_datasets(cls) -> List[BenchmarkDatasetSummary]:
        return [cls._dataset_summary(dataset_id) for dataset_id in _DATASETS]

    @classmethod
    def get_dataset(cls, dataset_id: str) -> BenchmarkDataset:
        canonical = cls._canonical_dataset_id(dataset_id)
        config = _DATASETS[canonical]
        return BenchmarkDataset(
            id=canonical,
            name=config["name"],
            description=config["description"],
            expected_behavior=config["expected_behavior"],
            recommended_top_k=config["recommended_top_k"],
            recommended_graph_depth=config["recommended_graph_depth"],
            question_count=len(config["questions"]),
            questions=[BenchmarkQuestion(**item) for item in config["questions"]],
        )

    @classmethod
    def run(
        cls,
        db: Any,
        collection_id: str,
        request: BenchmarkRunRequest,
        embedding_credentials: Optional[Dict[str, Any]] = None,
    ) -> BenchmarkRunResponse:
        from services.query_service import query_with_plugin

        creds = embedding_credentials or {}
        dataset = cls.get_dataset(request.dataset_id or "educational")
        questions = request.questions or dataset.questions
        if not questions:
            raise HTTPException(
                status_code=400, detail="No benchmark questions supplied"
            )

        top_k = int(request.top_k or dataset.recommended_top_k or 5)
        graph_depth = int(request.graph_depth or dataset.recommended_graph_depth or 2)
        top_k = max(1, min(top_k, 50))
        graph_depth = max(1, min(graph_depth, 4))
        threshold = float(request.threshold or 0.0)

        baseline_scores: List[BenchmarkQueryScore] = []
        kg_scores: List[BenchmarkQueryScore] = []
        rows: List[BenchmarkQueryResult] = []

        for question in questions:
            baseline_response = query_with_plugin(
                db=db,
                collection_id=collection_id,
                query_text=question.question,
                plugin_name="simple_query",
                plugin_params={"top_k": top_k, "threshold": threshold},
                embedding_credentials=creds,
            )
            kg_response = query_with_plugin(
                db=db,
                collection_id=collection_id,
                query_text=question.question,
                plugin_name="kg_rag_query",
                plugin_params={
                    "top_k": top_k,
                    "threshold": threshold,
                    "graph_depth": graph_depth,
                    "include_trace": True,
                },
                embedding_credentials=creds,
            )

            baseline_score = cls._score_response(
                question=question,
                response=baseline_response,
                top_k=top_k,
                vector_ms=float(
                    baseline_response.get("timing", {}).get("total_ms", 0.0)
                ),
                graph_ms=0.0,
                total_ms=float(
                    baseline_response.get("timing", {}).get("total_ms", 0.0)
                ),
            )
            trace = cls._trace_from_results(kg_response.get("results", []))
            kg_total_ms = float(kg_response.get("timing", {}).get("total_ms", 0.0))
            kg_graph_ms = float(trace.get("graph_latency_ms") or 0.0)
            kg_vector_ms = float(
                trace.get("vector_latency_ms") or max(kg_total_ms - kg_graph_ms, 0.0)
            )
            kg_score = cls._score_response(
                question=question,
                response=kg_response,
                top_k=top_k,
                vector_ms=kg_vector_ms,
                graph_ms=kg_graph_ms,
                total_ms=kg_total_ms,
            )

            baseline_scores.append(baseline_score)
            kg_scores.append(kg_score)
            rows.append(
                BenchmarkQueryResult(
                    question_id=question.id,
                    question=question.question,
                    kind=question.kind,
                    relevant_files=question.relevant_files,
                    expected_concepts=question.expected_concepts,
                    baseline=baseline_score,
                    kg_rag=kg_score,
                )
            )

        baseline_metrics = cls._aggregate(baseline_scores)
        kg_metrics = cls._aggregate(kg_scores)
        comparison = BenchmarkComparison(
            delta_precision_at_k=kg_metrics.precision_at_k
            - baseline_metrics.precision_at_k,
            delta_recall_at_k=kg_metrics.recall_at_k - baseline_metrics.recall_at_k,
            delta_mrr=kg_metrics.mrr - baseline_metrics.mrr,
            graph_overhead_ms=kg_metrics.avg_total_ms - baseline_metrics.avg_total_ms,
            expected_behavior=dataset.expected_behavior,
        )

        return BenchmarkRunResponse(
            collection_id=collection_id,
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            top_k=top_k,
            graph_depth=graph_depth,
            baseline=baseline_metrics,
            kg_rag=kg_metrics,
            comparison=comparison,
            results=rows,
        )

    @classmethod
    def run_all(
        cls,
        db: Any,
        collection_id: str,
        dataset_ids: Sequence[str],
        threshold: float = 0.0,
        embedding_credentials: Optional[Dict[str, Any]] = None,
    ) -> BenchmarkRunAllResponse:
        seen = set()
        runs: List[BenchmarkRunResponse] = []
        for dataset_id in dataset_ids or _DATASETS.keys():
            canonical = cls._canonical_dataset_id(dataset_id)
            if canonical in seen:
                continue
            seen.add(canonical)
            dataset = cls.get_dataset(canonical)
            runs.append(
                cls.run(
                    db=db,
                    collection_id=collection_id,
                    request=BenchmarkRunRequest(
                        dataset_id=canonical,
                        top_k=dataset.recommended_top_k,
                        graph_depth=dataset.recommended_graph_depth,
                        threshold=threshold,
                    ),
                    embedding_credentials=embedding_credentials,
                )
            )

        summary = {
            "datasets": len(runs),
            "avg_delta_recall_at_k": (
                mean(run.comparison.delta_recall_at_k for run in runs) if runs else 0.0
            ),
            "avg_delta_mrr": (
                mean(run.comparison.delta_mrr for run in runs) if runs else 0.0
            ),
            "avg_graph_overhead_ms": (
                mean(run.comparison.graph_overhead_ms for run in runs) if runs else 0.0
            ),
        }
        return BenchmarkRunAllResponse(
            collection_id=collection_id,
            runs=runs,
            summary=summary,
        )

    @classmethod
    def _dataset_summary(cls, dataset_id: str) -> BenchmarkDatasetSummary:
        config = _DATASETS[dataset_id]
        return BenchmarkDatasetSummary(
            id=dataset_id,
            name=config["name"],
            description=config["description"],
            expected_behavior=config["expected_behavior"],
            recommended_top_k=config["recommended_top_k"],
            recommended_graph_depth=config["recommended_graph_depth"],
            question_count=len(config["questions"]),
        )

    @staticmethod
    def _canonical_dataset_id(dataset_id: str) -> str:
        normalized = (dataset_id or "educational").strip().lower().replace("_", "-")
        canonical = _ALIASES.get(normalized, normalized)
        if canonical not in _DATASETS:
            valid = ", ".join(sorted(_DATASETS))
            raise HTTPException(
                status_code=400,
                detail=f"Unknown benchmark dataset '{dataset_id}'. Expected one of: {valid}",
            )
        return canonical

    @classmethod
    def _score_response(
        cls,
        *,
        question: BenchmarkQuestion,
        response: Dict[str, Any],
        top_k: int,
        vector_ms: float,
        graph_ms: float,
        total_ms: float,
    ) -> BenchmarkQueryScore:
        retrieved_files = cls._retrieved_files(response.get("results", []), top_k)
        relevant = {cls._normalize_filename(name) for name in question.relevant_files}
        relevant.discard("")
        if not relevant:
            return BenchmarkQueryScore(
                vector_ms=vector_ms,
                graph_ms=graph_ms,
                total_ms=total_ms,
                retrieved_files=retrieved_files,
            )

        hits = [filename in relevant for filename in retrieved_files]
        precision = sum(1 for hit in hits if hit) / max(top_k, 1)
        recall = len(
            {filename for filename in retrieved_files if filename in relevant}
        ) / len(relevant)
        reciprocal = 0.0
        for index, hit in enumerate(hits, start=1):
            if hit:
                reciprocal = 1.0 / index
                break

        return BenchmarkQueryScore(
            precision_at_k=precision,
            recall_at_k=recall,
            mrr=reciprocal,
            vector_ms=vector_ms,
            graph_ms=graph_ms,
            total_ms=total_ms,
            retrieved_files=retrieved_files,
        )

    @staticmethod
    def _aggregate(rows: Sequence[BenchmarkQueryScore]) -> BenchmarkMetrics:
        if not rows:
            return BenchmarkMetrics()
        return BenchmarkMetrics(
            precision_at_k=mean(row.precision_at_k for row in rows),
            recall_at_k=mean(row.recall_at_k for row in rows),
            mrr=mean(row.mrr for row in rows),
            avg_vector_ms=mean(row.vector_ms for row in rows),
            avg_graph_ms=mean(row.graph_ms for row in rows),
            avg_total_ms=mean(row.total_ms for row in rows),
        )

    @classmethod
    def _retrieved_files(
        cls, results: Sequence[Dict[str, Any]], top_k: int
    ) -> List[str]:
        retrieved: List[str] = []
        seen = set()
        for result in results:
            metadata = result.get("metadata") or {}
            filename = cls._result_filename(metadata)
            if not filename or filename in seen:
                continue
            seen.add(filename)
            retrieved.append(filename)
            if len(retrieved) >= top_k:
                break
        return retrieved

    @classmethod
    def _result_filename(cls, metadata: Dict[str, Any]) -> str:
        for key in ("filename", "original_filename", "source", "file_path", "file_url"):
            value = metadata.get(key)
            filename = cls._normalize_filename(value)
            if filename:
                return filename
        return ""

    @staticmethod
    def _normalize_filename(value: Optional[Any]) -> str:
        if not value:
            return ""
        text = str(value).strip().replace("\\", "/")
        if not text:
            return ""
        return PurePosixPath(text).name.lower()

    @staticmethod
    def _trace_from_results(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        for result in results:
            metadata = result.get("metadata") or {}
            trace = metadata.get("kg_rag")
            if isinstance(trace, dict):
                return trace
        return {}
