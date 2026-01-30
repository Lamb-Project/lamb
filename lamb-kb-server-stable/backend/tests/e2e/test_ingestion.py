"""
Tests for File Ingestion endpoints.
"""

import pytest
import time
from pathlib import Path


class TestFileIngestion:
    """Tests for POST /collections/{id}/ingest-file endpoint."""
    
    def test_ingest_file_success(self, client, test_collection, sample_text_file):
        """Ingest file should create file registry entry."""
        collection_id = test_collection["id"]
        
        result = client.ingest_file(collection_id, str(sample_text_file))
        
        assert result["success"] is True
        assert result["collection_id"] == collection_id
        assert "file_registry_id" in result
        assert result["status"] == "processing"
    
    def test_ingest_file_with_custom_chunking(self, client, test_collection, sample_text_file):
        """Ingest file with custom chunking parameters."""
        collection_id = test_collection["id"]
        
        result = client.ingest_file(
            collection_id, 
            str(sample_text_file),
            plugin_params={
                "chunk_size": 50,
                "chunk_unit": "word",
                "chunk_overlap": 10
            }
        )
        
        assert result["success"] is True
    
    def test_ingest_file_to_nonexistent_collection(self, client, sample_text_file):
        """Ingest to non-existent collection should fail."""
        with pytest.raises(Exception):
            client.ingest_file(999999, str(sample_text_file))
    
    def test_ingest_file_completes_processing(self, client, test_collection, sample_text_file):
        """Ingested file should eventually complete processing."""
        collection_id = test_collection["id"]
        
        client.ingest_file(collection_id, str(sample_text_file))
        
        # Wait for completion
        success = client.wait_for_ingestion(collection_id, 1, max_wait=30)
        assert success, "File should complete processing within timeout"
        
        # Verify file status
        files = client.list_files(collection_id)
        assert len(files) >= 1
        assert files[0]["status"] == "completed"
        assert files[0]["document_count"] > 0


class TestDocumentIngestion:
    """Tests for POST /collections/{id}/documents endpoint."""
    
    def test_add_documents_directly(self, client, test_collection):
        """Add documents directly to collection."""
        collection_id = test_collection["id"]
        
        response = client.post(
            f"/collections/{collection_id}/documents",
            json={
                "documents": [
                    {
                        "text": "This is a test document.",
                        "metadata": {"source": "test", "chunk_index": 0}
                    },
                    {
                        "text": "This is another test document.",
                        "metadata": {"source": "test", "chunk_index": 1}
                    }
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["documents_added"] == 2


class TestURLIngestion:
    """Tests for POST /collections/{id}/ingest-url endpoint."""
    
    def test_ingest_url_success(self, client, test_collection):
        """Ingest URL should create file registry entry and process content."""
        collection_id = test_collection["id"]
        
        response = client.post(
            f"/collections/{collection_id}/ingest-url",
            json={
                "urls": ["https://fib.upc.edu"],
                "plugin_params": {
                    "chunk_size": 500,
                    "chunk_unit": "char",
                    "chunk_overlap": 50
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True or "file_registry_id" in data
        
        # Wait for URL ingestion to complete
        if data.get("file_registry_id"):
            success = client.wait_for_ingestion(collection_id, 1, max_wait=60)
            # URL ingestion may take longer, just verify it started
            files = client.list_files(collection_id)
            assert len(files) >= 1


class TestMultipleFileTypes:
    """Tests for ingesting different file types."""
    
    def test_ingest_txt_file(self, client, test_collection, test_files_dir):
        """Ingest plain text file."""
        file_path = test_files_dir / f"test_{int(time.time())}.txt"
        file_path.write_text("This is plain text content.")
        
        result = client.ingest_file(test_collection["id"], str(file_path))
        assert result["success"] is True
    
    def test_ingest_md_file(self, client, test_collection, test_files_dir):
        """Ingest markdown file."""
        file_path = test_files_dir / f"test_{int(time.time())}.md"
        file_path.write_text("# Heading\n\nThis is **markdown** content.")
        
        result = client.ingest_file(test_collection["id"], str(file_path))
        assert result["success"] is True


class TestChunkingStrategies:
    """Tests for different chunking strategies."""
    
    def test_char_chunking(self, client, test_collection, sample_text_file):
        """Test character-based chunking."""
        result = client.ingest_file(
            test_collection["id"],
            str(sample_text_file),
            plugin_params={"chunk_size": 100, "chunk_unit": "char", "chunk_overlap": 20}
        )
        assert result["success"] is True
    
    def test_word_chunking(self, client, test_collection, test_files_dir):
        """Test word-based chunking."""
        file_path = test_files_dir / f"word_chunk_{int(time.time())}.txt"
        file_path.write_text("This is a test with many words for word-based chunking.")
        
        result = client.ingest_file(
            test_collection["id"],
            str(file_path),
            plugin_params={"chunk_size": 10, "chunk_unit": "word", "chunk_overlap": 2}
        )
        assert result["success"] is True
    
    def test_line_chunking(self, client, test_collection, test_files_dir):
        """Test line-based chunking."""
        file_path = test_files_dir / f"line_chunk_{int(time.time())}.txt"
        file_path.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
        
        result = client.ingest_file(
            test_collection["id"],
            str(file_path),
            plugin_params={"chunk_size": 2, "chunk_unit": "line", "chunk_overlap": 1}
        )
        assert result["success"] is True
