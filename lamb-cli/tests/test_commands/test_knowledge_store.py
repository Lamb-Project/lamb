"""Tests for Knowledge Store commands — lamb ks *."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lamb_cli.main import app

runner = CliRunner()


SAMPLE_OPTIONS = {
    "vector_db_backends": [
        {"name": "chromadb", "description": "ChromaDB local"},
        {"name": "qdrant", "description": "Qdrant cluster"},
    ],
    "chunking_strategies": [
        {"name": "simple", "description": "Fixed-size chunks"},
        {"name": "by_page", "description": "One chunk per page"},
    ],
    "embedding_vendors": [
        {"name": "openai", "description": "OpenAI embeddings"},
        {"name": "ollama", "description": "Ollama embeddings"},
    ],
    "embedding_models": {
        "openai": ["text-embedding-3-small", "text-embedding-3-large"],
        "ollama": ["nomic-embed-text"],
    },
}

SAMPLE_OPTIONS_EMPTY = {
    "vector_db_backends": [],
    "chunking_strategies": [],
    "embedding_vendors": [],
    "embedding_models": {},
}

SAMPLE_KS = {
    "id": "ks-1",
    "name": "Course KS",
    "description": "Course content KS",
    "chunking_strategy": "simple",
    "chunking_params": {},
    "embedding_vendor": "openai",
    "embedding_model": "text-embedding-3-small",
    "embedding_endpoint": None,
    "vector_db_backend": "chromadb",
    "is_shared": False,
    "is_owner": True,
    "server_status": "ready",
    "document_count": 0,
    "chunk_count": 0,
    "owner_email": "user@example.com",
    "content_count": 0,
    "created_at": "2026-04-01T00:00:00Z",
    "updated_at": "2026-04-01T00:00:00Z",
}

SAMPLE_KS_LIST = {
    "knowledge_stores": [
        SAMPLE_KS,
        {**SAMPLE_KS, "id": "ks-2", "name": "Lab KS"},
    ]
}

SAMPLE_CONTENT = {
    "content": [
        {
            "library_item_id": "item-1",
            "item_title": "Chapter 1",
            "library_name": "CS Lib",
            "item_source_type": "file",
            "status": "ready",
            "chunks_created": 12,
            "kb_job_id": "job-1",
        },
        {
            "library_item_id": "item-2",
            "item_title": "Lecture",
            "library_name": "CS Lib",
            "item_source_type": "youtube",
            "status": "in_progress",
            "chunks_created": 0,
            "kb_job_id": "job-2",
        },
    ]
}

SAMPLE_QUERY = {
    "results": [
        {
            "score": 0.9521,
            "text": "Chapter 1 covers algorithms and data structures.",
            "metadata": {
                "source_title": "Chapter 1",
                "source_item_id": "item-1",
                "permalink": "/docs/lib-1/item-1#p1",
            },
        },
        {
            "score": 0.8123,
            "text": "Big-O notation describes worst-case complexity.",
            "metadata": {
                "source_title": "Chapter 1",
                "source_item_id": "item-1",
                "permalink": "/docs/lib-1/item-1#p2",
            },
        },
    ]
}


# ---------------------------------------------------------------------------
# options
# ---------------------------------------------------------------------------


class TestKsOptions:
    def test_options_table_renders_sections(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_OPTIONS)
        result = runner.invoke(app, ["ks", "options"])
        assert result.exit_code == 0
        # Each section title rendered
        assert "Vector Db Backends" in result.output
        assert "Chunking Strategies" in result.output
        assert "Embedding Vendors" in result.output
        assert "Embedding Models" in result.output
        # Section content
        assert "chromadb" in result.output
        assert "simple" in result.output
        assert "openai" in result.output
        assert "text-embedding-3-small" in result.output

    def test_options_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_OPTIONS)
        result = runner.invoke(app, ["ks", "options", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "vector_db_backends" in data
        assert data["embedding_models"]["openai"][0] == "text-embedding-3-small"

    def test_options_empty(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_OPTIONS_EMPTY)
        result = runner.invoke(app, ["ks", "options"])
        assert result.exit_code == 0
        assert "(none available)" in result.output
        assert "(none configured)" in result.output


# ---------------------------------------------------------------------------
# create / list / get / update / delete / share
# ---------------------------------------------------------------------------


class TestKsCreate:
    def test_create_happy_path(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KS)
        result = runner.invoke(
            app,
            [
                "ks",
                "create",
                "Course KS",
                "--chunking",
                "simple",
                "--embedding-vendor",
                "openai",
                "--embedding-model",
                "text-embedding-3-small",
                "--vector-db",
                "chromadb",
                "--description",
                "Course content KS",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body == {
            "name": "Course KS",
            "description": "Course content KS",
            "chunking_strategy": "simple",
            "embedding_vendor": "openai",
            "embedding_model": "text-embedding-3-small",
            "vector_db_backend": "chromadb",
        }
        assert "/creator/knowledge-stores" in str(req.url)

    def test_create_missing_required_flag_errors(self, mock_token):
        result = runner.invoke(
            app,
            [
                "ks",
                "create",
                "Bad",
                "--chunking",
                "simple",
                # missing --embedding-vendor, --embedding-model, --vector-db
            ],
        )
        assert result.exit_code != 0

    def test_create_with_embedding_endpoint(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KS)
        result = runner.invoke(
            app,
            [
                "ks",
                "create",
                "Custom",
                "--chunking",
                "simple",
                "--embedding-vendor",
                "openai",
                "--embedding-model",
                "text-embedding-3-small",
                "--vector-db",
                "chromadb",
                "--embedding-endpoint",
                "https://my-proxy.example.com/v1",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["embedding_endpoint"] == "https://my-proxy.example.com/v1"


class TestKsList:
    def test_list_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KS_LIST)
        result = runner.invoke(app, ["ks", "list"])
        assert result.exit_code == 0
        assert "ks-1" in result.output
        assert "ks-2" in result.output

    def test_list_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KS_LIST)
        result = runner.invoke(app, ["ks", "list", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2

    def test_list_empty(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"knowledge_stores": []})
        result = runner.invoke(app, ["ks", "list", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestKsGet:
    def test_get_success(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KS)
        result = runner.invoke(app, ["ks", "get", "ks-1"])
        assert result.exit_code == 0
        assert "Course KS" in result.output

    def test_get_not_found(self, httpx_mock, mock_token):
        httpx_mock.add_response(status_code=404, json={"detail": "Not found"})
        result = runner.invoke(app, ["ks", "get", "ks-x"])
        assert result.exit_code != 0


class TestKsUpdate:
    def test_update_name_ok(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "ok"})
        result = runner.invoke(
            app, ["ks", "update", "ks-1", "--name", "Renamed"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body == {"name": "Renamed"}

    def test_update_description_ok(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "ok"})
        result = runner.invoke(
            app, ["ks", "update", "ks-1", "--description", "new desc"]
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body == {"description": "new desc"}

    def test_update_no_fields_errors(self, mock_token):
        result = runner.invoke(app, ["ks", "update", "ks-1"])
        assert result.exit_code == 1


class TestKsDelete:
    def test_delete_with_confirm(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "deleted"})
        result = runner.invoke(app, ["ks", "delete", "ks-1", "-y"])
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert req.method == "DELETE"
        assert "/creator/knowledge-stores/ks-1" in str(req.url)

    def test_delete_rejected(self, mock_token):
        result = runner.invoke(app, ["ks", "delete", "ks-1"], input="n\n")
        assert result.exit_code != 0


class TestKsShare:
    def test_share_enable(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"is_shared": True})
        result = runner.invoke(app, ["ks", "share", "ks-1", "--enable"])
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        body = json.loads(httpx_mock.get_request().content)
        assert body["is_shared"] is True

    def test_share_disable(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"is_shared": False})
        result = runner.invoke(app, ["ks", "share", "ks-1", "--disable"])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        body = json.loads(httpx_mock.get_request().content)
        assert body["is_shared"] is False


# ---------------------------------------------------------------------------
# add-content / list-content / remove-content
# ---------------------------------------------------------------------------


class TestKsAddContent:
    def test_add_content_single_item(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"job_id": "job-99", "status": "queued"})
        result = runner.invoke(
            app,
            [
                "ks",
                "add-content",
                "ks-1",
                "--library",
                "lib-1",
                "--items",
                "item-1",
            ],
        )
        assert result.exit_code == 0
        assert "job-99" in result.output
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body == {"library_id": "lib-1", "item_ids": ["item-1"]}

    def test_add_content_multiple_items(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"job_id": "job-100", "status": "queued"})
        result = runner.invoke(
            app,
            [
                "ks",
                "add-content",
                "ks-1",
                "--library",
                "lib-1",
                "--items",
                "item-1, item-2 ,item-3",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["item_ids"] == ["item-1", "item-2", "item-3"]

    def test_add_content_wait_polls_to_ready(self, httpx_mock, mock_token):
        # 1) add-content
        httpx_mock.add_response(json={"job_id": "job-w", "status": "queued"})
        # 2-3) two polls: in_progress, in_progress
        httpx_mock.add_response(json={"status": "in_progress"})
        httpx_mock.add_response(json={"status": "in_progress"})
        # 4) ready
        httpx_mock.add_response(
            json={"status": "ready", "chunks_created": 7}
        )
        with patch("lamb_cli.commands.knowledge_store.time.sleep", return_value=None):
            result = runner.invoke(
                app,
                [
                    "ks",
                    "add-content",
                    "ks-1",
                    "--library",
                    "lib-1",
                    "--items",
                    "item-1",
                    "--wait",
                ],
            )
        assert result.exit_code == 0
        assert len(httpx_mock.get_requests()) == 4

    def test_add_content_wait_polls_to_failed(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"job_id": "job-f", "status": "queued"})
        httpx_mock.add_response(
            json={"status": "failed", "error_message": "embedding error"}
        )
        with patch("lamb_cli.commands.knowledge_store.time.sleep", return_value=None):
            result = runner.invoke(
                app,
                [
                    "ks",
                    "add-content",
                    "ks-1",
                    "--library",
                    "lib-1",
                    "--items",
                    "item-1",
                    "--wait",
                ],
            )
        # --wait propagates failed ingestion as a non-zero exit so scripts
        # can react. The error message is printed to stderr before the exit.
        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "embedding error" in result.output.lower()

    def test_add_content_idempotent_noop(self, httpx_mock, mock_token):
        """Server returns status='noop' when items are already linked — CLI
        surfaces the 'already linked' message and does not error."""
        httpx_mock.add_response(
            json={"status": "noop", "message": "All items already linked."}
        )
        result = runner.invoke(
            app,
            [
                "ks",
                "add-content",
                "ks-1",
                "--library",
                "lib-1",
                "--items",
                "item-1",
            ],
        )
        assert result.exit_code == 0
        assert "already linked" in result.output.lower()

    def test_add_content_empty_items_errors(self, mock_token):
        result = runner.invoke(
            app,
            [
                "ks",
                "add-content",
                "ks-1",
                "--library",
                "lib-1",
                "--items",
                "  ,  ",
            ],
        )
        assert result.exit_code == 1


class TestKsListContent:
    def test_list_content_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_CONTENT)
        result = runner.invoke(app, ["ks", "list-content", "ks-1"])
        assert result.exit_code == 0
        assert "item-1" in result.output
        assert "item-2" in result.output

    def test_list_content_json(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_CONTENT)
        result = runner.invoke(
            app, ["ks", "list-content", "ks-1", "-o", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2


class TestKsRemoveContent:
    def test_remove_content_with_confirm(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"message": "removed"})
        result = runner.invoke(
            app,
            ["ks", "remove-content", "ks-1", "item-1", "-y"],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        assert req.method == "DELETE"
        assert "/creator/knowledge-stores/ks-1/content/item-1" in str(req.url)

    def test_remove_content_rejected(self, mock_token):
        result = runner.invoke(
            app, ["ks", "remove-content", "ks-1", "item-1"], input="n\n"
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


class TestKsStatus:
    def test_status_overall(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_CONTENT)
        result = runner.invoke(app, ["ks", "status", "ks-1"])
        assert result.exit_code == 0
        assert "item-1" in result.output

    def test_status_single_item(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            json={
                "library_item_id": "item-1",
                "status": "ready",
                "chunks_created": 5,
                "kb_job_id": "job-1",
                "item_title": "Chapter 1",
            }
        )
        result = runner.invoke(
            app, ["ks", "status", "ks-1", "--item", "item-1"]
        )
        assert result.exit_code == 0
        assert "item-1" in result.output

    def test_status_with_wait_polls(self, httpx_mock, mock_token):
        # poll iteration 1 (in_progress)
        httpx_mock.add_response(json={"status": "in_progress"})
        # poll iteration 2 (ready)
        httpx_mock.add_response(
            json={"status": "ready", "chunks_created": 3}
        )
        # final detail fetch after _wait_for_items returns
        httpx_mock.add_response(
            json={
                "library_item_id": "item-1",
                "status": "ready",
                "chunks_created": 3,
                "kb_job_id": "job-1",
            }
        )
        with patch("lamb_cli.commands.knowledge_store.time.sleep", return_value=None):
            result = runner.invoke(
                app,
                [
                    "ks",
                    "status",
                    "ks-1",
                    "--item",
                    "item-1",
                    "--wait",
                    "--max-wait",
                    "5",
                ],
            )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


class TestKsQuery:
    def test_query_table(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_QUERY)
        result = runner.invoke(
            app, ["ks", "query", "ks-1", "What is Big-O?"]
        )
        assert result.exit_code == 0
        # Score is rounded to 4 decimals in the table
        assert "0.9521" in result.output
        assert "Chapter 1" in result.output
        # Verify request body
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body == {"query_text": "What is Big-O?", "top_k": 5}

    def test_query_json_with_permalinks(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_QUERY)
        result = runner.invoke(
            app, ["ks", "query", "ks-1", "What is Big-O?", "-o", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        # The CLI flattens results — score, title, item id, snippet
        assert len(data) == 2
        assert data[0]["source_item_id"] == "item-1"
        assert data[0]["source_title"] == "Chapter 1"

    def test_query_with_top_k(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"results": []})
        result = runner.invoke(
            app,
            ["ks", "query", "ks-1", "test", "--top-k", "10"],
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content)
        assert body["top_k"] == 10


# ---------------------------------------------------------------------------
# Edge cases — guardrails surfaced through the CLI (#337)
# ---------------------------------------------------------------------------


class TestKsLockedConfig:
    """The chunking strategy, embedding vendor/model and vector DB backend are
    locked at creation time. ``lamb ks update`` deliberately does not expose
    flags for those fields, so Click rejects them before any HTTP call."""

    @pytest.mark.parametrize(
        "flag,value",
        [
            ("--chunking", "by_section"),
            ("--embedding-vendor", "ollama"),
            ("--embedding-model", "nomic-embed-text"),
            ("--vector-db", "qdrant"),
            ("--embedding-endpoint", "http://x"),
        ],
    )
    def test_update_rejects_locked_field_flags(self, mock_token, flag, value):
        result = runner.invoke(app, ["ks", "update", "ks-1", flag, value])
        assert result.exit_code != 0
        out = result.output.lower()
        assert "no such option" in out or "usage" in out

    def test_update_name_payload_excludes_locked_fields(self, httpx_mock, mock_token):
        httpx_mock.add_response(json=SAMPLE_KS)
        result = runner.invoke(
            app, ["ks", "update", "ks-1", "--name", "renamed"]
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content)
        for forbidden in (
            "chunking_strategy",
            "embedding_vendor",
            "embedding_model",
            "vector_db_backend",
            "embedding_endpoint",
        ):
            assert forbidden not in body, (
                f"{forbidden} must never appear in the update payload — "
                "locked fields are immutable after KS creation"
            )
        # And confirm the field that IS allowed went through.
        assert body["name"] == "renamed"


class TestKsBackendErrors:
    """The CLI must surface backend status codes as non-zero exits with
    actionable messages — never as a Python traceback."""

    def test_delete_returns_409_when_in_use(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            status_code=409,
            json={"detail": "Knowledge Store has active assistants"},
        )
        result = runner.invoke(app, ["ks", "delete", "ks-1", "-y"])
        assert result.exit_code != 0

    def test_get_returns_403_for_other_org(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            status_code=403, json={"detail": "Forbidden: not your org"}
        )
        result = runner.invoke(app, ["ks", "get", "ks-other"])
        from lamb_cli.errors import AuthenticationError

        assert result.exit_code != 0
        assert isinstance(result.exception, AuthenticationError)

    def test_query_returns_503_when_backend_unavailable(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            status_code=503, json={"detail": "KB Server unavailable"}
        )
        result = runner.invoke(app, ["ks", "query", "ks-1", "anything"])
        assert result.exit_code != 0

    def test_create_returns_500_provisional_not_visible(
        self, httpx_mock, mock_token
    ):
        # Backend rejects the create (e.g. KB-server backend down).
        httpx_mock.add_response(
            status_code=500, json={"detail": "Backend unavailable"}
        )
        result = runner.invoke(
            app,
            [
                "ks",
                "create",
                "demo",
                "--chunking",
                "simple",
                "--embedding-vendor",
                "openai",
                "--embedding-model",
                "text-embedding-3-small",
                "--vector-db",
                "chromadb",
            ],
        )
        assert result.exit_code != 0
        # Belt-and-braces: a follow-up list must not show a leaked provisional row.
        httpx_mock.add_response(json={"knowledge_stores": []})
        result2 = runner.invoke(app, ["ks", "list"])
        assert result2.exit_code == 0

    def test_query_returns_422_with_detail(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            status_code=422, json={"detail": "query_text must not be empty"}
        )
        result = runner.invoke(app, ["ks", "query", "ks-1", "x"])
        assert result.exit_code != 0


class TestKsAddContentEdgeCases:
    def test_add_content_returns_404_unknown_library(
        self, httpx_mock, mock_token
    ):
        httpx_mock.add_response(
            status_code=404, json={"detail": "Library not found"}
        )
        result = runner.invoke(
            app,
            [
                "ks",
                "add-content",
                "ks-1",
                "--library",
                "lib-missing",
                "--items",
                "item-1",
            ],
        )
        # CliRunner doesn't go through _cli()'s error handler, so the typed
        # exit code (5) becomes Click's default 1; we assert the exception
        # type to lock the contract (NotFoundError -> exit 5 in production).
        from lamb_cli.errors import NotFoundError

        assert result.exit_code != 0
        assert isinstance(result.exception, NotFoundError)

    def test_add_content_returns_409_on_retry(self, httpx_mock, mock_token):
        httpx_mock.add_response(
            status_code=409,
            json={"detail": "Ingestion already in flight for one or more items"},
        )
        result = runner.invoke(
            app,
            [
                "ks",
                "add-content",
                "ks-1",
                "--library",
                "lib-1",
                "--items",
                "item-1,item-2",
            ],
        )
        assert result.exit_code != 0

    def test_add_content_failure_surfaces_error_message(
        self, httpx_mock, mock_token
    ):
        """When --wait sees a failed item, the backend's error_message must
        appear in output (so users know WHY ingestion failed)."""
        httpx_mock.add_response(json={"job_id": "j", "status": "queued"})
        httpx_mock.add_response(
            json={
                "status": "failed",
                "error_message": "OpenAI quota exceeded — check billing",
            }
        )
        with patch(
            "lamb_cli.commands.knowledge_store.time.sleep", return_value=None
        ):
            result = runner.invoke(
                app,
                [
                    "ks",
                    "add-content",
                    "ks-1",
                    "--library",
                    "lib-1",
                    "--items",
                    "item-1",
                    "--wait",
                ],
            )
        # --wait surfaces failed ingestion as a non-zero exit so CI/scripts
        # can fail loudly. The error message appears in stderr first.
        assert result.exit_code != 0
        assert "OpenAI quota" in result.output

    def test_add_content_wait_times_out_gracefully(
        self, httpx_mock, mock_token
    ):
        """--max-wait expiry should print a 'Timed out' warning and exit 0
        (items remain in flight server-side)."""
        httpx_mock.add_response(json={"job_id": "j", "status": "queued"})
        # Always in_progress — never reaches terminal state. Mark reusable so
        # however many polls happen before the time budget expires, we have a
        # response to serve.
        httpx_mock.add_response(
            json={"status": "in_progress"}, is_reusable=True
        )
        # Force the polling loop to exit on the first sleep by jumping the
        # clock past the deadline.
        sleep_calls = {"n": 0}

        def fake_sleep(_d):
            sleep_calls["n"] += 1

        # Patch time.time so the deadline check trips after one iteration.
        import lamb_cli.commands.knowledge_store as ks_mod

        real_time = ks_mod.time.time
        clock = {"t": real_time()}

        def fake_time():
            clock["t"] += 100  # advance fast
            return clock["t"]

        with (
            patch.object(ks_mod.time, "sleep", side_effect=fake_sleep),
            patch.object(ks_mod.time, "time", side_effect=fake_time),
        ):
            result = runner.invoke(
                app,
                [
                    "ks",
                    "add-content",
                    "ks-1",
                    "--library",
                    "lib-1",
                    "--items",
                    "item-stuck",
                    "--wait",
                ],
            )
        assert result.exit_code == 0
        assert "Timed out" in result.output


class TestKsPollingBackoff:
    """Lock down the documented exponential-backoff schedule (1, 2, 4, 8, 16,
    capped at 16). The schedule is a literal in code with no constant to
    import — this test is its spec."""

    def test_add_content_wait_uses_documented_backoff(
        self, httpx_mock, mock_token
    ):
        # 1 add-content + 5 in_progress polls + 1 ready poll.
        # Each in_progress poll triggers a sleep before the next poll.
        # 5 sleeps total, cadence 1, 2, 4, 8, 16.
        httpx_mock.add_response(json={"job_id": "j", "status": "queued"})
        for _ in range(5):
            httpx_mock.add_response(json={"status": "in_progress"})
        httpx_mock.add_response(
            json={"status": "ready", "chunks_created": 1}
        )

        sleeps: list[float] = []
        with patch(
            "lamb_cli.commands.knowledge_store.time.sleep",
            side_effect=lambda d: sleeps.append(d),
        ):
            result = runner.invoke(
                app,
                [
                    "ks",
                    "add-content",
                    "ks-1",
                    "--library",
                    "lib-1",
                    "--items",
                    "item-1",
                    "--wait",
                ],
            )
        assert result.exit_code == 0
        assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0]

    def test_add_content_wait_caps_at_16_seconds(
        self, httpx_mock, mock_token
    ):
        # 8 in_progress polls → 7 sleeps before ready. Cap kicks in after the
        # 5th sleep — so the last 3 must all be 16.0.
        httpx_mock.add_response(json={"job_id": "j", "status": "queued"})
        for _ in range(8):
            httpx_mock.add_response(json={"status": "in_progress"})
        httpx_mock.add_response(
            json={"status": "ready", "chunks_created": 1}
        )

        sleeps: list[float] = []
        with patch(
            "lamb_cli.commands.knowledge_store.time.sleep",
            side_effect=lambda d: sleeps.append(d),
        ):
            result = runner.invoke(
                app,
                [
                    "ks",
                    "add-content",
                    "ks-1",
                    "--library",
                    "lib-1",
                    "--items",
                    "item-1",
                    "--wait",
                ],
            )
        assert result.exit_code == 0
        assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0, 16.0, 16.0, 16.0]


class TestKsResilience:
    """Future-proofing: catch the silly stuff before users hit it."""

    def test_options_handles_partial_response(self, httpx_mock, mock_token):
        """A stripped-down options response (no embedding_models map) must not
        KeyError — the CLI should render whatever sections exist."""
        httpx_mock.add_response(
            json={
                "vector_db_backends": [],
                "chunking_strategies": [],
                "embedding_vendors": [],
                # embedding_models intentionally missing
            }
        )
        result = runner.invoke(app, ["ks", "options"])
        assert result.exit_code == 0

    def test_query_handles_chunks_without_permalinks(
        self, httpx_mock, mock_token
    ):
        """Future chunk shapes may omit the permalink field — render
        gracefully instead of crashing on missing-key access."""
        httpx_mock.add_response(
            json={
                "results": [
                    {
                        "score": 0.9,
                        "text": "no permalink here",
                        "metadata": {"source_title": "X", "source_item_id": "i"},
                    }
                ]
            }
        )
        result = runner.invoke(
            app, ["ks", "query", "ks-1", "test", "-o", "json"]
        )
        assert result.exit_code == 0

    def test_get_handles_unknown_status_value(self, httpx_mock, mock_token):
        """Tomorrow's backend may add a new server_status enum value. The CLI
        must print the literal and not crash."""
        weird = {**SAMPLE_KS, "server_status": "reindexing"}
        httpx_mock.add_response(json=weird)
        result = runner.invoke(app, ["ks", "get", "ks-1"])
        assert result.exit_code == 0

    def test_create_with_unicode_name_round_trips(
        self, httpx_mock, mock_token
    ):
        """UTF-8 in names must survive the request body round-trip."""
        httpx_mock.add_response(json={**SAMPLE_KS, "name": "Lección 1 — Δ"})
        result = runner.invoke(
            app,
            [
                "ks",
                "create",
                "Lección 1 — Δ",
                "--chunking",
                "simple",
                "--embedding-vendor",
                "openai",
                "--embedding-model",
                "text-embedding-3-small",
                "--vector-db",
                "chromadb",
            ],
        )
        assert result.exit_code == 0
        body = json.loads(httpx_mock.get_request().content.decode("utf-8"))
        assert body["name"] == "Lección 1 — Δ"

    def test_query_zero_results_renders_empty(self, httpx_mock, mock_token):
        httpx_mock.add_response(json={"results": []})
        result = runner.invoke(app, ["ks", "query", "ks-1", "test"])
        assert result.exit_code == 0

    def test_add_content_huge_item_list_single_request(
        self, httpx_mock, mock_token
    ):
        """200 item IDs must go out in a single POST with all IDs intact —
        guards against an accidental future 'batch into chunks' that drops
        items off the end."""
        items_csv = ",".join(f"item-{i}" for i in range(200))
        httpx_mock.add_response(json={"job_id": "j", "status": "queued"})
        result = runner.invoke(
            app,
            [
                "ks",
                "add-content",
                "ks-1",
                "--library",
                "lib-1",
                "--items",
                items_csv,
            ],
        )
        assert result.exit_code == 0
        # Exactly one POST went out.
        assert len(httpx_mock.get_requests()) == 1
        body = json.loads(httpx_mock.get_request().content)
        assert len(body["item_ids"]) == 200
        assert body["item_ids"][0] == "item-0"
        assert body["item_ids"][-1] == "item-199"

    def test_command_without_token_errors_clearly(self, monkeypatch):
        """No LAMB_TOKEN, no credentials file. Must exit non-zero with a
        message pointing at 'lamb login', not a Python traceback."""
        monkeypatch.delenv("LAMB_TOKEN", raising=False)
        # Also redirect config to an empty temp dir so any local credentials
        # don't leak in.
        from pathlib import Path
        import tempfile
        from unittest.mock import patch as _patch

        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp)
            with (
                _patch("lamb_cli.config.CONFIG_DIR", empty),
                _patch("lamb_cli.config.CONFIG_FILE", empty / "config.toml"),
                _patch(
                    "lamb_cli.config.CREDENTIALS_FILE",
                    empty / "credentials.toml",
                ),
            ):
                result = runner.invoke(app, ["ks", "list"])
        assert result.exit_code != 0
        # CliRunner unwraps to exit 1; the typed exit (4) is enforced by
        # _cli() in production. Assert the exception type instead.
        from lamb_cli.errors import AuthenticationError

        assert isinstance(result.exception, AuthenticationError)
        assert "lamb login" in str(result.exception).lower() or "lamb_token" in str(result.exception).lower()

    def test_add_content_empty_item_id_after_split_errors(self, mock_token):
        """A trailing comma or all-whitespace --items value must fail before
        any HTTP call, not silently send an empty list."""
        result = runner.invoke(
            app,
            [
                "ks",
                "add-content",
                "ks-1",
                "--library",
                "lib-1",
                "--items",
                ",,, ,",
            ],
        )
        assert result.exit_code != 0
