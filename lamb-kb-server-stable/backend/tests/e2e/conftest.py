"""
Pytest configuration and fixtures for lamb-kb-server API tests.
"""

import os
import json
import time
import pytest
import requests
from pathlib import Path
from typing import Dict, Any, Optional, Generator


# Test configuration
BASE_URL = os.getenv("KB_SERVER_URL", "http://localhost:9090")
API_KEY = os.getenv("KB_SERVER_API_KEY", "0p3n-w3bu!")


class LambKBClient:
    """Client for interacting with the lamb-kb-server API."""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a request to the API and return the response object."""
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", self.headers.copy())
        timeout = kwargs.pop("timeout", 60)
        
        response = requests.request(
            method, 
            url, 
            headers=headers, 
            timeout=timeout,
            **kwargs
        )
        return response
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("get", endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("post", endpoint, **kwargs)
    
    def put(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("put", endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("delete", endpoint, **kwargs)
    
    # Collection operations
    def create_collection(self, name: str, owner: str = "test-user", **kwargs) -> Dict[str, Any]:
        data = {
            "name": name,
            "description": kwargs.get("description", "Test collection"),
            "owner": owner,
            "visibility": kwargs.get("visibility", "private"),
            "embeddings_model": kwargs.get("embeddings_model", {
                "model": "default",
                "vendor": "default",
                "api_endpoint": "default",
                "apikey": "default"
            })
        }
        response = self.post("/collections", json=data)
        response.raise_for_status()
        return response.json()
    
    def get_collection(self, collection_id: int) -> Dict[str, Any]:
        response = self.get(f"/collections/{collection_id}")
        response.raise_for_status()
        return response.json()
    
    def list_collections(self, **kwargs) -> Dict[str, Any]:
        response = self.get("/collections", params=kwargs)
        response.raise_for_status()
        return response.json()
    
    def delete_collection(self, collection_id: int) -> Dict[str, Any]:
        response = self.delete(f"/collections/{collection_id}")
        response.raise_for_status()
        return response.json()
    
    # File ingestion
    def ingest_file(self, collection_id: int, file_path: str, 
                    plugin_name: str = "simple_ingest", 
                    plugin_params: Optional[Dict] = None) -> Dict[str, Any]:
        if plugin_params is None:
            plugin_params = {"chunk_size": 100, "chunk_unit": "char", "chunk_overlap": 20}
        
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f.read())}
            data = {
                "plugin_name": plugin_name,
                "plugin_params": json.dumps(plugin_params)
            }
            response = self.post(
                f"/collections/{collection_id}/ingest-file",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=data,
                files=files
            )
        response.raise_for_status()
        return response.json()
    
    # Query
    def query_collection(self, collection_id: int, query_text: str,
                         plugin_name: str = "simple_query",
                         top_k: int = 5, threshold: float = 0.0) -> Dict[str, Any]:
        data = {
            "query_text": query_text,
            "top_k": top_k,
            "threshold": threshold,
            "plugin_params": {}
        }
        response = self.post(
            f"/collections/{collection_id}/query",
            params={"plugin_name": plugin_name},
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    # Files
    def list_files(self, collection_id: int, status: Optional[str] = None) -> list:
        params = {"status": status} if status else {}
        response = self.get(f"/collections/{collection_id}/files", params=params)
        response.raise_for_status()
        return response.json()
    
    def delete_file(self, collection_id: int, file_id: int, hard: bool = True) -> Dict[str, Any]:
        response = self.delete(
            f"/collections/{collection_id}/files/{file_id}",
            params={"hard": hard}
        )
        response.raise_for_status()
        return response.json()
    
    # Ingestion jobs
    def list_ingestion_jobs(self, collection_id: int, **kwargs) -> Dict[str, Any]:
        response = self.get(f"/collections/{collection_id}/ingestion-jobs", params=kwargs)
        response.raise_for_status()
        return response.json()
    
    def get_ingestion_job(self, collection_id: int, job_id: int) -> Dict[str, Any]:
        response = self.get(f"/collections/{collection_id}/ingestion-jobs/{job_id}")
        response.raise_for_status()
        return response.json()
    
    def get_ingestion_summary(self, collection_id: int) -> Dict[str, Any]:
        response = self.get(f"/collections/{collection_id}/ingestion-status")
        response.raise_for_status()
        return response.json()
    
    # System
    def health_check(self) -> Dict[str, Any]:
        response = self.get("/health")
        response.raise_for_status()
        return response.json()
    
    def database_status(self) -> Dict[str, Any]:
        response = self.get("/database/status")
        response.raise_for_status()
        return response.json()
    
    def get_embeddings_config(self) -> Dict[str, Any]:
        response = self.get("/config/embeddings")
        response.raise_for_status()
        return response.json()
    
    def get_ingestion_config(self) -> Dict[str, Any]:
        response = self.get("/config/ingestion")
        response.raise_for_status()
        return response.json()
    
    # Wait for ingestion
    def wait_for_ingestion(self, collection_id: int, expected_files: int, 
                           max_wait: int = 60) -> bool:
        """Wait for files to complete ingestion."""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            files = self.list_files(collection_id)
            completed = sum(1 for f in files if f.get('status') == 'completed')
            if completed >= expected_files:
                return True
            time.sleep(2)
        return False


@pytest.fixture(scope="session")
def client() -> LambKBClient:
    """Create a client for the KB server."""
    return LambKBClient(BASE_URL, API_KEY)


@pytest.fixture(scope="session")
def test_files_dir(tmp_path_factory) -> Path:
    """Create a temporary directory for test files."""
    return tmp_path_factory.mktemp("test_files")


@pytest.fixture
def test_collection(client: LambKBClient) -> Generator[Dict[str, Any], None, None]:
    """Create a test collection and clean it up after the test."""
    timestamp = int(time.time() * 1000)
    collection = client.create_collection(
        name=f"pytest-collection-{timestamp}",
        description="Pytest test collection"
    )
    
    yield collection
    
    # Cleanup
    try:
        client.delete_collection(collection["id"])
    except Exception:
        pass  # Collection may already be deleted


@pytest.fixture
def sample_text_file(test_files_dir: Path) -> Path:
    """Create a sample text file for testing."""
    file_path = test_files_dir / f"sample_{int(time.time())}.txt"
    content = """
    This is a test document for the lamb-kb-server API tests.
    
    Natural language processing (NLP) is a field of artificial intelligence.
    It focuses on the interaction between computers and humans through language.
    
    Machine learning is a subset of artificial intelligence that enables systems
    to learn and improve from experience without being explicitly programmed.
    
    Neural networks are computing systems inspired by biological neural networks
    that constitute animal brains.
    """
    file_path.write_text(content)
    return file_path


@pytest.fixture
def ingested_collection(client: LambKBClient, test_collection: Dict[str, Any], 
                        sample_text_file: Path) -> Dict[str, Any]:
    """Create a collection with ingested content."""
    collection_id = test_collection["id"]
    
    # Ingest the file
    client.ingest_file(collection_id, str(sample_text_file))
    
    # Wait for ingestion to complete
    client.wait_for_ingestion(collection_id, 1, max_wait=30)
    
    return test_collection
