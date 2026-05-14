"""Integration tests for ``/creator/knowledge-stores/*`` Creator routes.

These tests mount the real ``knowledge_store_router`` on a minimal
FastAPI app. ``KnowledgeStoreClient`` and ``LibraryManagerClient`` and
the LAMB DB singleton are stubbed via fixtures from ``conftest.py``.

Per ADR-KS-5 the locked fields (chunking, embedding vendor/model, vector
DB backend) cannot be modified after creation, so the update test
specifically verifies the API surface only accepts ``name`` /
``description``. Validation against the org allow-list happens at
``KnowledgeStoreClient.validate_against_allow_list`` — this is mocked
per test to either pass-through or return an error string.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import patch, AsyncMock

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ks_row(
    ks_id: str = "ks-1",
    name: str = "My KS",
    owner_user_id: int = 1,
    organization_id: int = 1,
    chunking_strategy: str = "simple",
    embedding_vendor: str = "ollama",
    embedding_model: str = "nomic-embed-text",
    vector_db_backend: str = "chromadb",
    embedding_endpoint: str = "http://172.18.0.1:11434/api/embeddings",
    description: str = "",
    status: str = "active",
) -> Dict[str, Any]:
    return {
        "id": ks_id,
        "name": name,
        "description": description,
        "owner_user_id": owner_user_id,
        "organization_id": organization_id,
        "chunking_strategy": chunking_strategy,
        "embedding_vendor": embedding_vendor,
        "embedding_model": embedding_model,
        "vector_db_backend": vector_db_backend,
        "embedding_endpoint": embedding_endpoint,
        "status": status,
        "is_shared": False,
        "created_at": 0,
        "updated_at": 0,
    }


# ---------------------------------------------------------------------------
# GET /creator/knowledge-stores/options  (D1 regression-adjacent)
# ---------------------------------------------------------------------------


def test_options_returns_org_endpoint_override(client, ks_client, async_return):
    """The org's ollama endpoint must be returned as the api_endpoint default
    when the org has ``providers.ollama.endpoint`` configured."""
    payload = {
        "vector_db_backends": [{"name": "chromadb"}],
        "chunking_strategies": [{"name": "simple"}],
        "embedding_vendors": [
            {
                "name": "ollama",
                "parameters": [
                    {"name": "model", "default": "nomic-embed-text"},
                    {
                        "name": "api_endpoint",
                        "default": "http://172.18.0.1:11434",
                    },
                ],
            }
        ],
        "embedding_models": {},
    }
    ks_client.get_org_options = async_return(payload)

    response = client.get("/creator/knowledge-stores/options")

    assert response.status_code == 200
    body = response.json()
    ollama = next(v for v in body["embedding_vendors"] if v["name"] == "ollama")
    api_endpoint = next(p for p in ollama["parameters"] if p["name"] == "api_endpoint")
    assert api_endpoint["default"] == "http://172.18.0.1:11434"


def test_options_falls_back_to_plugin_default(client, ks_client, async_return):
    """When the org has no ollama endpoint configured, the plugin's static
    default (``localhost``) must be preserved unchanged."""
    payload = {
        "vector_db_backends": [],
        "chunking_strategies": [],
        "embedding_vendors": [
            {
                "name": "ollama",
                "parameters": [
                    {
                        "name": "api_endpoint",
                        "default": "http://localhost:11434/api/embeddings",
                    }
                ],
            }
        ],
        "embedding_models": {},
    }
    ks_client.get_org_options = async_return(payload)

    response = client.get("/creator/knowledge-stores/options")
    assert response.status_code == 200
    ollama = next(
        v for v in response.json()["embedding_vendors"] if v["name"] == "ollama"
    )
    api_endpoint = next(p for p in ollama["parameters"] if p["name"] == "api_endpoint")
    assert api_endpoint["default"] == "http://localhost:11434/api/embeddings"


# ---------------------------------------------------------------------------
# POST /creator/knowledge-stores
# ---------------------------------------------------------------------------


def test_create_ks_happy_path(client, ks_db, ks_client, async_return):
    """Valid body -> 200, LAMB row inserted (provisional then promoted)."""
    ks_client.validate_against_allow_list.return_value = None  # no error
    ks_client.create_collection = async_return({"id": "ks-1"})
    ks_db.create_knowledge_store.return_value = "ks-1"
    ks_db.update_knowledge_store_status.return_value = True
    ks_db.get_knowledge_store.return_value = _ks_row(ks_id="ks-1", name="Bio KS")

    response = client.post(
        "/creator/knowledge-stores",
        json={
            "name": "Bio KS",
            "description": "Biology references",
            "chunking_strategy": "simple",
            "embedding_vendor": "ollama",
            "embedding_model": "nomic-embed-text",
            "vector_db_backend": "chromadb",
            "embedding_endpoint": "http://172.18.0.1:11434",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Bio KS"

    create_kwargs = ks_db.create_knowledge_store.call_args.kwargs
    assert create_kwargs["status"] == "provisional"
    assert create_kwargs["embedding_vendor"] == "ollama"
    assert create_kwargs["chunking_strategy"] == "simple"
    ks_db.update_knowledge_store_status.assert_called_once()


def test_create_ks_invalid_chunking_returns_400(client, ks_db, ks_client):
    """Allow-list validation rejects unknown chunking strategies with 400."""
    ks_client.validate_against_allow_list.return_value = (
        "Chunking strategy 'fancy' is not allowed for this organization."
    )

    response = client.post(
        "/creator/knowledge-stores",
        json={
            "name": "Bad KS",
            "chunking_strategy": "fancy",
            "embedding_vendor": "ollama",
            "embedding_model": "nomic-embed-text",
            "vector_db_backend": "chromadb",
        },
    )

    assert response.status_code == 400
    assert "fancy" in response.json()["detail"]
    ks_db.create_knowledge_store.assert_not_called()


# ---------------------------------------------------------------------------
# PUT /creator/knowledge-stores/{ks_id}
# ---------------------------------------------------------------------------


def test_update_ks_name_succeeds(client, ks_db, ks_client, async_return):
    """Name update is mutable per ADR-KS-5."""
    ks_db.update_knowledge_store.return_value = True
    ks_db.get_knowledge_store.return_value = _ks_row(name="New Name")
    ks_client.update_collection = async_return({})

    response = client.put(
        "/creator/knowledge-stores/ks-1",
        json={"name": "New Name"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    ks_db.update_knowledge_store.assert_called_once_with(
        "ks-1", name="New Name", description=None, chunking_params=None
    )


def test_update_ks_locked_chunking_field_is_rejected(client, ks_db, ks_client):
    """``chunking_strategy`` is locked — pydantic ``KnowledgeStoreUpdate``
    only accepts ``name`` and ``description``, so attempting to send other
    fields is silently ignored. Sending ONLY a locked field with no
    ``name``/``description`` => 400 ("Nothing to update")."""
    response = client.put(
        "/creator/knowledge-stores/ks-1",
        json={"chunking_strategy": "by_page"},
    )

    assert response.status_code == 400
    assert "nothing to update" in response.json()["detail"].lower()
    ks_db.update_knowledge_store.assert_not_called()


# ---------------------------------------------------------------------------
# POST /creator/knowledge-stores/{ks_id}/content
# ---------------------------------------------------------------------------


def _wire_add_content_happy(
    ks_db, ks_client, ks_library_client, async_return,
    *, existing_link=None,
):
    """Common wiring for /content tests."""
    ks_db.get_knowledge_store.return_value = _ks_row()
    ks_db.get_library.return_value = {
        "id": "lib-1",
        "name": "Course",
        "organization_id": 1,
        "owner_user_id": 1,
        "is_shared": False,
        "status": "active",
    }
    ks_client.resolve_embedding_api_key.return_value = ""
    ks_db.get_kb_content_link.return_value = existing_link
    ks_db.register_kb_content_link.return_value = 42

    ks_library_client.get_item = async_return(
        {"item_id": "item-1", "title": "Doc 1", "status": "ready"}
    )

    # proxy_content is called twice: once for content, once for pages.
    proxy_responses = [
        type("R", (), {"text": "the document text", "content": b""})(),  # markdown
        type("R", (), {"content": b'{"count": 0}', "text": ""})(),  # pages json
    ]

    async def _proxy(*args, **kwargs):
        return proxy_responses.pop(0)

    ks_library_client.proxy_content = _proxy

    ks_client.add_content = async_return(
        {"job_id": "job-1", "status": "processing", "documents_total": 1}
    )


def test_add_content_happy_path(
    client, ks_db, ks_client, ks_library_client, async_return
):
    """Happy path -> 200/202 with job_id, link registered with status='processing'."""
    _wire_add_content_happy(ks_db, ks_client, ks_library_client, async_return)

    response = client.post(
        "/creator/knowledge-stores/ks-1/content",
        json={"library_id": "lib-1", "item_ids": ["item-1"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-1"
    assert body["status"] == "processing"

    ks_db.register_kb_content_link.assert_called_once()
    register_kwargs = ks_db.register_kb_content_link.call_args.kwargs
    assert register_kwargs["status"] == "processing"
    assert register_kwargs["library_item_id"] == "item-1"


def test_add_content_already_linked_is_idempotent(
    client, ks_db, ks_client, ks_library_client, async_return
):
    """Re-linking an item that's already in the KS does NOT create a duplicate
    row — the existing link is detected and skipped."""
    existing = {
        "id": 99,
        "knowledge_store_id": "ks-1",
        "library_item_id": "item-1",
        "status": "ready",
    }
    _wire_add_content_happy(
        ks_db, ks_client, ks_library_client, async_return,
        existing_link=existing,
    )

    response = client.post(
        "/creator/knowledge-stores/ks-1/content",
        json={"library_id": "lib-1", "item_ids": ["item-1"]},
    )

    assert response.status_code == 200
    body = response.json()
    # The router returns a noop when no new docs need ingesting.
    assert body["status"] == "noop"
    assert body["job_id"] is None

    # The link wasn't re-registered (no duplicate).
    ks_db.register_kb_content_link.assert_not_called()


# ---------------------------------------------------------------------------
# GET /creator/knowledge-stores/{ks_id}/jobs/{job_id}
# ---------------------------------------------------------------------------


def test_get_job_status_proxies_kb_server(client, ks_db, ks_client, async_return):
    """Job-status endpoint proxies the KB Server response and syncs links."""
    ks_client.get_job_status = async_return(
        {"job_id": "job-1", "status": "completed", "chunks_created": 5}
    )
    ks_db.get_kb_content_links_for_ks.return_value = [
        {"id": 42, "kb_job_id": "job-1", "status": "processing"}
    ]
    ks_db.update_kb_content_link_status.return_value = True

    response = client.get("/creator/knowledge-stores/ks-1/jobs/job-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"

    # Linked rows were synced to status 'ready' (mapped from 'completed').
    update_kwargs = ks_db.update_kb_content_link_status.call_args.kwargs
    assert update_kwargs["status"] == "ready"
    assert update_kwargs["chunks_created"] == 5


# ---------------------------------------------------------------------------
# POST /creator/knowledge-stores/{ks_id}/query
# ---------------------------------------------------------------------------


def test_query_empty_text_returns_422(client, ks_db, ks_client):
    """Empty ``query_text`` is rejected by the pydantic validator (min_length=1)."""
    response = client.post(
        "/creator/knowledge-stores/ks-1/query",
        json={"query_text": "", "top_k": 5},
    )
    assert response.status_code == 422


def test_query_happy_path_returns_chunks(client, ks_db, ks_client, async_return):
    """Query returns chunk rows including permalinks in metadata."""
    ks_db.get_knowledge_store.return_value = _ks_row()
    ks_client.resolve_embedding_api_key.return_value = "fake-key"
    ks_client.query = async_return(
        {
            "chunks": [
                {
                    "text": "mitochondria are the powerhouse",
                    "permalinks": {"original": "/docs/1/lib-1/item-1/content"},
                    "score": 0.92,
                }
            ]
        }
    )

    response = client.post(
        "/creator/knowledge-stores/ks-1/query",
        json={"query_text": "what are mitochondria", "top_k": 3},
    )

    assert response.status_code == 200
    chunks = response.json()["chunks"]
    assert len(chunks) == 1
    assert "permalinks" in chunks[0]
    assert chunks[0]["permalinks"]["original"].startswith("/docs/")


# ---------------------------------------------------------------------------
# DELETE /creator/knowledge-stores/{ks_id}
# ---------------------------------------------------------------------------


def test_delete_ks_cascades_to_kb_server(client, ks_db, ks_client):
    """Deleting a KS calls the KB Server first, then deletes the LAMB row."""
    ks_client.delete_collection = AsyncMock(return_value={"status": "deleted"})
    ks_db.delete_knowledge_store.return_value = True

    response = client.delete("/creator/knowledge-stores/ks-1")

    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()

    # The downstream delete must have been called exactly once.
    ks_client.delete_collection.assert_called_once()
    ks_db.delete_knowledge_store.assert_called_once_with("ks-1")
