"""Unit tests for ``services.benchmark.BenchmarkService``.

Covers dataset listing/lookup/aliasing, the per-question scoring math
(precision/recall/MRR, retrieved-file extraction and normalization), the
trace extraction helper, and the full ``run`` / ``run_all`` orchestration
with a fake ``query_with_plugin``.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import services.query_service as query_service_module
from schemas.benchmark import (
    BenchmarkQuestion,
    BenchmarkQueryScore,
    BenchmarkRunRequest,
)
from services.benchmark import _DATASETS, BenchmarkService


# ---------------------------------------------------------------------------
# datasets
# ---------------------------------------------------------------------------


def test_list_datasets_covers_all_registered():
    summaries = BenchmarkService.list_datasets()
    assert {s.id for s in summaries} == set(_DATASETS)
    assert all(s.question_count > 0 for s in summaries)


def test_get_dataset_returns_questions():
    ds = BenchmarkService.get_dataset("educational")
    assert ds.id == "educational"
    assert len(ds.questions) == ds.question_count


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("default", "educational"),
        ("SAMPLE", "educational"),
        ("multi_hop", "paper"),
        ("no_connections", "control"),
        ("educational", "educational"),
    ],
)
def test_canonical_dataset_id_aliases(alias, expected):
    assert BenchmarkService._canonical_dataset_id(alias) == expected


def test_canonical_dataset_id_unknown_raises():
    with pytest.raises(HTTPException) as exc:
        BenchmarkService._canonical_dataset_id("does-not-exist")
    assert exc.value.status_code == 400


def test_canonical_dataset_id_default_when_empty():
    assert BenchmarkService._canonical_dataset_id("") == "educational"


# ---------------------------------------------------------------------------
# filename + trace helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),
        ("", ""),
        ("  ", ""),
        ("/docs/Sub/Report.MD", "report.md"),
        ("C:\\win\\Doc.PDF", "doc.pdf"),
    ],
)
def test_normalize_filename(value, expected):
    assert BenchmarkService._normalize_filename(value) == expected


def test_result_filename_key_precedence():
    assert BenchmarkService._result_filename({"filename": "a.md"}) == "a.md"
    assert BenchmarkService._result_filename({"source": "b.md"}) == "b.md"
    assert BenchmarkService._result_filename({"file_url": "/x/c.md"}) == "c.md"
    assert BenchmarkService._result_filename({"unrelated": "x"}) == ""


def test_retrieved_files_dedups_and_caps():
    results = [
        {"metadata": {"filename": "a.md"}},
        {"metadata": {"filename": "a.md"}},  # dup
        {"metadata": {}},                     # no filename -> skipped
        {"metadata": {"filename": "b.md"}},
        {"metadata": {"filename": "c.md"}},
    ]
    out = BenchmarkService._retrieved_files(results, top_k=2)
    assert out == ["a.md", "b.md"]  # capped at top_k


def test_trace_from_results():
    assert BenchmarkService._trace_from_results(
        [{"metadata": {"kg_rag": {"mode": "kg_rag"}}}]
    ) == {"mode": "kg_rag"}
    assert BenchmarkService._trace_from_results([{"metadata": {}}]) == {}


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


def _question(relevant):
    return BenchmarkQuestion(
        id="q", question="q?", relevant_files=relevant, kind="single-hop"
    )


def test_score_response_no_relevant_files():
    score = BenchmarkService._score_response(
        question=_question([]),
        response={"results": [{"metadata": {"filename": "a.md"}}]},
        top_k=5, vector_ms=1.0, graph_ms=0.0, total_ms=1.0,
    )
    # No relevant set -> precision/recall/mrr stay at defaults (0).
    assert score.precision_at_k == 0.0
    assert score.retrieved_files == ["a.md"]


def test_score_response_with_hits():
    score = BenchmarkService._score_response(
        question=_question(["a.md", "missing.md"]),
        response={
            "results": [
                {"metadata": {"filename": "x.md"}},  # miss at rank 1
                {"metadata": {"filename": "a.md"}},  # hit at rank 2
            ]
        },
        top_k=2, vector_ms=1.0, graph_ms=2.0, total_ms=3.0,
    )
    assert score.precision_at_k == 0.5   # 1 hit / top_k(2)
    assert score.recall_at_k == 0.5      # 1 of 2 relevant
    assert score.mrr == 0.5              # first hit at rank 2


def test_aggregate_empty_and_nonempty():
    assert BenchmarkService._aggregate([]).precision_at_k == 0.0
    rows = [
        BenchmarkQueryScore(precision_at_k=1.0, recall_at_k=1.0, mrr=1.0,
                            vector_ms=2.0, graph_ms=0.0, total_ms=2.0),
        BenchmarkQueryScore(precision_at_k=0.0, recall_at_k=0.0, mrr=0.0,
                            vector_ms=4.0, graph_ms=0.0, total_ms=4.0),
    ]
    agg = BenchmarkService._aggregate(rows)
    assert agg.precision_at_k == 0.5
    assert agg.avg_total_ms == 3.0


# ---------------------------------------------------------------------------
# run / run_all orchestration
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_query(monkeypatch):
    """Stub query_with_plugin: baseline misses, kg_rag hits the relevant file."""

    def _qwp(*, db, collection_id, query_text, plugin_name, plugin_params=None,
             embedding_credentials=None):
        if plugin_name == "kg_rag_query":
            return {
                "results": [
                    {"metadata": {"filename": "rag_basics.md",
                                  "kg_rag": {"graph_latency_ms": 5.0,
                                             "vector_latency_ms": 3.0}}},
                ],
                "timing": {"total_ms": 8.0},
            }
        return {
            "results": [{"metadata": {"filename": "unrelated.md"}}],
            "timing": {"total_ms": 2.0},
        }

    monkeypatch.setattr(query_service_module, "query_with_plugin", _qwp)
    return _qwp


def test_run_no_questions_raises(monkeypatch, fake_query):
    # A custom dataset with zero questions -> 400. We force questions empty by
    # passing an explicit empty list AND an unknown dataset is avoided by using
    # a request whose dataset resolves but questions override to empty.
    req = BenchmarkRunRequest(dataset_id="educational", questions=[])
    # questions=[] is falsy -> falls back to dataset.questions (non-empty), so
    # to hit the guard we monkeypatch get_dataset to yield no questions.
    monkeypatch.setattr(
        BenchmarkService, "get_dataset",
        classmethod(lambda cls, ds: type("D", (), {
            "questions": [], "recommended_top_k": 5, "recommended_graph_depth": 2,
            "id": "educational", "name": "n", "expected_behavior": "x",
        })()),
    )
    with pytest.raises(HTTPException) as exc:
        BenchmarkService.run(db=None, collection_id="c1", request=req)
    assert exc.value.status_code == 400


def test_run_full_with_custom_question(fake_query):
    req = BenchmarkRunRequest(
        dataset_id="educational",
        top_k=3,
        graph_depth=2,
        questions=[
            BenchmarkQuestion(
                id="q1", question="what is rag?",
                relevant_files=["rag_basics.md"], kind="single-hop",
            )
        ],
        rrf_k=15,  # extra field forwarded to kg params
    )
    resp = BenchmarkService.run(db=None, collection_id="c1", request=req)
    assert resp.collection_id == "c1"
    assert resp.dataset_id == "educational"
    assert len(resp.results) == 1
    # KG hit the relevant file; baseline missed -> positive recall delta.
    assert resp.kg_rag.recall_at_k == 1.0
    assert resp.baseline.recall_at_k == 0.0
    assert resp.comparison.delta_recall_at_k == 1.0


def test_run_all_dedups_aliases(fake_query):
    resp = BenchmarkService.run_all(
        db=None,
        collection_id="c1",
        dataset_ids=["educational", "default", "sample"],  # all alias to educational
    )
    # All three collapse to one canonical run.
    assert len(resp.runs) == 1
    assert resp.summary["datasets"] == 1
    assert "avg_delta_recall_at_k" in resp.summary


def test_run_all_empty_dataset_ids_uses_all(fake_query):
    resp = BenchmarkService.run_all(db=None, collection_id="c1", dataset_ids=[])
    # Falls back to every registered dataset.
    assert len(resp.runs) == len(_DATASETS)
