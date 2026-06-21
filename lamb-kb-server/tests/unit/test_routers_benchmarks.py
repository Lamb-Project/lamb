"""Router tests for ``routers.benchmarks`` via FastAPI TestClient.

Auth and DB session dependencies are overridden; the BenchmarkService layer
is monkeypatched so these tests stay at the routing/serialization layer.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.connection import get_session
from dependencies import verify_token
from routers import benchmarks as benchmarks_router
from schemas.benchmark import (
    BenchmarkComparison,
    BenchmarkDataset,
    BenchmarkDatasetSummary,
    BenchmarkMetrics,
    BenchmarkRunAllResponse,
    BenchmarkRunResponse,
)
from services.benchmark import BenchmarkService


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(benchmarks_router.router)
    app.dependency_overrides[verify_token] = lambda: "token"
    app.dependency_overrides[get_session] = lambda: object()
    return TestClient(app)


def _summary(ds_id="educational"):
    return BenchmarkDatasetSummary(
        id=ds_id, name="N", description="D", expected_behavior="x",
        recommended_top_k=5, recommended_graph_depth=2, question_count=3,
    )


def test_list_datasets(client, monkeypatch):
    monkeypatch.setattr(BenchmarkService, "list_datasets", classmethod(
        lambda cls: [_summary()]))
    resp = client.get("/benchmarks/datasets")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "educational"


def test_get_dataset(client, monkeypatch):
    monkeypatch.setattr(BenchmarkService, "get_dataset", classmethod(
        lambda cls, ds: BenchmarkDataset(
            id=ds, name="N", description="D", expected_behavior="x",
            recommended_top_k=5, recommended_graph_depth=2, question_count=0,
            questions=[],
        )))
    resp = client.get("/benchmarks/datasets/educational")
    assert resp.status_code == 200
    assert resp.json()["id"] == "educational"


def _run_response():
    metrics = BenchmarkMetrics()
    comparison = BenchmarkComparison(
        delta_precision_at_k=0.0, delta_recall_at_k=0.0, delta_mrr=0.0,
        graph_overhead_ms=0.0, expected_behavior="x",
    )
    return BenchmarkRunResponse(
        collection_id="c1", dataset_id="educational", dataset_name="N",
        top_k=5, graph_depth=2, baseline=metrics, kg_rag=metrics,
        comparison=comparison, results=[],
    )


def test_run_collection_benchmark(client, monkeypatch):
    captured = {}

    def fake_run(cls, *, db, collection_id, request, embedding_credentials):
        captured["creds"] = embedding_credentials
        captured["collection_id"] = collection_id
        return _run_response()

    monkeypatch.setattr(BenchmarkService, "run", classmethod(fake_run))
    resp = client.post(
        "/benchmarks/collections/c1/run",
        json={"dataset_id": "educational",
              "embedding_credentials": {"api_key": "sk-x", "api_endpoint": ""}},
    )
    assert resp.status_code == 200
    assert resp.json()["collection_id"] == "c1"
    assert captured["creds"] == {"api_key": "sk-x", "api_endpoint": ""}


def test_run_all_collection_benchmarks(client, monkeypatch):
    def fake_run_all(cls, *, db, collection_id, dataset_ids, threshold,
                     embedding_credentials):
        return BenchmarkRunAllResponse(
            collection_id=collection_id, runs=[], summary={"datasets": 0})

    monkeypatch.setattr(BenchmarkService, "run_all", classmethod(fake_run_all))
    resp = client.post(
        "/benchmarks/collections/c1/run-all",
        json={"dataset_ids": ["educational"], "threshold": 0.0,
              "embedding_credentials": {"api_key": "sk-x", "api_endpoint": ""}},
    )
    assert resp.status_code == 200
    assert resp.json()["collection_id"] == "c1"
