#!/usr/bin/env python3
"""
Test script for MockAI JSON Ingest Plugin.

This script tests the mockai-json-ingest plugin with sample data files.
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.append('/opt/lamb-project/lamb/lamb-kb-server-stable/backend')

from plugins.mockai_json_ingest import MockAIJSONIngestPlugin

def test_plugin_basic():
    """Test basic plugin functionality."""
    print("Testing MockAI JSON Ingest Plugin...")

    # Create plugin instance
    plugin = MockAIJSONIngestPlugin()

    # Test parameters
    params = plugin.get_parameters()
    print(f"Plugin parameters: {json.dumps(params, indent=2)}")

    # Test with sample.json
    sample_file = "/opt/lamb-project/lamb/lamb-kb-server-stable/sample.json"

    if os.path.exists(sample_file):
        print(f"\nTesting with {sample_file}...")

        try:
            chunks = plugin.ingest(sample_file, chunk_size=1000, chunk_overlap=100)

            print(f"Generated {len(chunks)} chunks")

            # Show first chunk metadata
            if chunks:
                print("\nFirst chunk preview:")
                print(f"Text: {chunks[0]['text'][:200]}...")
                print(f"Metadata keys: {list(chunks[0]['metadata'].keys())}")
                print(f"Sample metadata: {json.dumps({k: v for k, v in chunks[0]['metadata'].items() if k in ['number', 'kind', 'filename', 'source_file']}, indent=2)}")

        except Exception as e:
            print(f"Error testing sample.json: {e}")

    # Test with sample-2.json
    sample_file_2 = "/opt/lamb-project/lamb/lamb-kb-server-stable/sample-2.json"

    if os.path.exists(sample_file_2):
        print(f"\nTesting with {sample_file_2}...")

        try:
            chunks = plugin.ingest(sample_file_2, chunk_size=1500, chunk_overlap=200)

            print(f"Generated {len(chunks)} chunks")

            # Show first chunk metadata
            if chunks:
                print("\nFirst chunk preview:")
                print(f"Text: {chunks[0]['text'][:200]}...")
                print(f"Metadata keys: {list(chunks[0]['metadata'].keys())}")
                print(f"Sample metadata: {json.dumps({k: v for k, v in chunks[0]['metadata'].items() if k in ['number', 'title', 'kind', 'filename', 'page', 'source_file']}, indent=2)}")

        except Exception as e:
            print(f"Error testing sample-2.json: {e}")

    # Test with ZIP file
    zip_file = "/opt/lamb-project/lamb/lamb-kb-server-stable/test-mockai-data.zip"

    if os.path.exists(zip_file):
        print(f"\nTesting with ZIP file {zip_file}...")

        try:
            chunks = plugin.ingest(zip_file, chunk_size=1500, chunk_overlap=200, process_zip_files=True)

            print(f"Generated {len(chunks)} chunks from ZIP file")

            # Show first chunk metadata
            if chunks:
                print("\nFirst chunk preview:")
                print(f"Text: {chunks[0]['text'][:200]}...")
                print(f"Metadata keys: {list(chunks[0]['metadata'].keys())}")
                print(f"Sample metadata: {json.dumps({k: v for k, v in chunks[0]['metadata'].items() if k in ['number', 'kind', 'filename', 'source_file', 'page']}, indent=2)}")

            # Count chunks by source file
            source_counts = {}
            for chunk in chunks:
                source = chunk['metadata'].get('source_file', 'unknown')
                source_counts[source] = source_counts.get(source, 0) + 1

            print(f"\nChunks by source file: {json.dumps(source_counts, indent=2)}")

        except Exception as e:
            print(f"Error testing ZIP file: {e}")

    print("\nPlugin test completed!")

if __name__ == "__main__":
    test_plugin_basic()
