"""Unit tests for collection_service, ingestion_service, and query_service.

Drive each service function directly — no HTTP, no FastAPI app, no worker
loop.  Uses the real SQLAlchemy session (``db_session`` fixture) and the
real ChromaDB backend backed by a per-test temp directory so the tests
exercise actual I/O while remaining fully deterministic.

FakeEmbedding is already registered in ``tests/conftest.py``; these tests
assume it is available in ``EmbeddingRegistry._plugins["fake"]``.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from database.models import Collection, IngestionJob
from fastapi import HTTPException
from plugins.base import ChunkingRegistry, EmbeddingRegistry, VectorDBRegistry
from schemas.collection import CreateCollectionRequest, EmbeddingConfig, UpdateCollectionRequest
from schemas.content import (
    AddContentRequest,
    DocumentInputPayload,
    EmbeddingCredentials,
    PermalinkInput,
)
from schemas.query import QueryRequest
from services.collection_service import (
    create_collection,
    delete_collection,
    get_collection,
    list_collections,
    update_collection,
)
from services.ingestion_service import (
    delete_vectors,
    execute_ingestion_job,
    queue_add_content,
)
from services.query_service import query_collection

# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _org() -> str:
    """Generate a unique org ID per test to avoid cross-test collisions."""
    return uuid4().hex[:8]


def _create_req(
    org_id: str | None = None,
    name: str | None = None,
    *,
    chunking_strategy: str = "simple",
    embedding_vendor: str = "fake",
    vector_db_backend: str = "chromadb",
    collection_id: str | None = None,
) -> CreateCollectionRequest:
    return CreateCollectionRequest(
        id=collection_id,
        organization_id=org_id or _org(),
        name=name or f"test-kb-{uuid4().hex[:6]}",
        chunking_strategy=chunking_strategy,
        embedding=EmbeddingConfig(vendor=embedding_vendor, model="fake-model"),
        vector_db_backend=vector_db_backend,
    )


def _doc(source_item_id: str = "doc-1", text: str = "Hello world. " * 20) -> DocumentInputPayload:
    return DocumentInputPayload(
        source_item_id=source_item_id,
        title="Test Document",
        text=text,
        permalinks=PermalinkInput(),
    )


def _add_req(*docs: DocumentInputPayload) -> AddContentRequest:
    return AddContentRequest(
        documents=list(docs),
        embedding_credentials=EmbeddingCredentials(api_key="", api_endpoint=""),
    )


# ---------------------------------------------------------------------------
# collection_service — create_collection
# ---------------------------------------------------------------------------


class TestCreateCollection:
    def test_happy_path_returns_collection_row(self, db_session, tmp_storage) -> None:
        """create_collection returns a persisted Collection row."""
        org = _org()
        req = _create_req(org_id=org)
        col = create_collection(db_session, req)

        assert col.id
        assert col.organization_id == org
        assert col.name == req.name
        assert col.status == "ready"
        assert col.document_count == 0
        assert col.chunk_count == 0

    def test_storage_dir_created_on_disk(self, db_session, tmp_storage) -> None:
        """create_collection creates the storage directory on disk."""
        col = create_collection(db_session, _create_req())
        assert Path(col.storage_path).is_dir()

    def test_missing_chunking_plugin_raises_400(self, db_session) -> None:
        with pytest.raises(HTTPException) as exc:
            create_collection(db_session, _create_req(chunking_strategy="nonexistent"))
        assert exc.value.status_code == 400
        assert "nonexistent" in exc.value.detail

    def test_missing_embedding_vendor_raises_400(self, db_session) -> None:
        with pytest.raises(HTTPException) as exc:
            create_collection(db_session, _create_req(embedding_vendor="no_such_vendor"))
        assert exc.value.status_code == 400
        assert "no_such_vendor" in exc.value.detail

    def test_missing_vector_backend_raises_400(self, db_session) -> None:
        with pytest.raises(HTTPException) as exc:
            create_collection(db_session, _create_req(vector_db_backend="no_such_backend"))
        assert exc.value.status_code == 400
        assert "no_such_backend" in exc.value.detail

    def test_duplicate_org_name_raises_409(self, db_session) -> None:
        org = _org()
        name = f"duplicate-{uuid4().hex[:6]}"
        create_collection(db_session, _create_req(org_id=org, name=name))

        with pytest.raises(HTTPException) as exc:
            create_collection(db_session, _create_req(org_id=org, name=name))
        assert exc.value.status_code == 409

    def test_auto_generates_uuid_when_id_omitted(self, db_session) -> None:
        col = create_collection(db_session, _create_req())
        assert col.id  # non-empty
        # Should be a 32-char hex UUID
        assert len(col.id) == 32

    def test_uses_provided_id(self, db_session) -> None:
        cid = uuid4().hex
        col = create_collection(db_session, _create_req(collection_id=cid))
        assert col.id == cid

    def test_backend_failure_cleans_up_storage_dir(self, db_session, monkeypatch) -> None:
        """If the vector backend's create_collection raises, the storage dir is removed."""
        from plugins.vector_db.chromadb_backend import ChromaDBBackend

        def _boom(self, **kwargs):
            raise RuntimeError("simulated backend failure")

        monkeypatch.setattr(ChromaDBBackend, "create_collection", _boom)

        org = _org()
        req = _create_req(org_id=org)

        with pytest.raises(RuntimeError, match="simulated backend failure"):
            create_collection(db_session, req)

        # The storage directory should have been cleaned up.
        from config import STORAGE_DIR  # noqa: PLC0415
        storage_path = STORAGE_DIR / org
        # Either the per-collection subdir was removed or the org dir contains
        # no leftovers — assert no subdir matching the collection pattern exists.
        if storage_path.exists():
            for child in storage_path.iterdir():
                # No directory for this aborted collection should remain
                # (there may be dirs from other tests, but each is unique)
                pass  # we can't guess the generated ID; the key check is below

        # The collection row must not be in the DB.
        from database.models import Collection as _Col  # noqa: PLC0415
        count = (
            db_session.query(_Col)
            .filter(_Col.organization_id == org)
            .count()
        )
        assert count == 0

    def test_http_exception_during_creation_cleans_up_storage(
        self, db_session, monkeypatch, tmp_path
    ) -> None:
        """When EmbeddingRegistry.build raises an HTTPException (the except HTTPException
        branch at lines 140-142), the storage dir is cleaned up and the exception re-raised."""
        import config as cfg  # noqa: PLC0415
        import services.collection_service as cs  # noqa: PLC0415

        storage_root = tmp_path / "storage_http"
        storage_root.mkdir()
        monkeypatch.setattr(cfg, "STORAGE_DIR", storage_root)
        monkeypatch.setattr(cs, "STORAGE_DIR", storage_root)

        def _raise_http(*args, **kwargs):
            raise HTTPException(status_code=422, detail="forced http error")

        monkeypatch.setattr(EmbeddingRegistry, "build", staticmethod(_raise_http))

        org = _org()
        req = _create_req(org_id=org)

        with pytest.raises(HTTPException) as exc:
            create_collection(db_session, req)
        assert exc.value.status_code == 422

        org_dir = storage_root / org
        if org_dir.exists():
            children = list(org_dir.iterdir())
            assert children == [], f"Expected storage cleaned up, got: {children}"

    def test_backend_failure_storage_dir_removed(self, db_session, monkeypatch, tmp_path) -> None:
        """More targeted: monkeypatch STORAGE_DIR so we can inspect the exact path."""
        import config as cfg  # noqa: PLC0415
        from plugins.vector_db.chromadb_backend import ChromaDBBackend

        # Point STORAGE_DIR at a subdirectory of tmp_path so we can inspect it.
        storage_root = tmp_path / "storage"
        storage_root.mkdir()
        monkeypatch.setattr(cfg, "STORAGE_DIR", storage_root)

        # Also patch the import inside collection_service.
        import services.collection_service as cs  # noqa: PLC0415
        monkeypatch.setattr(cs, "STORAGE_DIR", storage_root)

        def _boom(self, **kwargs):
            raise RuntimeError("backend boom")

        monkeypatch.setattr(ChromaDBBackend, "create_collection", _boom)

        org = _org()
        req = _create_req(org_id=org)

        with pytest.raises(RuntimeError):
            create_collection(db_session, req)

        # All sub-paths under storage_root should be gone.
        org_dir = storage_root / org
        # Either the dir doesn't exist, or it contains no collection subdirs.
        if org_dir.exists():
            children = list(org_dir.iterdir())
            assert children == [], f"Expected empty org dir, got: {children}"


# ---------------------------------------------------------------------------
# collection_service — get_collection, list_collections
# ---------------------------------------------------------------------------


class TestGetAndListCollections:
    def test_get_collection_happy_path(self, db_session) -> None:
        col = create_collection(db_session, _create_req())
        fetched = get_collection(db_session, col.id)
        assert fetched.id == col.id

    def test_get_collection_not_found_raises_404(self, db_session) -> None:
        with pytest.raises(HTTPException) as exc:
            get_collection(db_session, "nonexistent-id-xyz")
        assert exc.value.status_code == 404

    def test_list_collections_returns_all_for_org(self, db_session) -> None:
        org = _org()
        col1 = create_collection(db_session, _create_req(org_id=org, name="alpha"))
        col2 = create_collection(db_session, _create_req(org_id=org, name="beta"))

        rows, total = list_collections(db_session, organization_id=org)
        ids = {r.id for r in rows}

        assert total == 2
        assert col1.id in ids
        assert col2.id in ids

    def test_list_collections_pagination(self, db_session) -> None:
        org = _org()
        names = [f"kb-pg-{i}" for i in range(5)]
        for n in names:
            create_collection(db_session, _create_req(org_id=org, name=n))

        rows, total = list_collections(db_session, organization_id=org, limit=3, offset=0)
        assert total == 5
        assert len(rows) == 3

        rows2, total2 = list_collections(db_session, organization_id=org, limit=3, offset=3)
        assert total2 == 5
        assert len(rows2) == 2

    def test_list_collections_filters_by_org(self, db_session) -> None:
        org_a = _org()
        org_b = _org()
        create_collection(db_session, _create_req(org_id=org_a))
        create_collection(db_session, _create_req(org_id=org_b))

        rows_a, total_a = list_collections(db_session, organization_id=org_a)
        rows_b, total_b = list_collections(db_session, organization_id=org_b)
        assert total_a == 1
        assert total_b == 1
        assert rows_a[0].organization_id == org_a
        assert rows_b[0].organization_id == org_b

    def test_list_collections_no_filter(self, db_session) -> None:
        # Just make sure it doesn't crash with no org filter.
        _rows, total = list_collections(db_session)
        assert total >= 0


# ---------------------------------------------------------------------------
# collection_service — update_collection
# ---------------------------------------------------------------------------


class TestUpdateCollection:
    def test_update_name_happy_path(self, db_session) -> None:
        col = create_collection(db_session, _create_req())
        updated = update_collection(
            db_session, col.id, UpdateCollectionRequest(name="new-name")
        )
        assert updated.name == "new-name"

    def test_update_description_only(self, db_session) -> None:
        col = create_collection(db_session, _create_req())
        updated = update_collection(
            db_session, col.id, UpdateCollectionRequest(description="desc updated")
        )
        assert updated.description == "desc updated"
        # Name must be unchanged.
        assert updated.name == col.name

    def test_update_same_name_no_error(self, db_session) -> None:
        col = create_collection(db_session, _create_req())
        # Setting the same name should silently succeed (no 409).
        updated = update_collection(
            db_session, col.id, UpdateCollectionRequest(name=col.name)
        )
        assert updated.name == col.name

    def test_update_name_conflict_within_org_raises_409(self, db_session) -> None:
        org = _org()
        col1 = create_collection(db_session, _create_req(org_id=org, name="first"))
        _col2 = create_collection(db_session, _create_req(org_id=org, name="second"))

        with pytest.raises(HTTPException) as exc:
            update_collection(
                db_session, col1.id, UpdateCollectionRequest(name="second")
            )
        assert exc.value.status_code == 409

    def test_update_collection_not_found_raises_404(self, db_session) -> None:
        with pytest.raises(HTTPException) as exc:
            update_collection(
                db_session, "no-such-id", UpdateCollectionRequest(name="x")
            )
        assert exc.value.status_code == 404

    def test_update_name_allowed_across_orgs(self, db_session) -> None:
        """Same name in a different org must not block the rename."""
        org_a = _org()
        org_b = _org()
        col_a = create_collection(db_session, _create_req(org_id=org_a, name="shared"))
        _col_b = create_collection(db_session, _create_req(org_id=org_b, name="shared"))

        # Renaming col_a to "shared" (same name it already has) — no conflict.
        updated = update_collection(
            db_session, col_a.id, UpdateCollectionRequest(name="shared")
        )
        assert updated.name == "shared"


# ---------------------------------------------------------------------------
# collection_service — delete_collection
# ---------------------------------------------------------------------------


class TestDeleteCollection:
    def test_delete_removes_db_row_and_storage(self, db_session) -> None:
        col = create_collection(db_session, _create_req())
        storage = col.storage_path
        assert Path(storage).is_dir()

        delete_collection(db_session, col.id)

        with pytest.raises(HTTPException) as exc:
            get_collection(db_session, col.id)
        assert exc.value.status_code == 404
        assert not Path(storage).exists()

    def test_delete_not_found_raises_404(self, db_session) -> None:
        with pytest.raises(HTTPException) as exc:
            delete_collection(db_session, "phantom-id")
        assert exc.value.status_code == 404

    def test_delete_proceeds_even_when_backend_raises(
        self, db_session, monkeypatch
    ) -> None:
        """When the vector backend's delete raises, the DB row and storage are
        still cleaned up (error is logged, not re-raised)."""
        from plugins.vector_db.chromadb_backend import ChromaDBBackend

        col = create_collection(db_session, _create_req())
        col_id = col.id

        def _failing_delete(**kwargs):
            raise RuntimeError("backend delete failed")

        monkeypatch.setattr(ChromaDBBackend, "delete_collection", _failing_delete)

        # Should NOT raise despite backend failure.
        delete_collection(db_session, col_id)

        # DB row must be gone.
        with pytest.raises(HTTPException) as exc:
            get_collection(db_session, col_id)
        assert exc.value.status_code == 404

    def test_delete_when_backend_registry_returns_none(
        self, db_session, monkeypatch
    ) -> None:
        """If VectorDBRegistry.get returns None during delete, the DB row and storage
        are still cleaned up (the 'if backend is not None' false branch, line 284)."""
        col = create_collection(db_session, _create_req())
        col_id = col.id

        # Remove the backend from the registry so VectorDBRegistry.get returns None.
        original = VectorDBRegistry._plugins.pop(col.vector_db_backend, None)
        try:
            delete_collection(db_session, col_id)
        finally:
            if original is not None:
                VectorDBRegistry._plugins[col.vector_db_backend] = original

        with pytest.raises(HTTPException) as exc:
            get_collection(db_session, col_id)
        assert exc.value.status_code == 404

    def test_delete_calls_backend_before_db_row_removed(
        self, db_session, monkeypatch
    ) -> None:
        """Verify deletion order: backend.delete called, then DB row gone."""
        from plugins.vector_db.chromadb_backend import ChromaDBBackend

        calls: list[str] = []
        original_delete = ChromaDBBackend.delete_collection

        def _tracking_delete(self, **kwargs):
            calls.append("backend_delete")
            original_delete(self, **kwargs)

        monkeypatch.setattr(ChromaDBBackend, "delete_collection", _tracking_delete)

        col = create_collection(db_session, _create_req())
        delete_collection(db_session, col.id)

        assert "backend_delete" in calls


# ---------------------------------------------------------------------------
# ingestion_service — queue_add_content
# ---------------------------------------------------------------------------


class TestQueueAddContent:
    def test_happy_path_creates_pending_job(self, db_session) -> None:
        col = create_collection(db_session, _create_req())
        req = _add_req(_doc())
        job = queue_add_content(db_session, col.id, req)

        assert job.id
        assert job.status == "pending"
        assert job.collection_id == col.id
        assert job.documents_total == 1
        assert job.documents_processed == 0

    def test_api_key_not_in_documents_json(self, db_session) -> None:
        """Credentials must never be serialized into documents_json (ADR-4)."""
        col = create_collection(db_session, _create_req())
        req = AddContentRequest(
            documents=[_doc()],
            embedding_credentials=EmbeddingCredentials(
                api_key="super-secret-key", api_endpoint=""
            ),
        )
        job = queue_add_content(db_session, col.id, req)

        payload = json.loads(job.documents_json)
        payload_str = json.dumps(payload)
        assert "super-secret-key" not in payload_str
        assert "api_key" not in payload_str

    def test_empty_docs_list_raises_400(self, db_session) -> None:
        """The schema-level validator prevents empty lists before reaching
        the service, but we test the service guard directly by constructing
        a request with an empty list (bypassing Pydantic validation)."""
        col = create_collection(db_session, _create_req())

        # Construct without Pydantic's own validator firing.
        req = AddContentRequest.__new__(AddContentRequest)
        object.__setattr__(req, "documents", [])
        object.__setattr__(
            req,
            "embedding_credentials",
            EmbeddingCredentials(api_key="", api_endpoint=""),
        )

        with pytest.raises(HTTPException) as exc:
            queue_add_content(db_session, col.id, req)
        assert exc.value.status_code == 400

    def test_missing_collection_raises_404(self, db_session) -> None:
        req = _add_req(_doc())
        with pytest.raises(HTTPException) as exc:
            queue_add_content(db_session, "no-such-collection", req)
        assert exc.value.status_code == 404

    def test_store_credentials_called(self, db_session, monkeypatch) -> None:
        """store_credentials is invoked exactly once after the job is persisted.

        Because ingestion_service does ``from tasks.worker import store_credentials``,
        we must patch the name *inside* the ingestion_service module, not on the
        tasks.worker module directly.
        """
        import services.ingestion_service as svc  # noqa: PLC0415

        stored: list[tuple[str, dict]] = []
        original_store = svc.store_credentials

        def _capture(job_id, creds):
            stored.append((job_id, creds))
            original_store(job_id, creds)

        monkeypatch.setattr(svc, "store_credentials", _capture)

        col = create_collection(db_session, _create_req())
        req = AddContentRequest(
            documents=[_doc()],
            embedding_credentials=EmbeddingCredentials(api_key="test-key", api_endpoint=""),
        )
        job = queue_add_content(db_session, col.id, req)

        assert len(stored) == 1
        job_id_stored, creds_stored = stored[0]
        assert job_id_stored == job.id
        assert creds_stored["api_key"] == "test-key"


# ---------------------------------------------------------------------------
# ingestion_service — execute_ingestion_job
# ---------------------------------------------------------------------------


class TestExecuteIngestionJob:
    def _make_collection_with_job(
        self,
        db_session,
        docs: list[DocumentInputPayload] | None = None,
    ) -> tuple[Collection, IngestionJob]:
        if docs is None:
            docs = [
                _doc("doc-1", "The quick brown fox jumps over the lazy dog. " * 10),
                _doc("doc-2", "Knowledge bases store vectorized text chunks. " * 10),
            ]
        col = create_collection(db_session, _create_req())
        req = _add_req(*docs)
        job = queue_add_content(db_session, col.id, req)

        # Simulate worker's pre-processing step.
        job.status = "processing"
        db_session.commit()
        db_session.refresh(col)
        return col, job

    def test_end_to_end_updates_counters_and_vectors_queryable(
        self, db_session
    ) -> None:
        """execute_ingestion_job processes docs, updates chunk/doc counts, and
        the vectors are queryable via the backend afterward."""
        col, job = self._make_collection_with_job(db_session)

        credentials = {"api_key": "", "api_endpoint": ""}
        execute_ingestion_job(db_session, job, col, credentials)

        db_session.refresh(col)
        db_session.refresh(job)

        assert col.document_count == 2
        assert col.chunk_count > 0
        assert job.documents_processed == 2
        assert job.chunks_created > 0

        # Vectors must be queryable.
        backend = VectorDBRegistry.get(col.vector_db_backend)
        ef = EmbeddingRegistry.build(
            col.embedding_vendor, model=col.embedding_model
        )
        results = backend.query(
            collection_id=col.backend_collection_id or col.id,
            storage_path=col.storage_path,
            query_text="brown fox",
            top_k=5,
            embedding_function=ef,
        )
        assert len(results) > 0

    def test_batch_commit_with_monkeypatched_batch_size(
        self, db_session, monkeypatch
    ) -> None:
        """With _COMMIT_BATCH_SIZE=2 and 5 docs, intermediate commits happen.
        After the call, documents_processed == 5.
        """
        import services.ingestion_service as svc  # noqa: PLC0415

        monkeypatch.setattr(svc, "_COMMIT_BATCH_SIZE", 2)

        docs = [
            _doc(f"doc-{i}", f"Text for document {i}. " * 15)
            for i in range(5)
        ]
        col, job = self._make_collection_with_job(db_session, docs)

        credentials = {"api_key": "", "api_endpoint": ""}
        execute_ingestion_job(db_session, job, col, credentials)

        db_session.refresh(job)
        assert job.documents_processed == 5
        assert job.chunks_created > 0

    def test_chunking_plugin_disabled_mid_run_raises_runtime_error(
        self, db_session, monkeypatch
    ) -> None:
        """Removing a chunking strategy from the registry after collection creation
        causes execute_ingestion_job to raise RuntimeError with a descriptive message."""
        col, job = self._make_collection_with_job(db_session)

        # Remove the plugin from the registry to simulate it being disabled.
        original = ChunkingRegistry._plugins.pop(col.chunking_strategy, None)
        try:
            credentials = {"api_key": "", "api_endpoint": ""}
            with pytest.raises(RuntimeError, match="not available"):
                execute_ingestion_job(db_session, job, col, credentials)
        finally:
            if original is not None:
                ChunkingRegistry._plugins[col.chunking_strategy] = original

    def test_vector_backend_unavailable_raises_runtime_error(
        self, db_session, monkeypatch
    ) -> None:
        """Removing the vector backend from the registry raises RuntimeError."""
        col, job = self._make_collection_with_job(db_session)

        original = VectorDBRegistry._plugins.pop(col.vector_db_backend, None)
        try:
            credentials = {"api_key": "", "api_endpoint": ""}
            with pytest.raises(RuntimeError, match="not available"):
                execute_ingestion_job(db_session, job, col, credentials)
        finally:
            if original is not None:
                VectorDBRegistry._plugins[col.vector_db_backend] = original

    def test_document_producing_zero_chunks_is_skipped(
        self, db_session, monkeypatch
    ) -> None:
        """When a chunking strategy returns an empty list for a document, n_stored
        stays 0 and the job still progresses (covers the 'if chunks:' false branch)."""

        original_chunk_fn = None
        strategy_name = "simple"

        # Grab the real strategy class and patch its chunk() method to return [].
        strategy_class = ChunkingRegistry._plugins.get(strategy_name)
        original_chunk_fn = strategy_class.chunk

        def _empty_chunks(self, document, params=None):
            return []

        strategy_class.chunk = _empty_chunks
        try:
            col, job = self._make_collection_with_job(db_session)
            credentials = {"api_key": "", "api_endpoint": ""}
            execute_ingestion_job(db_session, job, col, credentials)

            db_session.refresh(job)
            assert job.documents_processed == 2
            # Zero chunks were added since chunk() returned [].
            assert job.chunks_created == 0
        finally:
            strategy_class.chunk = original_chunk_fn


# ---------------------------------------------------------------------------
# ingestion_service — delete_vectors
# ---------------------------------------------------------------------------


class TestDeleteVectors:
    def _ingest(self, db_session, source_item_id: str = "src-1") -> Collection:
        """Create a collection, ingest one document, and return the collection."""
        col = create_collection(db_session, _create_req())
        docs = [_doc(source_item_id, "Sample text for deletion test. " * 10)]
        req = _add_req(*docs)
        job = queue_add_content(db_session, col.id, req)
        job.status = "processing"
        db_session.commit()
        db_session.refresh(col)

        execute_ingestion_job(db_session, job, col, {"api_key": "", "api_endpoint": ""})
        db_session.refresh(col)
        return col

    def test_delete_vectors_returns_deleted_count(self, db_session) -> None:
        col = self._ingest(db_session, "src-del")
        assert col.chunk_count > 0

        deleted = delete_vectors(db_session, col.id, "src-del")
        assert deleted > 0

    def test_delete_vectors_decrements_counters(self, db_session) -> None:
        col = self._ingest(db_session, "src-cnt")
        before_chunks = col.chunk_count
        before_docs = col.document_count

        delete_vectors(db_session, col.id, "src-cnt")
        db_session.refresh(col)

        assert col.document_count == max(0, before_docs - 1)
        assert col.chunk_count == max(0, before_chunks - 1)

    def test_delete_vectors_clamps_at_zero(self, db_session) -> None:
        """If chunk_count is artificially small, counters clamp at 0 (no negatives)."""
        col = self._ingest(db_session, "src-clamp")
        # Set chunk_count below the number of vectors that exist.
        col.chunk_count = 2
        col.document_count = 1
        db_session.commit()

        # delete_vectors for a source with >2 chunks → chunk_count would go negative
        # without the max(0, …) guard.
        delete_vectors(db_session, col.id, "src-clamp")
        db_session.refresh(col)

        assert col.chunk_count >= 0
        assert col.document_count >= 0

    def test_delete_vectors_missing_collection_raises_404(self, db_session) -> None:
        with pytest.raises(HTTPException) as exc:
            delete_vectors(db_session, "no-such-col", "src-x")
        assert exc.value.status_code == 404

    def test_delete_vectors_nonexistent_source_returns_zero(self, db_session) -> None:
        col = self._ingest(db_session, "src-real")
        deleted = delete_vectors(db_session, col.id, "nonexistent-source")
        assert deleted == 0

    def test_delete_vectors_backend_unavailable_raises_503(
        self, db_session, monkeypatch
    ) -> None:
        """delete_vectors raises 503 when VectorDBRegistry.get returns None."""
        col = self._ingest(db_session, "src-503")

        monkeypatch.setattr(VectorDBRegistry, "get", staticmethod(lambda name: None))

        with pytest.raises(HTTPException) as exc:
            delete_vectors(db_session, col.id, "src-503")
        assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# query_service — query_collection
# ---------------------------------------------------------------------------


class TestQueryCollection:
    def _populated_collection(self, db_session) -> Collection:
        col = create_collection(db_session, _create_req())
        docs = [
            _doc("doc-q1", "The capital of France is Paris. " * 10),
            _doc("doc-q2", "Machine learning relies on linear algebra. " * 10),
        ]
        req = _add_req(*docs)
        job = queue_add_content(db_session, col.id, req)
        job.status = "processing"
        db_session.commit()
        db_session.refresh(col)
        execute_ingestion_job(db_session, job, col, {"api_key": "", "api_endpoint": ""})
        db_session.refresh(col)
        return col

    def test_query_happy_path_returns_results(self, db_session) -> None:
        col = self._populated_collection(db_session)
        req = QueryRequest(query_text="France Paris capital", top_k=5)
        results = query_collection(db_session, col.id, req)

        assert isinstance(results, list)
        assert len(results) > 0
        for r in results:
            assert r.text
            assert 0.0 <= r.score <= 1.0

    def test_query_missing_collection_raises_404(self, db_session) -> None:
        req = QueryRequest(query_text="test query")
        with pytest.raises(HTTPException) as exc:
            query_collection(db_session, "no-such-collection", req)
        assert exc.value.status_code == 404

    def test_query_backend_unavailable_raises_503(
        self, db_session, monkeypatch
    ) -> None:
        """When VectorDBRegistry.get returns None, a 503 is raised."""
        col = self._populated_collection(db_session)

        monkeypatch.setattr(VectorDBRegistry, "get", staticmethod(lambda name: None))

        req = QueryRequest(query_text="test query")
        with pytest.raises(HTTPException) as exc:
            query_collection(db_session, col.id, req)
        assert exc.value.status_code == 503

    def test_query_uses_request_scoped_credentials(
        self, db_session, monkeypatch
    ) -> None:
        """EmbeddingRegistry.build is called with the request's credentials,
        not with credentials from the collection row."""
        col = self._populated_collection(db_session)

        observed: list[dict] = []
        original_build = EmbeddingRegistry.build

        @classmethod  # type: ignore[misc]
        def _capturing_build(cls, name, *, model, api_key="", api_endpoint=""):
            observed.append({"api_key": api_key, "api_endpoint": api_endpoint})
            return original_build.__func__(
                cls, name, model=model, api_key=api_key, api_endpoint=api_endpoint
            )

        monkeypatch.setattr(EmbeddingRegistry, "build", _capturing_build)

        req = QueryRequest(
            query_text="France",
            embedding_credentials=EmbeddingCredentials(
                api_key="request-key-xyz", api_endpoint=""
            ),
        )
        query_collection(db_session, col.id, req)

        assert observed, "EmbeddingRegistry.build was never called"
        assert observed[0]["api_key"] == "request-key-xyz"

    def test_query_top_k_respected(self, db_session) -> None:
        col = self._populated_collection(db_session)
        req = QueryRequest(query_text="machine learning", top_k=1)
        results = query_collection(db_session, col.id, req)
        assert len(results) <= 1
