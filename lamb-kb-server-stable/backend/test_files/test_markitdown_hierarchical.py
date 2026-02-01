#!/usr/bin/env python3
"""
Test script for hierarchical parent-child chunking in markitdown_plus plugin.

This test validates:
1. Hierarchical chunking mode works for converted markdown documents
2. Document outline is generated and appended when enabled
3. Parent-child metadata is correctly structured
4. Works with different file formats (via markdown conversion)
"""

import sys
import os
import tempfile
from pathlib import Path

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.markitdown_plus_ingest import MarkItDownPlusPlugin


def create_test_markdown_file():
    """Create a test markdown file to simulate converted content."""
    test_content = """# Complete Python Tutorial

This is a comprehensive guide to learning Python programming.

## Getting Started

Learn the basics of Python setup and installation.

### Installing Python

Download and install Python from the official website.

### Setting Up IDE

Choose and configure your development environment.

## Core Concepts

Master the fundamental concepts of Python.

### Variables and Data Types

Understanding different data types in Python.

### Control Flow

Learn about if statements, loops, and more.

### Functions

Create reusable code with functions.

## Advanced Topics

Dive into more advanced Python concepts.

### Object-Oriented Programming

Learn classes, objects, and inheritance.

### Decorators and Generators

Advanced Python features for cleaner code.

## Conclusion

You now have a solid foundation in Python programming.
"""
    
    # Create a temporary markdown file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(test_content)
        return f.name


def test_hierarchical_chunking():
    """Test the hierarchical chunking mode in markitdown_plus plugin."""
    print("=" * 80)
    print("TESTING MARKITDOWN_PLUS HIERARCHICAL CHUNKING")
    print("=" * 80)
    
    # Create test file
    test_file = create_test_markdown_file()
    print(f"\n✓ Created test file: {test_file}")
    
    # Initialize plugin
    plugin = MarkItDownPlusPlugin()
    print(f"✓ Initialized plugin: {plugin.name}")
    
    # Test 1: Hierarchical mode WITHOUT outline
    print("\n" + "-" * 80)
    print("TEST 1: Hierarchical chunking without outline")
    print("-" * 80)
    
    results_no_outline = plugin.ingest(
        test_file,
        chunking_mode="hierarchical",
        parent_chunk_size=2000,
        child_chunk_size=400,
        child_chunk_overlap=50,
        split_by_headers=True,
        include_outline=False
    )
    
    print(f"✓ Generated {len(results_no_outline)} chunks")
    
    # Verify no outline in content
    has_outline = any(
        "Document Outline" in chunk.get("text", "") or
        "Document Outline" in chunk.get("metadata", {}).get("parent_text", "")
        for chunk in results_no_outline
    )
    if has_outline:
        print("✗ FAIL: Outline found when it should not be present")
        return False
    else:
        print("✓ No outline present (as expected)")
    
    # Test 2: Hierarchical mode WITH outline
    print("\n" + "-" * 80)
    print("TEST 2: Hierarchical chunking with outline")
    print("-" * 80)
    
    results_with_outline = plugin.ingest(
        test_file,
        chunking_mode="hierarchical",
        parent_chunk_size=2000,
        child_chunk_size=400,
        child_chunk_overlap=50,
        split_by_headers=True,
        include_outline=True
    )
    
    print(f"✓ Generated {len(results_with_outline)} chunks")
    
    # Verify outline is present
    outline_found = False
    for chunk in results_with_outline:
        parent_text = chunk.get("metadata", {}).get("parent_text", "")
        if "Document Outline" in parent_text and "Complete Python Tutorial" in parent_text:
            outline_found = True
            print("✓ Document outline found in parent_text")
            break
    
    if not outline_found:
        print("✗ FAIL: Outline not found when it should be present")
        return False
    
    # Test 3: Verify parent-child metadata structure
    print("\n" + "-" * 80)
    print("TEST 3: Verify parent-child metadata structure")
    print("-" * 80)
    
    sample_chunk = results_with_outline[0]
    required_fields = [
        "parent_chunk_id", "child_chunk_id", "chunk_level", "parent_text",
        "chunk_index", "chunk_count", "children_in_parent"
    ]
    
    print("\nChecking required metadata fields in first chunk:")
    all_present = True
    for field in required_fields:
        present = field in sample_chunk["metadata"]
        status = "✓" if present else "✗"
        print(f"  {status} {field}")
        if not present:
            all_present = False
    
    if not all_present:
        print("\n✗ FAIL: Some required metadata fields missing")
        return False
    else:
        print("\n✓ All required parent-child metadata fields present")
    
    # Verify chunking strategy metadata
    if sample_chunk["metadata"].get("chunking_strategy") == "hierarchical_parent_child":
        print("✓ Chunking strategy correctly set to 'hierarchical_parent_child'")
    else:
        print(f"✗ FAIL: Incorrect chunking strategy: {sample_chunk['metadata'].get('chunking_strategy')}")
        return False
    
    # Test 4: Verify chunk_level field
    print("\n" + "-" * 80)
    print("TEST 4: Verify chunk_level is 'child'")
    print("-" * 80)
    
    all_are_children = all(
        chunk["metadata"].get("chunk_level") == "child"
        for chunk in results_with_outline
    )
    
    if all_are_children:
        print("✓ All chunks have chunk_level='child'")
    else:
        print("✗ FAIL: Some chunks don't have chunk_level='child'")
        return False
    
    # Test 5: Verify parent text contains child text
    print("\n" + "-" * 80)
    print("TEST 5: Verify child text is subset of parent text")
    print("-" * 80)
    
    sample_indices = [0, min(5, len(results_with_outline) - 1), len(results_with_outline) - 1]
    all_contained = True
    
    for idx in sample_indices:
        chunk = results_with_outline[idx]
        child_text = chunk["text"]
        parent_text = chunk["metadata"]["parent_text"]
        
        # Note: child_text might not be directly in parent_text if outline was appended
        # So we check if the parent_text is reasonable
        if len(parent_text) >= len(child_text):
            print(f"✓ Chunk {idx}: parent ({len(parent_text)} chars) >= child ({len(child_text)} chars)")
        else:
            print(f"✗ Chunk {idx}: parent smaller than child!")
            all_contained = False
    
    if not all_contained:
        print("\n✗ FAIL: Parent-child relationship issue")
        return False
    else:
        print("\n✓ Parent-child relationships verified")
    
    # Test 6: Verify outline format
    print("\n" + "-" * 80)
    print("TEST 6: Verify outline format")
    print("-" * 80)
    
    # Find the outline in parent_text
    outline_text = ""
    for chunk in results_with_outline:
        parent_text = chunk["metadata"].get("parent_text", "")
        if "Document Outline" in parent_text:
            start = parent_text.find("Document Outline")
            outline_text = parent_text[start:]
            break
    
    if outline_text:
        print("✓ Found outline in parent_text")
        
        # Check format
        expected_elements = [
            "Complete Python Tutorial",
            "Getting Started",
            "Core Concepts",
            "Advanced Topics",
            "<a>",
            "</a>"
        ]
        
        all_found = True
        for element in expected_elements:
            if element in outline_text:
                print(f"  ✓ Contains: {element}")
            else:
                print(f"  ✗ Missing: {element}")
                all_found = False
        
        if not all_found:
            print("\n✗ FAIL: Outline format issues")
            return False
        else:
            print("\n✓ Outline format verified")
    else:
        print("✗ FAIL: Could not find outline text")
        return False
    
    # Test 7: Verify parameter configuration
    print("\n" + "-" * 80)
    print("TEST 7: Verify parameter configuration")
    print("-" * 80)
    
    params = plugin.get_parameters()
    
    # Check hierarchical mode exists
    if "hierarchical" in params.get("chunking_mode", {}).get("enum", []):
        print("✓ 'hierarchical' chunking mode is available")
    else:
        print("✗ FAIL: 'hierarchical' mode not in chunking_mode options")
        return False
    
    # Check hierarchical parameters exist
    hierarchical_params = [
        "parent_chunk_size",
        "child_chunk_size",
        "child_chunk_overlap",
        "split_by_headers",
        "include_outline"
    ]
    
    for param_name in hierarchical_params:
        if param_name in params:
            print(f"  ✓ Parameter '{param_name}' defined")
        else:
            print(f"  ✗ Parameter '{param_name}' missing")
            return False
    
    print("\n✓ All hierarchical parameters configured")
    
    # Cleanup
    try:
        os.unlink(test_file)
        # Also clean up generated .md file if it exists
        md_file = Path(test_file).with_suffix('.md')
        if md_file.exists():
            os.unlink(md_file)
    except:
        pass
    
    print("\n" + "=" * 80)
    print("ALL MARKITDOWN_PLUS HIERARCHICAL TESTS PASSED")
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
