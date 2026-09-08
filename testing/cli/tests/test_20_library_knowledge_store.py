"""Live Library -> Knowledge Store -> retrieval checks, using OpenAI embeddings.

Runs against the configured test instance. Creates synthetic fixtures only.
No Ollama/local models are selected. Resources remain available for inspection.
"""
import time
import httpx
import pytest


class TestLibraryKnowledgeStore:
    library_id = ""
    item_id = ""
    store_id = ""
    marker = "QA-CROSS-SERVICE-9261"

    def test_create_library(self, cli, timestamp):
        result = cli.run_json("library", "create", f"cli_library_{timestamp}")
        result.assert_success()
        TestLibraryKnowledgeStore.library_id = result.json["id"]
        detail = cli.run_json("library", "get", self.library_id).assert_success()
        assert detail.json["id"] == self.library_id

    def test_import_document_and_read_content(self, cli, tmp_path):
        assert self.library_id
        document = tmp_path / "field-guide.md"
        document.write_text(f"# Field guide\nVerification: {self.marker}. Inspection interval: 43 days.")
        cli.run("library", "upload", self.library_id, str(document),
                "--plugin", "simple_import", "--wait", "--max-wait", "30").assert_success()
        result = cli.run_json("library", "items", self.library_id).assert_success()
        items = result.json if isinstance(result.json, list) else result.json["items"]
        assert len(items) == 1
        TestLibraryKnowledgeStore.item_id = items[0]["id"]
        content = cli.run("library", "item-content", self.library_id, self.item_id).assert_success()
        assert self.marker in content.stdout

    def test_create_knowledge_store(self, cli, timestamp):
        result = cli.run_json("ks", "create", f"cli_ks_{timestamp}", "--chunking", "simple",
                              "--embedding-vendor", "openai", "--embedding-model", "text-embedding-3-small",
                              "--embedding-endpoint", "https://api.openai.com/v1", "--vector-db", "chromadb")
        result.assert_success()
        TestLibraryKnowledgeStore.store_id = result.json["id"]

    def test_ingest_and_confirm_real_chunks(self, cli, server_url, admin_token):
        assert self.store_id and self.item_id
        cli.run("ks", "add-content", self.store_id, "--library", self.library_id,
                "--items", self.item_id).assert_success()
        with httpx.Client(base_url=server_url, headers={"Authorization": f"Bearer {admin_token}"}, timeout=30) as api:
            for _ in range(30):
                response = api.get(f"/creator/knowledge-stores/{self.store_id}/content/{self.item_id}")
                response.raise_for_status()
                data = response.json()
                if data["status"] in ("ready", "failed"):
                    break
                time.sleep(1)
        assert data["status"] == "ready", data
        assert data["chunks_created"] > 0

    def test_cli_lists_content_and_library_filter(self, cli):
        assert self.store_id and self.item_id
        for args in ((), ("--library", self.library_id)):
            result = cli.run_json("ks", "list-content", self.store_id, *args).assert_success()
            assert any(item["library_item_id"] == self.item_id for item in result.json)
        reverse = cli.run_json("library", "list-knowledge-stores", self.library_id).assert_success()
        assert self.store_id in str(reverse.json)

    def test_query_and_linked_document_protection(self, server_url, admin_token):
        assert self.store_id and self.item_id
        with httpx.Client(base_url=server_url, headers={"Authorization": f"Bearer {admin_token}"}, timeout=60) as api:
            response = api.post(f"/creator/knowledge-stores/{self.store_id}/query",
                                json={"query_text": "verification inspection interval", "top_k": 3})
            response.raise_for_status()
            hits = response.json()["results"]
            assert any(self.marker in hit["text"] for hit in hits)
            assert hits[0]["metadata"]["permalink_markdown"].startswith("/docs/")
            blocked = api.delete(f"/creator/libraries/{self.library_id}/items/{self.item_id}")
            assert blocked.status_code == 409
