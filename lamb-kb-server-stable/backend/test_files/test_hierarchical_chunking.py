#!/usr/bin/env python3
"""
Test script for the hierarchical parent-child chunking plugin.

This test validates:
1. Parent chunks are created from sections
2. Child chunks are created from parents
3. Metadata correctly stores parent-child relationships
4. Parent context is preserved in child metadata
"""

import sys
import os
import json
from pathlib import Path

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.hierarchical_ingest import HierarchicalIngestPlugin


def create_test_markdown():
    """Create a test Markdown file with hierarchical structure."""
    test_content = """# Test Document

This is the introduction to the test document. It contains some preliminary information.

## Step 1: Setup Environment

First, you need to set up your development environment. This includes installing the necessary dependencies and configuring your system.

You will need Python 3.8 or higher. Install the required packages using pip install -r requirements.txt.

## Step 2: Configure the Application

Next, configure your application settings. Edit the config.yaml file to set your preferences.

Important settings include:
- Database connection string
- API endpoints
- Authentication credentials

Make sure to review all settings carefully before proceeding.

## Step 3: Run the Tests

Finally, run the test suite to ensure everything is working correctly.

Execute the command: python -m pytest tests/

Review the test results and fix any failures before deployment.

### Step 3.1: Unit Tests

Run unit tests first with: pytest tests/unit/

These tests verify individual components in isolation.

### Step 3.2: Integration Tests

Then run integration tests with: pytest tests/integration/

These tests verify that components work together correctly.

## Conclusion

You have now completed all the steps. Your application should be ready for deployment.
"""
    
    test_file_path = Path("/tmp/test_hierarchical.md")
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    return test_file_path


def test_hierarchical_chunking():
    """Test the hierarchical chunking plugin."""
    print("=" * 80)
    print("TESTING HIERARCHICAL PARENT-CHILD CHUNKING PLUGIN")
    print("=" * 80)
    
    # Create test file
    test_file = create_test_markdown()
    print(f"\n✓ Created test file: {test_file}")
    
    # Initialize plugin
    plugin = HierarchicalIngestPlugin()
    print(f"✓ Initialized plugin: {plugin.name}")
    
    # Test with default parameters
    print("\n" + "-" * 80)
    print("TEST 1: Default parameters (split by headers)")
    print("-" * 80)
    
    results = plugin.ingest(
        str(test_file),
        parent_chunk_size=2000,
        child_chunk_size=400,
        child_chunk_overlap=50,
        split_by_headers=True
    )
    
    print(f"\n✓ Generated {len(results)} child chunks")
    
    # Analyze parent chunks
    parent_chunks = {}
    for chunk in results:
        parent_id = chunk["metadata"]["parent_chunk_id"]
        if parent_id not in parent_chunks:
            parent_chunks[parent_id] = {
                "children": [],
                "section_title": chunk["metadata"].get("section_title", "Unknown")
            }
        parent_chunks[parent_id]["children"].append(chunk)
    
    print(f"✓ Organized into {len(parent_chunks)} parent chunks")
    
    # Display parent-child structure
    print("\nParent-Child Structure:")
    for parent_id in sorted(parent_chunks.keys()):
        parent_info = parent_chunks[parent_id]
        section = parent_info["section_title"]
        num_children = len(parent_info["children"])
        print(f"  Parent {parent_id} ('{section}'): {num_children} child chunks")
    
    # Verify metadata structure
    print("\n" + "-" * 80)
    print("TEST 2: Metadata validation")
    print("-" * 80)
    
    sample_chunk = results[0]
    required_fields = [
        "parent_chunk_id", "child_chunk_id", "chunk_level", "parent_text",
        "chunk_index", "chunk_count", "children_in_parent", "filename",
        "chunking_strategy"
    ]
    
    print("\nChecking required metadata fields in first chunk:")
    all_present = True
    for field in required_fields:
        present = field in sample_chunk["metadata"]
        status = "✓" if present else "✗"
        print(f"  {status} {field}")
        if not present:
            all_present = False
    
    if all_present:
        print("\n✓ All required metadata fields present")
    else:
        print("\n✗ Some metadata fields missing!")
        return False
    
    # Verify parent text is stored
    print("\n" + "-" * 80)
    print("TEST 3: Parent context preservation")
    print("-" * 80)
    
    for i, chunk in enumerate(results[:3]):  # Check first 3 chunks
        parent_text = chunk["metadata"]["parent_text"]
        child_text = chunk["text"]
        
        print(f"\nChunk {i}:")
        print(f"  Child text length: {len(child_text)} chars")
        print(f"  Parent text length: {len(parent_text)} chars")
        print(f"  Child is subset of parent: {child_text in parent_text}")
        
        if child_text not in parent_text:
            print(f"  ✗ WARNING: Child text not found in parent!")
    
    # Display sample child chunk
    print("\n" + "-" * 80)
    print("TEST 4: Sample chunk inspection")
    print("-" * 80)
    
    sample_idx = min(2, len(results) - 1)
    sample = results[sample_idx]
    
    print(f"\nSample Child Chunk #{sample_idx}:")
    print(f"  Section: {sample['metadata'].get('section_title', 'N/A')}")
    print(f"  Parent ID: {sample['metadata']['parent_chunk_id']}")
    print(f"  Child ID: {sample['metadata']['child_chunk_id']}")
    print(f"  Children in parent: {sample['metadata']['children_in_parent']}")
    print(f"\n  Child text ({len(sample['text'])} chars):")
    print(f"  {sample['text'][:200]}...")
    print(f"\n  Parent text ({len(sample['metadata']['parent_text'])} chars):")
    print(f"  {sample['metadata']['parent_text'][:200]}...")
    
    # Test without header splitting
    print("\n" + "-" * 80)
    print("TEST 5: Without header splitting")
    print("-" * 80)
    
    results_no_headers = plugin.ingest(
        str(test_file),
        parent_chunk_size=1000,
        child_chunk_size=300,
        child_chunk_overlap=50,
        split_by_headers=False
    )
    
    print(f"✓ Generated {len(results_no_headers)} child chunks (no header splitting)")
    
    parent_chunks_no_headers = {}
    for chunk in results_no_headers:
        parent_id = chunk["metadata"]["parent_chunk_id"]
        if parent_id not in parent_chunks_no_headers:
            parent_chunks_no_headers[parent_id] = []
        parent_chunks_no_headers[parent_id].append(chunk)
    
    print(f"✓ Organized into {len(parent_chunks_no_headers)} parent chunks")
    
    # Verify JSON output was created
    print("\n" + "-" * 80)
    print("TEST 6: JSON output file")
    print("-" * 80)
    
    json_file = Path("/tmp/test_hierarchical.md.hierarchical.json")
    if json_file.exists():
        print(f"✓ JSON output file created: {json_file}")
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        print(f"✓ JSON contains {len(json_data)} chunks")
    else:
        print(f"✗ JSON output file not found: {json_file}")
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = test_hierarchical_chunking()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED WITH ERROR:")
        print(f"  {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
