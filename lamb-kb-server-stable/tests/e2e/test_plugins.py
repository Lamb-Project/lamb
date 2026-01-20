"""
E2E tests for ingestion plugins.
"""

import pytest
import time
import json
from pathlib import Path


pytestmark = pytest.mark.live


@pytest.fixture
def test_markdown_file(tmp_path) -> Path:
    file_path = tmp_path / "test_document.md"
    file_path.write_text("""# Machine Learning Guide

## Introduction
Machine learning is a branch of artificial intelligence that focuses on building 
systems that can learn from data.

## Types of ML
1. **Supervised Learning** - Uses labeled data
2. **Unsupervised Learning** - Finds patterns in unlabeled data  
3. **Reinforcement Learning** - Learns through trial and error

## Applications
- Natural language processing
- Computer vision
- Recommendation systems
""")
    return file_path


@pytest.fixture
def test_pdf_file(tmp_path) -> Path:
    """Minimal valid PDF for testing."""
    file_path = tmp_path / "test_document.pdf"
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Test PDF Document) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer << /Size 5 /Root 1 0 R >>
startxref
307
%%EOF"""
    file_path.write_bytes(pdf_content)
    return file_path


@pytest.fixture  
def test_youtube_file(tmp_path) -> Path:
    file_path = tmp_path / "youtube_urls.txt"
    file_path.write_text("https://www.youtube.com/watch?v=dQw4w9WgXcQ\n")
    return file_path


class TestSimpleIngestPlugin:
    
    def test_txt_default_params(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        unique_name = f"simple-txt-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_text_file, "rb") as f:
            files = {"file": ("test.txt", f, "text/plain")}
            plugin_data = {"plugin_name": "simple_ingest", "plugin_params": "{}"}
            response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "file_registry_id" in result
    
    def test_md_custom_chunking(self, live_client, sample_collection_data, test_markdown_file, cleanup_collection):
        unique_name = f"simple-md-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_markdown_file, "rb") as f:
            files = {"file": ("test.md", f, "text/markdown")}
            plugin_data = {
                "plugin_name": "simple_ingest",
                "plugin_params": json.dumps({
                    "chunk_size": 200,
                    "chunk_overlap": 50,
                    "splitter_type": "RecursiveCharacterTextSplitter"
                })
            }
            response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    def test_character_splitter(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        unique_name = f"simple-char-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_text_file, "rb") as f:
            files = {"file": ("test.txt", f, "text/plain")}
            plugin_data = {
                "plugin_name": "simple_ingest",
                "plugin_params": json.dumps({
                    "splitter_type": "CharacterTextSplitter",
                    "chunk_size": 500
                })
            }
            response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert response.status_code == 200


class TestMarkitdownPlusPlugin:
    
    def test_pdf_ingestion(self, live_client, sample_collection_data, test_pdf_file, cleanup_collection):
        unique_name = f"markitdown-pdf-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_pdf_file, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            plugin_data = {
                "plugin_name": "markitdown_plus_ingest",
                "plugin_params": json.dumps({
                    "chunk_size": 500,
                    "image_description_mode": "none"
                })
            }
            response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert response.status_code == 200
    
    def test_markdown_ingestion(self, live_client, sample_collection_data, test_markdown_file, cleanup_collection):
        unique_name = f"markitdown-md-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_markdown_file, "rb") as f:
            files = {"file": ("test.md", f, "text/markdown")}
            plugin_data = {
                "plugin_name": "markitdown_plus_ingest",
                "plugin_params": json.dumps({"chunk_size": 300, "chunk_overlap": 50})
            }
            response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestURLIngestPlugin:
    
    def test_url_ingestion(self, live_client, sample_collection_data, cleanup_collection):
        unique_name = f"url-ingest-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        url_request = {
            "urls": ["https://example.com"],
            "plugin_params": {"chunk_size": 500}
        }
        
        response = live_client.post(
            f"/collections/{collection_id}/ingest-url",
            json=url_request
        )
        
        assert response.status_code == 200
        assert "file_registry_id" in response.json()


class TestYouTubeTranscriptPlugin:
    
    def test_youtube_transcript_ingestion(self, live_client, sample_collection_data, test_youtube_file, cleanup_collection):
        unique_name = f"youtube-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_youtube_file, "rb") as f:
            files = {"file": ("youtube_urls.txt", f, "text/plain")}
            plugin_data = {
                "plugin_name": "youtube_transcript_ingest",
                "plugin_params": json.dumps({"chunk_duration": 60})
            }
            response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "file_registry_id" in result


class TestPluginDiscovery:
    
    def test_list_all_plugins(self, live_client):
        response = live_client.get("/ingestion/plugins")
        
        assert response.status_code == 200
        plugins = response.json()
        assert isinstance(plugins, list)
        
        plugin_names = [p["name"] for p in plugins]
        assert "simple_ingest" in plugin_names
    
    def test_plugin_has_required_fields(self, live_client):
        response = live_client.get("/ingestion/plugins")
        assert response.status_code == 200
        
        for plugin in response.json():
            assert "name" in plugin
            assert "kind" in plugin or "description" in plugin
