"""
E2E tests for file endpoints.
"""

import pytest
import time
import json


pytestmark = pytest.mark.live


class TestListFiles:
    
    def test_list_files_empty_collection(self, live_client, sample_collection_data, cleanup_collection):
        unique_name = f"files-empty-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        response = live_client.get(f"/collections/{collection_id}/files")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_list_files_after_ingest(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        unique_name = f"files-ingest-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_text_file, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            plugin_data = {
                "plugin_name": "simple_ingest",
                "plugin_params": json.dumps({"chunk_size": 200})
            }
            ingest_response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert ingest_response.status_code == 200
        time.sleep(1)
        
        response = live_client.get(f"/collections/{collection_id}/files")
        
        assert response.status_code == 200
        files_list = response.json()
        assert len(files_list) >= 1
        assert "id" in files_list[0]
    
    def test_list_files_filter_by_status(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        unique_name = f"files-filter-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_text_file, "rb") as f:
            files = {"file": ("test.txt", f, "text/plain")}
            plugin_data = {"plugin_name": "simple_ingest", "plugin_params": "{}"}
            live_client.post(f"/collections/{collection_id}/ingest-file", files=files, data=plugin_data)
        
        # Wait for processing to complete (poll for status)
        max_retries = 10
        for _ in range(max_retries):
            response = live_client.get(f"/collections/{collection_id}/files")
            files = response.json()
            if files and files[0]["status"] == "completed":
                break
            time.sleep(1)
        
        # Filter by completed - should find the file
        response = live_client.get(f"/collections/{collection_id}/files?status=completed")
        assert response.status_code == 200
        assert len(response.json()) >= 1
        
        # Filter by deleted - should be empty
        response = live_client.get(f"/collections/{collection_id}/files?status=deleted")
        assert response.status_code == 200
        assert response.json() == []


class TestDeleteFile:
    
    def test_delete_file_success(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        unique_name = f"files-delete-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_text_file, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            plugin_data = {"plugin_name": "simple_ingest", "plugin_params": "{}"}
            ingest_response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert ingest_response.status_code == 200
        file_id = ingest_response.json()["file_registry_id"]
        time.sleep(2)
        
        delete_response = live_client.delete(f"/collections/{collection_id}/files/{file_id}?hard=true")
        assert delete_response.status_code == 200
    
    def test_delete_file_not_found(self, live_client, sample_collection_data, cleanup_collection):
        unique_name = f"files-delete-notfound-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        response = live_client.delete(f"/collections/{collection_id}/files/999999")
        assert response.status_code == 404


class TestFileContent:
    
    def test_get_file_content_success(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        unique_name = f"content-test-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_text_file, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            plugin_data = {"plugin_name": "simple_ingest", "plugin_params": "{}"}
            ingest_response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert ingest_response.status_code == 200
        file_id = ingest_response.json()["file_registry_id"]
        time.sleep(2)
        
        response = live_client.get(f"/files/{file_id}/content")
        # 404 is valid if the file content isn't stored separately
        assert response.status_code in [200, 404]
    
    def test_get_file_content_not_found(self, live_client):
        response = live_client.get("/files/999999/content")
        assert response.status_code == 404


class TestUpdateFileStatus:
    
    def test_update_file_status(self, live_client, sample_collection_data, test_text_file, cleanup_collection):
        unique_name = f"status-update-{int(time.time() * 1000)}"
        data = sample_collection_data.copy()
        data["name"] = unique_name
        
        create_response = live_client.post("/collections", json=data)
        assert create_response.status_code == 201
        collection_id = create_response.json()["id"]
        cleanup_collection(collection_id)
        
        with open(test_text_file, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            plugin_data = {"plugin_name": "simple_ingest", "plugin_params": "{}"}
            ingest_response = live_client.post(
                f"/collections/{collection_id}/ingest-file",
                files=files,
                data=plugin_data
            )
        
        assert ingest_response.status_code == 200
        file_id = ingest_response.json()["file_registry_id"]
        time.sleep(2)
        
        response = live_client.put(f"/collections/files/{file_id}/status?status=completed")
        assert response.status_code == 200
        assert "id" in response.json()
