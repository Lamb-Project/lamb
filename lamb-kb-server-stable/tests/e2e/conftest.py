"""
Live test configuration and fixtures.

This module provides fixtures for testing against a real running server:
- httpx client for HTTP requests
- Mock embeddings to avoid LLM calls
- Test database helpers
"""

import sys
import pytest
import httpx
from pathlib import Path
from typing import Generator, Dict, Any, List
import time

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))


# =============================================================================
# MOCK EMBEDDINGS
# =============================================================================

class MockEmbeddingFunction:
    """Mock embedding function that returns deterministic vectors without LLM calls."""
    
    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions
        self._call_count = 0
    
    def __call__(self, texts: List[str]) -> List[List[float]]:
        """Generate fake embeddings for texts."""
        embeddings = []
        for i, text in enumerate(texts):
            # Create deterministic but unique embedding based on text hash
            base_value = (hash(text) % 1000) / 10000
            embedding = [(base_value + (j * 0.001)) for j in range(self.dimensions)]
            embeddings.append(embedding)
            self._call_count += 1
        return embeddings
    
    def embed(self, text: str) -> List[float]:
        """Single text embedding."""
        return self.__call__([text])[0]


@pytest.fixture(scope="session")
def mock_embedding_function():
    """Provide a mock embedding function for all live tests."""
    return MockEmbeddingFunction(dimensions=384)


# =============================================================================
# HTTP CLIENT FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def live_client(live_server_url, api_key) -> Generator[httpx.Client, None, None]:
    """Create an httpx client for live server testing."""
    with httpx.Client(
        base_url=live_server_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0
    ) as client:
        # Verify server is running
        try:
            response = client.get("/health")
            if response.status_code != 200:
                pytest.skip(f"Live server not available at {live_server_url}")
        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to live server at {live_server_url}")
        
        yield client


@pytest.fixture
def auth_headers(api_key) -> Dict[str, str]:
    """Return valid authentication headers."""
    return {"Authorization": f"Bearer {api_key}"}


@pytest.fixture
def invalid_auth_headers() -> Dict[str, str]:
    """Return invalid authentication headers."""
    return {"Authorization": "Bearer invalid-token-12345"}


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================

@pytest.fixture
def unique_collection_name() -> str:
    """Generate a unique collection name for each test."""
    return f"live-test-collection-{int(time.time() * 1000)}"


@pytest.fixture
def sample_collection_data(unique_collection_name) -> Dict[str, Any]:
    """Return sample collection creation data with unique name."""
    return {
        "name": unique_collection_name,
        "description": "Live test collection",
        "owner": "live-test-user",
        "visibility": "private",
        "embeddings_model": {
            "model": "nomic-embed-text:latest",
            "vendor": "ollama",
            "apikey": "",
            "api_endpoint": "http://127.0.0.1:11435"
        }
    }


@pytest.fixture
def sample_documents() -> Dict[str, Any]:
    """Return sample documents for ingestion."""
    return {
        "documents": [
            {
                "text": "Machine learning is a subset of artificial intelligence.",
                "metadata": {"source": "test.txt", "chunk_index": 0}
            },
            {
                "text": "Python is widely used for data science applications.",
                "metadata": {"source": "test.txt", "chunk_index": 1}
            }
        ]
    }


@pytest.fixture
def sample_query() -> Dict[str, Any]:
    """Return sample query data."""
    return {
        "query_text": "What is machine learning?",
        "top_k": 5,
        "threshold": 0.0,
        "plugin_params": {}
    }


@pytest.fixture
def test_text_file(tmp_path) -> Path:
    """Create a temporary text file for ingestion tests."""
    file_path = tmp_path / "test_document.txt"
    file_path.write_text("""
    Introduction to Machine Learning
    
    Machine learning is a subset of artificial intelligence that enables 
    computers to learn from data without being explicitly programmed.
    
    Types of Machine Learning:
    1. Supervised Learning - Uses labeled data
    2. Unsupervised Learning - Finds patterns in unlabeled data
    3. Reinforcement Learning - Learns through trial and error
    """)
    return file_path


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================

@pytest.fixture
def cleanup_collection(live_client):
    """Fixture to track and clean up created collections after test."""
    created_ids = []
    
    def register(collection_id: int):
        created_ids.append(collection_id)
    
    yield register
    
    # Cleanup after test
    for collection_id in created_ids:
        try:
            live_client.delete(f"/collections/{collection_id}")
        except Exception:
            pass  # Ignore cleanup errors
