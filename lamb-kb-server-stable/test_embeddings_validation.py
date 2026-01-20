#!/usr/bin/env python3
"""
Test script for embeddings validation enhancement.

This script demonstrates the new validation system by testing various
configuration scenarios (both valid and invalid).

Usage:
    python test_embeddings_validation.py
"""

import requests
import json
import os
from typing import Dict, Any

# Configuration
BASE_URL = os.getenv("LAMB_KB_SERVER_URL", "http://localhost:9090")
API_KEY = os.getenv("LAMB_API_KEY", "0p3n-w3bu!")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_collection_creation(name: str, config: Dict[str, Any], description: str):
    """
    Test collection creation with given embeddings config.
    
    Args:
        name: Collection name
        config: Embeddings model configuration
        description: Test description
    """
    print(f"Test: {description}")
    print(f"Config: {json.dumps(config, indent=2)}")
    
    payload = {
        "name": name,
        "description": f"Test collection: {description}",
        "owner": "test-user",
        "visibility": "private",
        "embeddings_model": config
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/collections/",
            headers=HEADERS,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 201:
            result = response.json()
            print(f"✅ SUCCESS: Collection created (ID: {result.get('id')})")
            print(f"   Embeddings: {result.get('embeddings_model', {}).get('model')} "
                  f"({result.get('embeddings_model', {}).get('vendor')})")
            
            # Clean up - delete the test collection
            collection_id = result.get('id')
            if collection_id:
                delete_response = requests.delete(
                    f"{BASE_URL}/collections/{collection_id}",
                    headers=HEADERS
                )
                if delete_response.status_code == 200:
                    print(f"   Cleaned up test collection (ID: {collection_id})")
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            try:
                error = response.json()
                print(f"   Error: {error.get('detail', response.text)}")
            except:
                print(f"   Error: {response.text}")
    
    except requests.exceptions.Timeout:
        print(f"❌ TIMEOUT: Request exceeded 60 seconds")
    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
    
    print("-" * 80)


def main():
    """Run all validation tests."""
    
    print_section("Embeddings Validation Test Suite")
    
    # Test 1: Using environment defaults
    print_section("Test 1: Environment Defaults")
    test_collection_creation(
        name="test-env-defaults",
        config={
            "vendor": "default",
            "model": "default",
            "api_endpoint": "default",
            "apikey": "default"
        },
        description="Using environment defaults for all fields"
    )
    
    # Test 2: Valid Ollama configuration
    print_section("Test 2: Valid Ollama Configuration")
    test_collection_creation(
        name="test-ollama-valid",
        config={
            "vendor": "ollama",
            "model": "nomic-embed-text",
            "api_endpoint": "http://localhost:11434/api/embeddings",
            "apikey": ""
        },
        description="Valid Ollama configuration (requires Ollama running)"
    )
    
    # Test 3: Invalid Ollama model
    print_section("Test 3: Invalid Ollama Model")
    test_collection_creation(
        name="test-ollama-invalid-model",
        config={
            "vendor": "ollama",
            "model": "this-model-does-not-exist",
            "api_endpoint": "http://localhost:11434/api/embeddings",
            "apikey": ""
        },
        description="Invalid Ollama model name (should fail)"
    )
    
    # Test 4: Invalid Ollama endpoint
    print_section("Test 4: Unreachable Ollama Endpoint")
    test_collection_creation(
        name="test-ollama-bad-endpoint",
        config={
            "vendor": "ollama",
            "model": "nomic-embed-text",
            "api_endpoint": "http://localhost:99999/api/embeddings",
            "apikey": ""
        },
        description="Unreachable Ollama endpoint (should fail with network error)"
    )
    
    # Test 5: Invalid OpenAI API key
    print_section("Test 5: Invalid OpenAI API Key")
    test_collection_creation(
        name="test-openai-invalid-key",
        config={
            "vendor": "openai",
            "model": "text-embedding-3-small",
            "api_endpoint": "https://api.openai.com/v1/embeddings",
            "apikey": "sk-invalid-key-for-testing"
        },
        description="Invalid OpenAI API key (should fail with auth error)"
    )
    
    # Test 6: Valid OpenAI (if key provided)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print_section("Test 6: Valid OpenAI Configuration")
        test_collection_creation(
            name="test-openai-valid",
            config={
                "vendor": "openai",
                "model": "text-embedding-3-small",
                "api_endpoint": "https://api.openai.com/v1/embeddings",
                "apikey": openai_key
            },
            description="Valid OpenAI configuration (requires valid API key)"
        )
    else:
        print_section("Test 6: Valid OpenAI Configuration")
        print("⏭️  SKIPPED: No OPENAI_API_KEY environment variable found")
        print("-" * 80)
    
    # Summary
    print_section("Test Suite Complete")
    print("Check the following to review validation behavior:")
    print(f"  1. Server logs for validation details")
    print(f"  2. Audit log: backend/data/audit_logs/embeddings_validation.log")
    print()
    print("To view audit log:")
    print("  tail -f backend/data/audit_logs/embeddings_validation.log | jq")
    print()


if __name__ == "__main__":
    main()

