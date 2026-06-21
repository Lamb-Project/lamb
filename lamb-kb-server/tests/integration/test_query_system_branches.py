"""Branch tests for the query + system routers.

* ``query_collection`` surfacing ``question_entities`` at the top level when
  a KG-RAG trace is attached (router line, no live graph needed).
* ``GET /llm-vendors`` returning the registered extraction vendors.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from database.connection import get_session
from dependencies import verify_token
from plugins.base import QueryResult
from tests._helpers import AUTH_HEADERS


def test_query_surfaces_question_entities(monkeypatch):
    import routers.query as query_router
    from services import query_service

    # Result carries a KG-RAG trace -> the router lifts question_entities up.
    def fake_query(db, collection_id, body):
        return [QueryResult(
            text="hit", score=0.9,
            metadata={"kg_rag": {"question_entities": ["alpha", "beta"]}},
        )]

    monkeypatch.setattr(query_service, "query_collection", fake_query)

    app = FastAPI()
    app.include_router(query_router.router)
    app.dependency_overrides[verify_token] = lambda: "tok"
    app.dependency_overrides[get_session] = lambda: object()
    tc = TestClient(app)

    resp = tc.post("/collections/c1/query", json={"query_text": "what is alpha?"})
    assert resp.status_code == 200
    assert resp.json()["entities"] == ["alpha", "beta"]


def test_query_no_trace_entities_none(monkeypatch):
    import routers.query as query_router
    from services import query_service

    monkeypatch.setattr(
        query_service, "query_collection",
        lambda db, cid, body: [QueryResult(text="hit", score=0.9, metadata={})],
    )
    app = FastAPI()
    app.include_router(query_router.router)
    app.dependency_overrides[verify_token] = lambda: "tok"
    app.dependency_overrides[get_session] = lambda: object()
    resp = TestClient(app).post("/collections/c1/query", json={"query_text": "q"})
    assert resp.json()["entities"] is None


@pytest.mark.asyncio
async def test_list_llm_vendors_endpoint(client: AsyncClient):
    resp = await client.get("/llm-vendors", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "vendors" in resp.json()
