"""Unit tests for Pydantic schemas.

Covers:
  - schemas/common.py   (ErrorResponse, PaginatedResponse)
  - schemas/collection.py (EmbeddingConfig, CreateCollectionRequest,
                           UpdateCollectionRequest, CollectionResponse,
                           CollectionListResponse)
  - schemas/content.py  (PageInput, PermalinkInput, EmbeddingCredentials,
                         DocumentInputPayload, AddContentRequest,
                         AddContentResponse, DeleteVectorsResponse)
  - schemas/query.py    (QueryRequest, QueryResultItem, QueryResponse)
  - schemas/jobs.py     (JobStatusResponse)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _make_embedding_config(**kwargs):
    from schemas.collection import EmbeddingConfig

    defaults = dict(vendor="openai", model="text-embedding-3-small")
    defaults.update(kwargs)
    return EmbeddingConfig(**defaults)


def _make_create_collection(**kwargs):
    from schemas.collection import CreateCollectionRequest

    defaults = dict(
        organization_id="org-1",
        name="my-kb",
        chunking_strategy="simple",
        embedding=_make_embedding_config(),
    )
    defaults.update(kwargs)
    return CreateCollectionRequest(**defaults)


def _minimal_document(**kwargs):
    defaults = dict(source_item_id="item-1", title="Doc", text="Hello world")
    defaults.update(kwargs)
    return defaults


def _make_ingestion_job(db_session, **kwargs) -> object:
    """Insert a minimal IngestionJob row and return the ORM instance."""
    from database.models import IngestionJob

    defaults = dict(
        id=str(uuid.uuid4()),
        collection_id=str(uuid.uuid4()),
        organization_id="org-1",
        documents_json="[]",
    )
    defaults.update(kwargs)
    job = IngestionJob(**defaults)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# ===========================================================================
# schemas/common.py
# ===========================================================================


class TestErrorResponse:
    def test_detail_field_populated(self) -> None:
        from schemas.common import ErrorResponse

        err = ErrorResponse(detail="something went wrong")
        assert err.detail == "something went wrong"

    def test_missing_detail_raises(self) -> None:
        from schemas.common import ErrorResponse

        with pytest.raises(ValidationError):
            ErrorResponse()  # type: ignore[call-arg]

    def test_detail_as_empty_string(self) -> None:
        from schemas.common import ErrorResponse

        err = ErrorResponse(detail="")
        assert err.detail == ""

    def test_model_dump_shape(self) -> None:
        from schemas.common import ErrorResponse

        data = ErrorResponse(detail="oops").model_dump()
        assert data == {"detail": "oops"}


class TestPaginatedResponse:
    def test_all_fields_required(self) -> None:
        from schemas.common import PaginatedResponse

        with pytest.raises(ValidationError):
            PaginatedResponse(items=[], total=10)  # type: ignore[call-arg]

    def test_valid_instance(self) -> None:
        from schemas.common import PaginatedResponse

        resp = PaginatedResponse(items=["a", "b"], total=2, limit=10, offset=0)
        assert resp.items == ["a", "b"]
        assert resp.total == 2
        assert resp.limit == 10
        assert resp.offset == 0

    def test_empty_items(self) -> None:
        from schemas.common import PaginatedResponse

        resp = PaginatedResponse(items=[], total=0, limit=20, offset=0)
        assert resp.items == []
        assert resp.total == 0

    def test_model_dump_shape(self) -> None:
        from schemas.common import PaginatedResponse

        data = PaginatedResponse(items=[1, 2], total=2, limit=5, offset=0).model_dump()
        assert set(data.keys()) == {"items", "total", "limit", "offset"}


# ===========================================================================
# schemas/collection.py
# ===========================================================================


class TestEmbeddingConfig:
    def test_required_vendor_and_model(self) -> None:
        from schemas.collection import EmbeddingConfig

        cfg = EmbeddingConfig(vendor="openai", model="text-embedding-ada-002")
        assert cfg.vendor == "openai"
        assert cfg.model == "text-embedding-ada-002"

    def test_missing_vendor_raises(self) -> None:
        from schemas.collection import EmbeddingConfig

        with pytest.raises(ValidationError):
            EmbeddingConfig(model="text-embedding-ada-002")  # type: ignore[call-arg]

    def test_missing_model_raises(self) -> None:
        from schemas.collection import EmbeddingConfig

        with pytest.raises(ValidationError):
            EmbeddingConfig(vendor="openai")  # type: ignore[call-arg]

    def test_api_endpoint_defaults_to_empty_string(self) -> None:
        cfg = _make_embedding_config()
        assert cfg.api_endpoint == ""

    def test_api_endpoint_optional_set(self) -> None:
        cfg = _make_embedding_config(api_endpoint="http://proxy/v1")
        assert cfg.api_endpoint == "http://proxy/v1"


class TestCreateCollectionRequest:
    def test_minimal_valid(self) -> None:
        req = _make_create_collection()
        assert req.organization_id == "org-1"
        assert req.name == "my-kb"
        assert req.chunking_strategy == "simple"

    def test_id_is_optional(self) -> None:
        req = _make_create_collection()
        assert req.id is None

    def test_id_can_be_supplied(self) -> None:
        supplied = str(uuid.uuid4())
        req = _make_create_collection(id=supplied)
        assert req.id == supplied

    def test_description_defaults_to_none(self) -> None:
        req = _make_create_collection()
        assert req.description is None

    def test_description_optional_set(self) -> None:
        req = _make_create_collection(description="A test KB")
        assert req.description == "A test KB"

    def test_chunking_params_defaults_to_empty_dict(self) -> None:
        req = _make_create_collection()
        assert req.chunking_params == {}

    def test_chunking_params_set(self) -> None:
        req = _make_create_collection(chunking_params={"chunk_size": 512})
        assert req.chunking_params == {"chunk_size": 512}

    def test_vector_db_backend_defaults_to_chromadb(self) -> None:
        req = _make_create_collection()
        assert req.vector_db_backend == "chromadb"

    def test_name_empty_string_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_create_collection(name="")

    def test_missing_organization_id_raises(self) -> None:
        from schemas.collection import CreateCollectionRequest

        with pytest.raises(ValidationError):
            CreateCollectionRequest(
                name="kb",
                chunking_strategy="simple",
                embedding=_make_embedding_config(),
            )  # type: ignore[call-arg]

    def test_missing_chunking_strategy_raises(self) -> None:
        from schemas.collection import CreateCollectionRequest

        with pytest.raises(ValidationError):
            CreateCollectionRequest(
                organization_id="org-1",
                name="kb",
                embedding=_make_embedding_config(),
            )  # type: ignore[call-arg]

    def test_missing_embedding_raises(self) -> None:
        from schemas.collection import CreateCollectionRequest

        with pytest.raises(ValidationError):
            CreateCollectionRequest(
                organization_id="org-1",
                name="kb",
                chunking_strategy="simple",
            )  # type: ignore[call-arg]


class TestUpdateCollectionRequest:
    def test_all_fields_optional(self) -> None:
        from schemas.collection import UpdateCollectionRequest

        req = UpdateCollectionRequest()
        assert req.name is None
        assert req.description is None

    def test_set_name_and_description(self) -> None:
        from schemas.collection import UpdateCollectionRequest

        req = UpdateCollectionRequest(name="new-name", description="desc")
        assert req.name == "new-name"
        assert req.description == "desc"

    def test_name_min_length_empty_raises(self) -> None:
        from schemas.collection import UpdateCollectionRequest

        with pytest.raises(ValidationError):
            UpdateCollectionRequest(name="")

    def test_extra_field_is_silently_dropped(self) -> None:
        """chunking_strategy is not a field on UpdateCollectionRequest.

        Pydantic's default is to ignore (not error on) extra fields; the field
        must not appear in model_dump().
        """
        from schemas.collection import UpdateCollectionRequest

        req = UpdateCollectionRequest(
            name="kb", chunking_strategy="by_page"  # type: ignore[call-arg]
        )
        dumped = req.model_dump()
        assert "chunking_strategy" not in dumped
        assert dumped == {"name": "kb", "description": None}


class TestCollectionResponse:
    def _make_orm_row(self, **kwargs):
        """Return a simple namespace that mimics the ORM Collection row."""
        import types

        now = _now()
        defaults = dict(
            id=str(uuid.uuid4()),
            organization_id="org-1",
            name="test-kb",
            description=None,
            chunking_strategy="simple",
            chunking_params='{"chunk_size": 512}',
            embedding_vendor="openai",
            embedding_model="text-embedding-3-small",
            embedding_endpoint=None,
            vector_db_backend="chromadb",
            status="ready",
            document_count=3,
            chunk_count=12,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        defaults.update(kwargs)
        return types.SimpleNamespace(**defaults)

    def test_from_orm_row_basic(self) -> None:
        from schemas.collection import CollectionResponse

        row = self._make_orm_row()
        resp = CollectionResponse.from_orm_row(row)
        assert resp.id == row.id
        assert resp.organization_id == "org-1"
        assert resp.name == "test-kb"
        assert resp.chunking_params == {"chunk_size": 512}
        assert resp.embedding.vendor == "openai"
        assert resp.embedding.model == "text-embedding-3-small"
        assert resp.embedding.api_endpoint == ""
        assert resp.status == "ready"
        assert resp.document_count == 3
        assert resp.chunk_count == 12

    def test_from_orm_row_with_description(self) -> None:
        from schemas.collection import CollectionResponse

        row = self._make_orm_row(description="A description")
        resp = CollectionResponse.from_orm_row(row)
        assert resp.description == "A description"

    def test_from_orm_row_null_chunking_params(self) -> None:
        """None chunking_params must fall back to empty dict."""
        from schemas.collection import CollectionResponse

        row = self._make_orm_row(chunking_params=None)
        resp = CollectionResponse.from_orm_row(row)
        assert resp.chunking_params == {}

    def test_from_orm_row_embedding_endpoint_set(self) -> None:
        from schemas.collection import CollectionResponse

        row = self._make_orm_row(embedding_endpoint="http://proxy/v1")
        resp = CollectionResponse.from_orm_row(row)
        assert resp.embedding.api_endpoint == "http://proxy/v1"

    def test_from_orm_row_with_error_message(self) -> None:
        from schemas.collection import CollectionResponse

        row = self._make_orm_row(status="error", error_message="Timeout")
        resp = CollectionResponse.from_orm_row(row)
        assert resp.status == "error"
        assert resp.error_message == "Timeout"


class TestCollectionListResponse:
    def test_collections_and_total(self) -> None:
        from schemas.collection import CollectionListResponse, CollectionResponse

        now = _now()
        col = CollectionResponse(
            id="c-1",
            organization_id="org-1",
            name="kb",
            description=None,
            chunking_strategy="simple",
            chunking_params={},
            embedding=_make_embedding_config(),
            vector_db_backend="chromadb",
            status="ready",
            document_count=0,
            chunk_count=0,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        lst = CollectionListResponse(collections=[col], total=1)
        assert lst.total == 1
        assert len(lst.collections) == 1

    def test_empty_list(self) -> None:
        from schemas.collection import CollectionListResponse

        lst = CollectionListResponse(collections=[], total=0)
        assert lst.total == 0
        assert lst.collections == []


# ===========================================================================
# schemas/content.py
# ===========================================================================


class TestPageInput:
    def test_required_fields(self) -> None:
        from schemas.content import PageInput

        pg = PageInput(page_number=1, text="page content")
        assert pg.page_number == 1
        assert pg.text == "page content"

    def test_missing_page_number_raises(self) -> None:
        from schemas.content import PageInput

        with pytest.raises(ValidationError):
            PageInput(text="content")  # type: ignore[call-arg]

    def test_missing_text_raises(self) -> None:
        from schemas.content import PageInput

        with pytest.raises(ValidationError):
            PageInput(page_number=1)  # type: ignore[call-arg]


class TestPermalinkInput:
    def test_all_fields_optional(self) -> None:
        from schemas.content import PermalinkInput

        pl = PermalinkInput()
        assert pl.original == ""
        assert pl.full_markdown == ""
        assert pl.pages == []

    def test_extra_allow_preserves_field(self) -> None:
        from schemas.content import PermalinkInput

        pl = PermalinkInput(original="a", arbitrary_field="x")  # type: ignore[call-arg]
        dumped = pl.model_dump()
        assert dumped["arbitrary_field"] == "x"
        assert dumped["original"] == "a"

    def test_extra_allow_multiple_extra_fields(self) -> None:
        from schemas.content import PermalinkInput

        pl = PermalinkInput(  # type: ignore[call-arg]
            original="http://example.com/file.pdf",
            full_markdown="http://example.com/file.md",
            pages=["http://example.com/p1.md"],
            thumbnail="http://example.com/thumb.png",
            preview_url="http://example.com/preview",
        )
        dumped = pl.model_dump()
        assert dumped["thumbnail"] == "http://example.com/thumb.png"
        assert dumped["preview_url"] == "http://example.com/preview"

    def test_pages_default_factory(self) -> None:
        from schemas.content import PermalinkInput

        p1 = PermalinkInput()
        p2 = PermalinkInput()
        # Ensure separate instances (default_factory, not shared list).
        p1.pages.append("http://x")
        assert p2.pages == []


class TestEmbeddingCredentials:
    def test_defaults_empty_strings(self) -> None:
        from schemas.content import EmbeddingCredentials

        creds = EmbeddingCredentials()
        assert creds.api_key == ""
        assert creds.api_endpoint == ""

    def test_set_api_key(self) -> None:
        from schemas.content import EmbeddingCredentials

        creds = EmbeddingCredentials(api_key="sk-test")
        assert creds.api_key == "sk-test"

    def test_set_api_endpoint(self) -> None:
        from schemas.content import EmbeddingCredentials

        creds = EmbeddingCredentials(api_endpoint="http://proxy/v1")
        assert creds.api_endpoint == "http://proxy/v1"


class TestDocumentInputPayload:
    def test_minimal_valid(self) -> None:
        from schemas.content import DocumentInputPayload

        doc = DocumentInputPayload(**_minimal_document())
        assert doc.source_item_id == "item-1"
        assert doc.title == "Doc"
        assert doc.text == "Hello world"

    def test_defaults_for_optional_fields(self) -> None:
        from schemas.content import DocumentInputPayload

        doc = DocumentInputPayload(**_minimal_document())
        assert doc.pages == []
        assert doc.extra_metadata == {}
        # permalinks defaults to a PermalinkInput instance
        assert doc.permalinks.original == ""
        assert doc.permalinks.full_markdown == ""

    def test_missing_source_item_id_raises(self) -> None:
        from schemas.content import DocumentInputPayload

        with pytest.raises(ValidationError):
            DocumentInputPayload(title="Doc", text="text")  # type: ignore[call-arg]

    def test_missing_title_raises(self) -> None:
        from schemas.content import DocumentInputPayload

        with pytest.raises(ValidationError):
            DocumentInputPayload(source_item_id="x", text="text")  # type: ignore[call-arg]

    def test_missing_text_raises(self) -> None:
        from schemas.content import DocumentInputPayload

        with pytest.raises(ValidationError):
            DocumentInputPayload(source_item_id="x", title="Doc")  # type: ignore[call-arg]

    def test_pages_field_populated(self) -> None:
        from schemas.content import DocumentInputPayload, PageInput

        pages = [PageInput(page_number=1, text="p1"), PageInput(page_number=2, text="p2")]
        doc = DocumentInputPayload(**_minimal_document(), pages=pages)
        assert len(doc.pages) == 2

    def test_extra_metadata_populated(self) -> None:
        from schemas.content import DocumentInputPayload

        doc = DocumentInputPayload(**_minimal_document(), extra_metadata={"lang": "en"})
        assert doc.extra_metadata == {"lang": "en"}


class TestAddContentRequest:
    def test_valid_with_one_document(self) -> None:
        from schemas.content import AddContentRequest

        req = AddContentRequest(documents=[_minimal_document()])
        assert len(req.documents) == 1

    def test_empty_documents_list_raises_via_field_constraint(self) -> None:
        """min_length=1 on the Field must reject an empty list at validation time."""
        from schemas.content import AddContentRequest

        with pytest.raises(ValidationError):
            AddContentRequest(documents=[])

    def test_missing_documents_raises(self) -> None:
        from schemas.content import AddContentRequest

        with pytest.raises(ValidationError):
            AddContentRequest()  # type: ignore[call-arg]

    def test_embedding_credentials_defaults(self) -> None:
        from schemas.content import AddContentRequest

        req = AddContentRequest(documents=[_minimal_document()])
        assert req.embedding_credentials.api_key == ""

    def test_single_document_with_empty_text_passes(self) -> None:
        """An empty text field in DocumentInputPayload has no min_length constraint."""
        from schemas.content import AddContentRequest

        doc = _minimal_document(text="")
        req = AddContentRequest(documents=[doc])
        assert req.documents[0].text == ""

    def test_multiple_documents_accepted(self) -> None:
        from schemas.content import AddContentRequest

        docs = [_minimal_document(source_item_id=f"item-{i}") for i in range(3)]
        req = AddContentRequest(documents=docs)
        assert len(req.documents) == 3


class TestAddContentResponse:
    def test_required_fields(self) -> None:
        from schemas.content import AddContentResponse

        resp = AddContentResponse(
            job_id="job-123", status="pending", documents_total=5
        )
        assert resp.job_id == "job-123"
        assert resp.status == "pending"
        assert resp.documents_total == 5

    def test_missing_job_id_raises(self) -> None:
        from schemas.content import AddContentResponse

        with pytest.raises(ValidationError):
            AddContentResponse(status="pending", documents_total=1)  # type: ignore[call-arg]

    def test_missing_status_raises(self) -> None:
        from schemas.content import AddContentResponse

        with pytest.raises(ValidationError):
            AddContentResponse(job_id="j", documents_total=1)  # type: ignore[call-arg]


class TestDeleteVectorsResponse:
    def test_fields(self) -> None:
        from schemas.content import DeleteVectorsResponse

        resp = DeleteVectorsResponse(source_item_id="item-1", deleted_count=7)
        assert resp.source_item_id == "item-1"
        assert resp.deleted_count == 7

    def test_missing_source_item_id_raises(self) -> None:
        from schemas.content import DeleteVectorsResponse

        with pytest.raises(ValidationError):
            DeleteVectorsResponse(deleted_count=1)  # type: ignore[call-arg]

    def test_missing_deleted_count_raises(self) -> None:
        from schemas.content import DeleteVectorsResponse

        with pytest.raises(ValidationError):
            DeleteVectorsResponse(source_item_id="x")  # type: ignore[call-arg]


# ===========================================================================
# schemas/query.py
# ===========================================================================


class TestQueryRequest:
    def test_minimal_valid(self) -> None:
        from schemas.query import QueryRequest

        req = QueryRequest(query_text="machine learning")
        assert req.query_text == "machine learning"
        assert req.top_k == 5  # default

    def test_top_k_default(self) -> None:
        from schemas.query import QueryRequest

        req = QueryRequest(query_text="test")
        assert req.top_k == 5

    def test_top_k_boundary_1(self) -> None:
        from schemas.query import QueryRequest

        req = QueryRequest(query_text="test", top_k=1)
        assert req.top_k == 1

    def test_top_k_boundary_100(self) -> None:
        from schemas.query import QueryRequest

        req = QueryRequest(query_text="test", top_k=100)
        assert req.top_k == 100

    def test_top_k_zero_raises(self) -> None:
        from schemas.query import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest(query_text="test", top_k=0)

    def test_top_k_101_raises(self) -> None:
        from schemas.query import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest(query_text="test", top_k=101)

    def test_query_text_empty_raises(self) -> None:
        from schemas.query import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest(query_text="")

    def test_missing_query_text_raises(self) -> None:
        from schemas.query import QueryRequest

        with pytest.raises(ValidationError):
            QueryRequest()  # type: ignore[call-arg]

    def test_embedding_credentials_default(self) -> None:
        from schemas.query import QueryRequest

        req = QueryRequest(query_text="hello")
        assert req.embedding_credentials.api_key == ""

    def test_embedding_credentials_custom(self) -> None:
        from schemas.query import QueryRequest

        req = QueryRequest(
            query_text="hello",
            embedding_credentials={"api_key": "sk-123"},
        )
        assert req.embedding_credentials.api_key == "sk-123"


class TestQueryResultItem:
    def test_required_fields(self) -> None:
        from schemas.query import QueryResultItem

        item = QueryResultItem(text="chunk content", score=0.87)
        assert item.text == "chunk content"
        assert item.score == 0.87

    def test_metadata_defaults_to_empty_dict(self) -> None:
        from schemas.query import QueryResultItem

        item = QueryResultItem(text="x", score=0.5)
        assert item.metadata == {}

    def test_metadata_populated(self) -> None:
        from schemas.query import QueryResultItem

        item = QueryResultItem(
            text="x", score=0.9, metadata={"source_item_id": "doc-1"}
        )
        assert item.metadata["source_item_id"] == "doc-1"

    def test_missing_score_raises(self) -> None:
        from schemas.query import QueryResultItem

        with pytest.raises(ValidationError):
            QueryResultItem(text="x")  # type: ignore[call-arg]

    def test_missing_text_raises(self) -> None:
        from schemas.query import QueryResultItem

        with pytest.raises(ValidationError):
            QueryResultItem(score=0.5)  # type: ignore[call-arg]


class TestQueryResponse:
    def test_valid(self) -> None:
        from schemas.query import QueryResponse, QueryResultItem

        items = [QueryResultItem(text="a", score=0.9)]
        resp = QueryResponse(results=items, query="my query", top_k=5)
        assert resp.query == "my query"
        assert resp.top_k == 5
        assert len(resp.results) == 1

    def test_empty_results(self) -> None:
        from schemas.query import QueryResponse

        resp = QueryResponse(results=[], query="q", top_k=3)
        assert resp.results == []

    def test_missing_query_raises(self) -> None:
        from schemas.query import QueryResponse

        with pytest.raises(ValidationError):
            QueryResponse(results=[], top_k=5)  # type: ignore[call-arg]

    def test_missing_top_k_raises(self) -> None:
        from schemas.query import QueryResponse

        with pytest.raises(ValidationError):
            QueryResponse(results=[], query="q")  # type: ignore[call-arg]


# ===========================================================================
# schemas/jobs.py
# ===========================================================================


class TestJobStatusResponse:
    def test_from_orm_row(self, db_session) -> None:
        """model_validate(orm_row) must map all fields correctly."""
        from schemas.jobs import JobStatusResponse

        job = _make_ingestion_job(db_session)
        resp = JobStatusResponse.model_validate(job)

        assert resp.id == job.id
        assert resp.collection_id == job.collection_id
        assert resp.status == "pending"
        assert resp.documents_total == 0
        assert resp.documents_processed == 0
        assert resp.chunks_created == 0
        assert resp.error_message is None
        assert resp.attempts == 0
        assert resp.created_at is not None
        assert resp.updated_at is not None
        assert resp.started_at is None
        assert resp.completed_at is None

    def test_from_orm_row_with_all_fields(self, db_session) -> None:
        """Fully-populated ORM row round-trips correctly."""
        from schemas.jobs import JobStatusResponse

        now = _now()
        job = _make_ingestion_job(
            db_session,
            status="completed",
            documents_total=5,
            documents_processed=5,
            chunks_created=25,
            attempts=1,
            started_at=now,
            completed_at=now,
        )
        resp = JobStatusResponse.model_validate(job)

        assert resp.status == "completed"
        assert resp.documents_total == 5
        assert resp.documents_processed == 5
        assert resp.chunks_created == 25
        assert resp.attempts == 1
        assert resp.started_at is not None
        assert resp.completed_at is not None

    def test_direct_construction(self) -> None:
        """JobStatusResponse can also be constructed directly (not just from ORM)."""
        from schemas.jobs import JobStatusResponse

        now = _now()
        resp = JobStatusResponse(
            id="job-1",
            collection_id="col-1",
            status="pending",
            documents_total=2,
            documents_processed=0,
            chunks_created=0,
            error_message=None,
            attempts=0,
            created_at=now,
            updated_at=now,
        )
        assert resp.id == "job-1"

    def test_missing_required_fields_raises(self) -> None:
        from schemas.jobs import JobStatusResponse

        with pytest.raises(ValidationError):
            JobStatusResponse(id="job-1")  # type: ignore[call-arg]

    def test_error_message_populated(self, db_session) -> None:
        from schemas.jobs import JobStatusResponse

        job = _make_ingestion_job(
            db_session,
            status="failed",
            error_message="Embedding API timed out",
        )
        resp = JobStatusResponse.model_validate(job)
        assert resp.error_message == "Embedding API timed out"
        assert resp.status == "failed"
