#!/usr/bin/env python3
"""
Debug script to test embeddings throughout the collection lifecycle.
This script creates a collection, ingests content, and queries it, while tracking embedding functions.
"""

import os
import sys
import time
import json
import tempfile
import requests
from typing import Dict, Any

# Set up API access
BASE_URL = "http://localhost:9090"
API_KEY = "0p3n-w3bu!"  # Default API key
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def api_request(method: str, endpoint: str, data=None, files=None, params=None):
    """Make a request to the API with error handling."""
    url = f"{BASE_URL}{endpoint}"
    headers = HEADERS.copy()
    
    if files:
        # Don't use Content-Type: application/json for file uploads
        headers.pop("Content-Type", None)
    
    print(f"\n>>> {method.upper()} {endpoint}")
    if data and not files:
        print(f"Request data: {json.dumps(data, indent=2)}")
    
    try:
        response = requests.request(
            method, 
            url, 
            headers=headers, 
            json=data if not files else None,
            data=data if files else None,
            files=files,
            params=params
        )
        
        print(f"Status code: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"Response: {json.dumps(response_json, indent=2)[:1000]}...")
            return response_json
        except:
            print(f"Response text: {response.text[:500]}...")
            return response.text
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def create_collection(name: str, description: str = "Test collection") -> Dict[str, Any]:
    """Create a new collection."""
    print("\n=== CREATING COLLECTION ===")
    
    # Get the embeddings model and vendor from environment variables
    embeddings_vendor = os.getenv("EMBEDDINGS_VENDOR", "default")
    embeddings_model = os.getenv("EMBEDDINGS_MODEL", "default")
    print(f"Using embeddings_vendor={embeddings_vendor}, embeddings_model={embeddings_model}")
    
    data = {
        "name": name,
        "description": description,
        "owner": "test_user",
        "visibility": "private",
        "embeddings_model": {
            "model": embeddings_model,
            "vendor": embeddings_vendor,
            "apikey": "default"
        }
    }
    
    return api_request("post", "/collections", data=data)

def create_test_file(content: str) -> str:
    """Create a temporary test file with the given content."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    temp_file.write(content.encode("utf-8"))
    temp_file.close()
    return temp_file.name

def ingest_file(collection_id: int, file_path: str) -> Dict[str, Any]:
    """Ingest a file into the collection."""
    print(f"\n=== INGESTING FILE: {file_path} ===")
    
    with open(file_path, "rb") as f:
        files = {
            "file": (os.path.basename(file_path), f, "text/plain"),
            "plugin_name": (None, "simple_ingest"),
            "plugin_params": (None, json.dumps({
                "chunk_size": 500,
                "chunk_unit": "char",
                "chunk_overlap": 50
            }))
        }
        
        return api_request(
            "post", 
            f"/collections/{collection_id}/ingest-file", 
            files=files
        )

def query_collection(collection_id: int, query_text: str) -> Dict[str, Any]:
    """Query the collection."""
    print(f"\n=== QUERYING COLLECTION: '{query_text}' ===")
    
    data = {
        "query_text": query_text,
        "top_k": 5,
        "threshold": 0.0,
        "plugin_params": {}
    }
    
    return api_request(
        "post", 
        f"/collections/{collection_id}/query?plugin_name=simple_query", 
        data=data
    )

def check_database_health():
    """Check the database health and status."""
    print("\n=== CHECKING DATABASE STATUS ===")
    return api_request("get", "/database/status")

def get_collection_details(collection_id: int) -> Dict[str, Any]:
    """Get the collection details."""
    print(f"\n=== GETTING COLLECTION DETAILS: {collection_id} ===")
    return api_request("get", f"/collections/{collection_id}")

def main():
    """Main test function."""
    print("=== EMBEDDING DEBUG TEST ===")
    
    # Check database health
    check_database_health()
    
    # Create a unique collection name
    collection_name = f"test_collection_{int(time.time())}"
    
    # Step 1: Create a collection
    collection = create_collection(collection_name)
    collection_id = collection.get("id")
    
    if not collection_id:
        print("Error: Failed to create collection")
        sys.exit(1)
    
    print(f"Created collection with ID: {collection_id}")
    
    # Get collection details to see embedding config
    collection_details = get_collection_details(collection_id)
    
    # Step 2: Create and ingest a test file
    test_content = """
    This is a test document for embedding debug.
    
    The LAMB Knowledge Base server is designed to provide robust vector database functionality.
    It uses ChromaDB as its vector database and supports various embedding models.
    
    This test is checking if the embedding functions are consistent across the collection lifecycle.
    
    Embeddings can be generated using different models and vendors such as:
    - OpenAI (text-embedding-ada-002, text-embedding-3-small, etc.)
    - HuggingFace sentence-transformers
    - Ollama local models
    
    The dimensionality of these embeddings varies:
    - OpenAI text-embedding-ada-002: 1536 dimensions
    - OpenAI text-embedding-3-small: 1536 dimensions
    - Nomic AI nomic-embed-text: 768 dimensions
    - Many sentence-transformers: 384 or 768 dimensions
    
    If the dimensionality doesn't match between ingestion and query time, you'll get errors.
    """
    
    test_file_path = create_test_file(test_content)
    print(f"Created test file: {test_file_path}")
    
    # Ingest the file
    ingestion_result = ingest_file(collection_id, test_file_path)
    
    # Get collection details again after ingestion
    collection_details = get_collection_details(collection_id)
    
    # Wait a moment to ensure indexing is complete
    print("Waiting for indexing to complete...")
    time.sleep(2)
    
    # Step 3: Query the collection
    query_result = query_collection(collection_id, "embedding dimensionality")
    
    # Cleanup
    os.unlink(test_file_path)
    print(f"\nRemoved test file: {test_file_path}")
    
    # Summary
    print("\n=== TEST COMPLETE ===")
    print(f"Collection ID: {collection_id}")
    print(f"Collection Name: {collection_name}")
    print(f"Documents ingested: {ingestion_result.get('documents_added', 0) if isinstance(ingestion_result, dict) else 'Unknown'}")
    print(f"Query results count: {query_result.get('count', 0) if isinstance(query_result, dict) else 'Unknown'}")
    
    # Check query results
    if isinstance(query_result, dict) and query_result.get("count", 0) > 0:
        print("\nQuery successful! Results found.")
    else:
        print("\nQuery unsuccessful. No results found.")
        print("This may indicate embedding dimensionality mismatch between ingestion and query.")
        print("Check the server logs for more details about the embedding functions used.")

if __name__ == "__main__":
    main() 