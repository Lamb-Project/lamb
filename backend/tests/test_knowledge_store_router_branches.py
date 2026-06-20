"""Branch/error-path tests for ``creator_interface.knowledge_store_router``.

Complements the happy-path integration tests by driving the error and edge
branches: validation/conflict/rollback on create, the KB-Server-failure
fallbacks on get/update/delete, the per-item ingestion guards in add_content,
and the best-effort teardown in remove_content. Uses the conftest fixtures
(``client``, ``ks_db``, ``ks_client``, ``ks_library_client``, ``async_*``).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import creator_interface.knowledge_store_router as ksr


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def test_build_permalinks_variants():
    # original_filename branch + pages branch.
    p = ksr._build_permalinks(1, "lib", "item", pages_count=2,
                              original_filename="f.pdf")
    assert p["full_markdown"] == "/docs/1/lib/item/content"
    assert p["original"] == "/docs/1/lib/item/original/f.pdf"
    assert p["pages"] == ["/docs/1/lib/item/content/pages/1",
                          "/docs/1/lib/item/content/pages/2"]
    # source_url branch (no filename).
    p2 = ksr._build_permalinks(1, "lib", "item", source_url="https://ext/x")
    assert p2["original"] == "https://ext/x"
    assert "pages" not in p2


def test_flatten_pages():
    payload = {"pages": [
        {"page_number": 1, "text": "a"},
        {"number": 2, "markdown": "b"},
        "not-a-dict",  # skipped
    ]}
    out = ksr._flatten_pages(payload)
    assert out == [
        {"page_number": 1, "text": "a"},
        {"page_number": 2, "text": "b"},
    ]
    assert ksr._flatten_pages({}) == []


# ---------------------------------------------------------------------------
# /options + /llm-vendors
# ---------------------------------------------------------------------------


def test_options_success(client, ks_client, async_return):
    ks_client.get_org_options = async_return({"vector_db_backends": []})
    resp = client.get("/creator/knowledge-stores/options")
    assert resp.status_code == 200


def test_options_unavailable_503(client, ks_client, async_raise):
    from creator_interface.knowledge_store_client import KnowledgeStoreUnavailable

    ks_client.get_org_options = async_raise(KnowledgeStoreUnavailable("down"))
    resp = client.get("/creator/knowledge-stores/options")
    assert resp.status_code == 503
    assert resp.json()["error"] == "knowledge_store_unavailable"


def test_llm_vendors(client, ks_client, async_return):
    ks_client.get_llm_vendors = async_return({"vendors": []})
    assert client.get("/creator/knowledge-stores/llm-vendors").status_code == 200


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def _create_body(**over):
    base = dict(
        name="KS", chunking_strategy="simple", embedding_vendor="openai",
        embedding_model="m", vector_db_backend="chromadb",
        embedding_endpoint="http://e",
    )
    base.update(over)
    return base


def test_create_validation_error_400(client, ks_client):
    ks_client.validate_against_allow_list.return_value = "vendor not allowed"
    resp = client.post("/creator/knowledge-stores", json=_create_body())
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"]


def test_create_conflict_409(client, ks_db, ks_client):
    ks_client.validate_against_allow_list.return_value = None
    ks_db.create_knowledge_store.return_value = None  # name taken
    resp = client.post("/creator/knowledge-stores", json=_create_body())
    assert resp.status_code == 409


def test_create_collection_failure_rolls_back_502(client, ks_db, ks_client, async_raise):
    ks_client.validate_against_allow_list.return_value = None
    ks_db.create_knowledge_store.return_value = True
    ks_client.create_collection = async_raise(RuntimeError("kb boom"))
    resp = client.post("/creator/knowledge-stores", json=_create_body())
    assert resp.status_code == 502
    ks_db.delete_knowledge_store.assert_called_once()


def test_create_success_resolves_endpoint(client, ks_db, ks_client, async_return,
                                          monkeypatch):
    import lamb.completions.org_config_resolver as ocr

    class _Resolver:
        def __init__(self, email):
            pass

        def get_provider_endpoint(self, vendor):
            return "http://org-endpoint"

    monkeypatch.setattr(ocr, "OrganizationConfigResolver", _Resolver)
    ks_client.validate_against_allow_list.return_value = None
    ks_db.create_knowledge_store.return_value = True
    ks_client.create_collection = async_return({})
    ks_db.get_knowledge_store.return_value = {"id": "ks1", "name": "KS"}
    # No endpoint supplied -> resolver fallback path.
    resp = client.post("/creator/knowledge-stores", json=_create_body(embedding_endpoint=None))
    assert resp.status_code == 200
    assert resp.json()["id"] == "ks1"


def test_create_endpoint_resolver_valueerror(client, ks_db, ks_client, async_return,
                                             monkeypatch):
    import lamb.completions.org_config_resolver as ocr

    class _Resolver:
        def __init__(self, email):
            pass

        def get_provider_endpoint(self, vendor):
            raise ValueError("no endpoint")

    monkeypatch.setattr(ocr, "OrganizationConfigResolver", _Resolver)
    ks_client.validate_against_allow_list.return_value = None
    ks_db.create_knowledge_store.return_value = True
    ks_client.create_collection = async_return({})
    ks_db.get_knowledge_store.return_value = {"id": "ks1"}
    resp = client.post("/creator/knowledge-stores", json=_create_body(embedding_endpoint=None))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_not_found_404(client, ks_db):
    ks_db.get_knowledge_store.return_value = None
    assert client.get("/creator/knowledge-stores/ks1").status_code == 404


def test_get_success_with_server_data(client, ks_db, ks_client, async_return):
    ks_db.get_knowledge_store.return_value = {"id": "ks1", "owner_user_id": 1}
    ks_client.get_collection = async_return({
        "status": "ready", "document_count": 3, "chunk_count": 9,
        "graph_enabled": True, "extraction": {"vendor": "openai"},
    })
    ks_db.get_kb_content_links_for_ks.return_value = []
    body = client.get("/creator/knowledge-stores/ks1").json()
    assert body["document_count"] == 3
    assert body["graph_enabled"] is True
    assert body["is_owner"] is True


def test_get_server_error_fallback(client, ks_db, ks_client, async_raise):
    ks_db.get_knowledge_store.return_value = {"id": "ks1", "owner_user_id": 2}
    ks_client.get_collection = async_raise(RuntimeError("kb down"))
    ks_db.get_kb_content_links_for_ks.return_value = []
    body = client.get("/creator/knowledge-stores/ks1").json()
    assert body["server_status"] is None
    assert body["graph_enabled"] is False


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_update_nothing_to_update_400(client):
    resp = client.put("/creator/knowledge-stores/ks1", json={})
    assert resp.status_code == 400


def test_update_success(client, ks_db, ks_client, async_return):
    ks_client.update_collection = async_return({})
    ks_db.update_knowledge_store.return_value = True
    ks_db.get_knowledge_store.return_value = {"id": "ks1", "name": "New"}
    resp = client.put("/creator/knowledge-stores/ks1", json={"name": "New"})
    assert resp.status_code == 200


def test_update_collection_404_is_swallowed(client, ks_db, ks_client, async_raise):
    ks_client.update_collection = async_raise(HTTPException(404, "missing"))
    ks_db.update_knowledge_store.return_value = True
    ks_db.get_knowledge_store.return_value = {"id": "ks1"}
    resp = client.put("/creator/knowledge-stores/ks1", json={"description": "d"})
    assert resp.status_code == 200


def test_update_collection_other_error_propagates(client, ks_client, async_raise):
    ks_client.update_collection = async_raise(HTTPException(500, "boom"))
    resp = client.put("/creator/knowledge-stores/ks1", json={"name": "x"})
    assert resp.status_code == 500


def test_update_db_missing_404(client, ks_db, ks_client, async_return):
    ks_client.update_collection = async_return({})
    ks_db.update_knowledge_store.return_value = False
    resp = client.put("/creator/knowledge-stores/ks1", json={"name": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_success(client, ks_db, ks_client, async_return):
    ks_client.delete_collection = async_return({})
    resp = client.delete("/creator/knowledge-stores/ks1")
    assert resp.status_code == 200
    ks_db.delete_knowledge_store.assert_called_once()


def test_delete_collection_404_proceeds(client, ks_db, ks_client, async_raise):
    ks_client.delete_collection = async_raise(HTTPException(404, "gone"))
    resp = client.delete("/creator/knowledge-stores/ks1")
    assert resp.status_code == 200


def test_delete_collection_5xx_502(client, ks_client, async_raise):
    ks_client.delete_collection = async_raise(HTTPException(503, "down"))
    resp = client.delete("/creator/knowledge-stores/ks1")
    assert resp.status_code == 502


def test_delete_collection_4xx_propagates(client, ks_client, async_raise):
    ks_client.delete_collection = async_raise(HTTPException(403, "forbidden"))
    resp = client.delete("/creator/knowledge-stores/ks1")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# share + list content
# ---------------------------------------------------------------------------


def test_toggle_sharing_on_and_off(client, ks_db):
    on = client.put("/creator/knowledge-stores/ks1/share", json={"is_shared": True})
    assert on.json()["is_shared"] is True
    off = client.put("/creator/knowledge-stores/ks1/share", json={"is_shared": False})
    assert "private" in off.json()["message"]


def test_list_knowledge_stores(client, ks_db):
    ks_db.get_accessible_knowledge_stores.return_value = [{"id": "ks1"}]
    body = client.get("/creator/knowledge-stores").json()
    assert body["knowledge_stores"][0]["id"] == "ks1"


def test_list_ks_content(client, ks_db):
    ks_db.get_kb_content_links_for_ks.return_value = [
        {"library_item_id": "i1", "status": "ready"},
    ]
    body = client.get("/creator/knowledge-stores/ks1/content").json()
    assert body["items"][0]["library_item_id"] == "i1"


# ---------------------------------------------------------------------------
# add_content
# ---------------------------------------------------------------------------


def _add_body(item_ids=None):
    return {"library_id": "lib1", "item_ids": item_ids or ["i1"]}


def test_add_content_ks_not_found(client, ks_db):
    ks_db.get_knowledge_store.return_value = None
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.status_code == 404


def test_add_content_library_not_found(client, ks_db, ks_client):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai"}
    ks_db.get_library.return_value = None
    ks_client.resolve_embedding_api_key.return_value = "sk"
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.status_code == 404


def test_add_content_org_mismatch_403(client, ks_db, ks_client):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai"}
    ks_db.get_library.return_value = {"organization_id": 2}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.status_code == 403


def test_add_content_all_already_linked_noop(client, ks_db, ks_client):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai"}
    ks_db.get_library.return_value = {"organization_id": 1, "name": "Lib"}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    ks_db.get_kb_content_link.return_value = {"status": "ready"}
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.json()["status"] == "noop"


def test_add_content_item_fetch_error_400(client, ks_db, ks_client, ks_library_client,
                                          async_raise):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai"}
    ks_db.get_library.return_value = {"organization_id": 1, "name": "Lib"}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    ks_db.get_kb_content_link.return_value = None
    ks_library_client.get_item = async_raise(HTTPException(404, "no item"))
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.status_code == 400


def test_add_content_item_not_ready_409(client, ks_db, ks_client, ks_library_client,
                                        async_return):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai"}
    ks_db.get_library.return_value = {"organization_id": 1, "name": "Lib"}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    ks_db.get_kb_content_link.return_value = None
    ks_library_client.get_item = async_return({"status": "processing"})
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.status_code == 409


def test_add_content_empty_text_400(client, ks_db, ks_client, ks_library_client,
                                    async_return):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai"}
    ks_db.get_library.return_value = {"organization_id": 1, "name": "Lib"}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    ks_db.get_kb_content_link.return_value = None
    ks_library_client.get_item = async_return({"status": "ready", "title": "T"})

    class _Resp:
        text = ""

    ks_library_client.proxy_content = async_return(_Resp())
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.status_code == 400


def test_add_content_proxy_content_error_400(client, ks_db, ks_client, ks_library_client,
                                             async_return, async_raise):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai"}
    ks_db.get_library.return_value = {"organization_id": 1, "name": "Lib"}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    ks_db.get_kb_content_link.return_value = None
    ks_library_client.get_item = async_return({"status": "ready", "title": "T"})
    ks_library_client.proxy_content = async_raise(HTTPException(404, "no content"))
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.status_code == 400


def test_add_content_bad_page_count_defaults_zero(client, ks_db, ks_client,
                                                  ks_library_client, async_return):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai",
                                              "embedding_endpoint": ""}
    ks_db.get_library.return_value = {"organization_id": 1, "name": "Lib"}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    ks_db.get_kb_content_link.return_value = None
    # page_count is non-numeric -> the int() guard falls back to 0.
    ks_library_client.get_item = async_return(
        {"status": "ready", "title": "Doc", "page_count": "not-a-number"})

    class _Resp:
        text = "content"

    ks_library_client.proxy_content = async_return(_Resp())
    ks_client.add_content = async_return({"job_id": "j", "status": "processing"})
    ks_db.register_kb_content_link.return_value = 1
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.status_code == 200


def test_add_content_success_registers_links(client, ks_db, ks_client, ks_library_client,
                                             async_return):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai",
                                              "embedding_endpoint": ""}
    ks_db.get_library.return_value = {"organization_id": 1, "name": "Lib"}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    ks_db.get_kb_content_link.return_value = None
    ks_library_client.get_item = async_return(
        {"status": "ready", "title": "Doc", "page_count": 2,
         "original_filename": "f.pdf"})

    class _Resp:
        text = "real content"

    ks_library_client.proxy_content = async_return(_Resp())
    ks_client.add_content = async_return({"job_id": "job1", "status": "processing",
                                          "documents_total": 1})
    ks_db.register_kb_content_link.return_value = 99
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    body = resp.json()
    assert body["job_id"] == "job1"
    assert body["links"][0]["id"] == 99


def test_add_content_ingestion_failure_502(client, ks_db, ks_client, ks_library_client,
                                           async_return, async_raise):
    ks_db.get_knowledge_store.return_value = {"organization_id": 1, "embedding_vendor": "openai",
                                              "embedding_endpoint": ""}
    ks_db.get_library.return_value = {"organization_id": 1, "name": "Lib"}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    ks_db.get_kb_content_link.return_value = None
    ks_library_client.get_item = async_return({"status": "ready", "title": "Doc"})

    class _Resp:
        text = "content"

    ks_library_client.proxy_content = async_return(_Resp())
    ks_client.add_content = async_raise(HTTPException(500, "ingest boom"))
    resp = client.post("/creator/knowledge-stores/ks1/content", json=_add_body())
    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# get_content_link / remove_content
# ---------------------------------------------------------------------------


def test_get_content_link_404(client, ks_db):
    ks_db.get_kb_content_link.return_value = None
    resp = client.get("/creator/knowledge-stores/ks1/content/i1")
    assert resp.status_code == 404


def test_get_content_link_polls_job(client, ks_db, ks_client, async_return):
    ks_db.get_kb_content_link.side_effect = [
        {"id": 1, "status": "processing", "kb_job_id": "job1"},
        {"id": 1, "status": "ready", "kb_job_id": "job1"},
    ]
    ks_client.get_job_status = async_return({"status": "completed", "chunks_created": 5})
    body = client.get("/creator/knowledge-stores/ks1/content/i1").json()
    assert body["status"] == "ready"


def test_get_content_link_poll_failure_warns(client, ks_db, ks_client, async_raise):
    ks_db.get_kb_content_link.return_value = {"id": 1, "status": "processing",
                                             "kb_job_id": "job1"}
    ks_client.get_job_status = async_raise(RuntimeError("poll boom"))
    # Returns the (unchanged) link despite the poll failure.
    body = client.get("/creator/knowledge-stores/ks1/content/i1").json()
    assert body["status"] == "processing"


def test_remove_content_404(client, ks_db):
    ks_db.get_kb_content_link.return_value = None
    resp = client.delete("/creator/knowledge-stores/ks1/content/i1")
    assert resp.status_code == 404


def test_remove_content_success_cancels_inflight(client, ks_db, ks_client, async_return):
    ks_db.get_kb_content_link.return_value = {"id": 1, "status": "processing",
                                             "kb_job_id": "job1"}
    ks_client.cancel_job = async_return({})
    ks_client.delete_content_by_source = async_return({})
    resp = client.delete("/creator/knowledge-stores/ks1/content/i1")
    assert resp.status_code == 200
    ks_db.delete_kb_content_link.assert_called_once()


def test_remove_content_cancel_job_failure_warns(client, ks_db, ks_client,
                                                 async_return, async_raise):
    ks_db.get_kb_content_link.return_value = {"id": 1, "status": "pending",
                                             "kb_job_id": "job1"}
    # cancel_job raises -> warning, but teardown proceeds.
    ks_client.cancel_job = async_raise(RuntimeError("cancel boom"))
    ks_client.delete_content_by_source = async_return({})
    resp = client.delete("/creator/knowledge-stores/ks1/content/i1")
    assert resp.status_code == 200
    ks_db.delete_kb_content_link.assert_called_once()


def test_remove_content_delete_best_effort_5xx(client, ks_db, ks_client, async_raise):
    ks_db.get_kb_content_link.return_value = {"id": 1, "status": "ready", "kb_job_id": None}
    ks_client.delete_content_by_source = async_raise(HTTPException(503, "down"))
    # Best-effort: link still torn down, returns 200.
    resp = client.delete("/creator/knowledge-stores/ks1/content/i1")
    assert resp.status_code == 200


def test_remove_content_delete_4xx_propagates(client, ks_db, ks_client, async_raise):
    ks_db.get_kb_content_link.return_value = {"id": 1, "status": "ready", "kb_job_id": None}
    ks_client.delete_content_by_source = async_raise(HTTPException(403, "forbidden"))
    resp = client.delete("/creator/knowledge-stores/ks1/content/i1")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# query + job status
# ---------------------------------------------------------------------------


def test_query_not_found_404(client, ks_db):
    ks_db.get_knowledge_store.return_value = None
    resp = client.post("/creator/knowledge-stores/ks1/query", json={"query_text": "q"})
    assert resp.status_code == 404


def test_query_success(client, ks_db, ks_client, async_return):
    ks_db.get_knowledge_store.return_value = {"embedding_vendor": "openai", "embedding_endpoint": ""}
    ks_client.resolve_embedding_api_key.return_value = "sk"
    ks_client.query = async_return({"results": [{"text": "hit"}]})
    body = client.post("/creator/knowledge-stores/ks1/query",
                       json={"query_text": "q", "top_k": 3}).json()
    assert body["results"][0]["text"] == "hit"


def test_job_status_syncs_links(client, ks_db, ks_client, async_return):
    ks_client.get_job_status = async_return({"status": "completed", "chunks_created": 7})
    ks_db.get_kb_content_links_for_ks.return_value = [
        {"id": 1, "kb_job_id": "job1", "status": "processing"},
    ]
    body = client.get("/creator/knowledge-stores/ks1/jobs/job1").json()
    assert body["status"] == "completed"
    ks_db.update_kb_content_link_status.assert_called_once()
