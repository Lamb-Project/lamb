#!/usr/bin/env python3
"""
Test script for evaluating chunking strategies in the SimpleIngestPlugin.
"""

import sys
import os
import json
from enum import Enum

# Add the current directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from plugins.simple_ingest import SimpleIngestPlugin, ChunkUnit

def test_chunking_strategies(file_path, output_details=True):
    """Test different chunking strategies on a file.
    
    Args:
        file_path: Path to the file to test
        output_details: Whether to print detailed chunk information
    """
    print(f"Testing chunking strategies on file: {file_path}")
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"File size: {len(content)} characters")
    
    # Create plugin instance
    plugin = SimpleIngestPlugin()
    
    # Test different chunking strategies
    strategies = [
        {"name": "Character-based", "unit": ChunkUnit.CHAR, "size": 100, "overlap": 20},
        {"name": "Word-based", "unit": ChunkUnit.WORD, "size": 20, "overlap": 5},
        {"name": "Line-based", "unit": ChunkUnit.LINE, "size": 5, "overlap": 1}
    ]
    
    for strategy in strategies:
        print(f"\n\nTesting {strategy['name']} chunking:")
        print(f"  Unit: {strategy['unit']}, Size: {strategy['size']}, Overlap: {strategy['overlap']}")
        
        try:
            chunks = plugin._split_content(
                content=content,
                chunk_size=strategy['size'],
                chunk_unit=strategy['unit'],
                chunk_overlap=strategy['overlap']
            )
            
            print(f"Successfully created {len(chunks)} chunks")
            
            if output_details and chunks:
                print(f"\nSample of first chunk ({len(chunks[0])} chars):")
                print(f"{chunks[0][:100]}..." if len(chunks[0]) > 100 else chunks[0])
                
                if len(chunks) > 1:
                    print(f"\nSample of last chunk ({len(chunks[-1])} chars):")
                    print(f"{chunks[-1][:100]}..." if len(chunks[-1]) > 100 else chunks[-1])
        
        except Exception as e:
            print(f"ERROR: Failed to chunk with {strategy['name']} strategy: {str(e)}")
            import traceback
            print(traceback.format_exc())

if __name__ == "__main__":
    # Use command line argument if provided, otherwise use default test file
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "test_files/test1.txt"
        
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        print("Creating a sample test file...")
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("This is a test file for chunking strategies.\n" * 20)
        
    test_chunking_strategies(file_path)
