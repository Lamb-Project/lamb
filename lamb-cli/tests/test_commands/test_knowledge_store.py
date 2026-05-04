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
        # The CLI command itself succeeds (exit 0); the failure is reported
        # via stderr, not via exit code.
        assert result.exit_code == 0
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
