#!/usr/bin/env python3
"""
Debug script to test OpenAI API key handling.
"""

import os
import json
import openai
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env
load_dotenv()

def test_openai_api_key():
    """Test the OpenAI API key directly."""
    # Get the API key from environment
    api_key = os.getenv("EMBEDDINGS_APIKEY", "")
    
    print(f"API key length: {len(api_key)}")
    print(f"API key first/last chars: {api_key[:4]}...{api_key[-4:] if len(api_key) > 4 else ''}")
    
    # Create OpenAI client with direct key
    client = OpenAI(api_key=api_key)
    
    # Test embeddings
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=["Test embedding validation"]
        )
        
        embedding = response.data[0].embedding
        print(f"SUCCESS: Generated embedding with {len(embedding)} dimensions")
        return True
    except Exception as e:
        print(f"ERROR: OpenAI API error: {str(e)}")
        return False

def test_openai_with_client_class():
    """Test using our custom OpenAIEmbeddingFunction class."""
    # Get the API key from environment
    api_key = os.getenv("EMBEDDINGS_APIKEY", "")
    
    # Create our custom embedding function (similar to the one in the code)
    class OpenAIEmbeddingFunction:
        def __init__(self, model_name, api_key):
            self.model_name = model_name
            # Create client with API key
            self.client = OpenAI(api_key=api_key)
            print(f"Created OpenAI client with api_key length: {len(api_key)}")
            
        def __call__(self, input):
            """Generate embeddings using OpenAI with the expected ChromaDB interface."""
            if isinstance(input, str):
                input = [input]
                
            all_embeddings = []
            
            try:
                response = self.client.embeddings.create(
                    model=self.model_name,
                    input=input
                )
                
                batch_embeddings = [embedding.embedding for embedding in response.data]
                all_embeddings.extend(batch_embeddings)
                print(f"Generated {len(all_embeddings)} embeddings with {len(all_embeddings[0]) if all_embeddings else 0} dimensions")
                return all_embeddings
            except Exception as e:
                print(f"OpenAI API error: {str(e)}")
                raise RuntimeError(f"OpenAI API error: {str(e)}")
    
    # Create the function and try to use it
    embedding_function = OpenAIEmbeddingFunction("text-embedding-3-small", api_key)
    
    try:
        result = embedding_function(["Test embedding validation"])
        print(f"SUCCESS: Generated embedding with {len(result[0])} dimensions")
        return True
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== Testing OpenAI API key ===")
    
    # Load API key from environment
    print("\nEnvironment variables:")
    api_key = os.getenv("EMBEDDINGS_APIKEY", "")
    model = os.getenv("EMBEDDINGS_MODEL", "")
    vendor = os.getenv("EMBEDDINGS_VENDOR", "")
    endpoint = os.getenv("EMBEDDINGS_ENDPOINT", "")
    
    print(f"EMBEDDINGS_MODEL: {model}")
    print(f"EMBEDDINGS_VENDOR: {vendor}")
    print(f"EMBEDDINGS_ENDPOINT: {endpoint}")
    print(f"EMBEDDINGS_APIKEY length: {len(api_key)}")
    print(f"EMBEDDINGS_APIKEY first/last chars: {api_key[:4]}...{api_key[-4:] if len(api_key) > 4 else ''}")
    
    # Also check for OPENAI_API_KEY
    openai_key = os.getenv("OPENAI_API_KEY", "")
    print(f"OPENAI_API_KEY set: {'Yes' if openai_key else 'No'}")
    print(f"OPENAI_API_KEY length: {len(openai_key)}")
    
    print("\n=== Testing direct OpenAI API key ===")
    success1 = test_openai_api_key()
    
    print("\n=== Testing with OpenAIEmbeddingFunction ===")
    success2 = test_openai_with_client_class()
    
    if success1 and success2:
        print("\nBoth tests PASSED! The API key works properly.")
    elif success1:
        print("\nDirect test PASSED but embedding function test FAILED!")
    elif success2:
        print("\nDirect test FAILED but embedding function test PASSED!")
    else:
        print("\nBoth tests FAILED! Check your API key and environment variables.") 