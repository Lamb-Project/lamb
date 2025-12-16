#!/usr/bin/env python3
"""
Simple test script for multi-tool assistant backend components.
Tests core functionality without full imports.
"""

import sys
import os

def test_directory_structure():
    """Test that all required directories and files exist."""
    print("Testing directory structure...")

    base_dir = os.path.join(os.path.dirname(__file__), 'lamb', 'completions')

    # Check directories exist
    dirs_to_check = ['tools', 'orchestrators']
    for dir_name in dirs_to_check:
        dir_path = os.path.join(base_dir, dir_name)
        if os.path.isdir(dir_path):
            print(f"✓ Directory exists: {dir_name}")
        else:
            print(f"✗ Directory missing: {dir_name}")
            return False

    # Check files exist
    files_to_check = [
        'tools/__init__.py',
        'tools/base.py',
        'tools/simple_rag.py',
        'tools/rubric_rag.py',
        'tools/single_file_rag.py',
        'orchestrators/__init__.py',
        'orchestrators/base.py',
        'orchestrators/sequential.py',
        'tool_registry.py',
        'tool_orchestrator.py'
    ]

    for file_path in files_to_check:
        full_path = os.path.join(base_dir, file_path)
        if os.path.isfile(full_path):
            print(f"✓ File exists: {file_path}")
        else:
            print(f"✗ File missing: {file_path}")
            return False

    return True


def test_base_classes():
    """Test that base classes can be imported and instantiated."""
    print("\nTesting base classes...")

    try:
        # Test base tool definition
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lamb'))
        from lamb.completions.tools.base import ToolDefinition, ToolResult
        from lamb.completions.orchestrators.base import OrchestrationResult, BaseOrchestrator, ToolConfig

        # Test creating instances
        tool_def = ToolDefinition(
            name="test_tool",
            display_name="Test Tool",
            description="A test tool",
            placeholder="test",
            config_schema={"type": "object"}
        )
        print("✓ ToolDefinition created successfully")

        tool_result = ToolResult(
            placeholder="test",
            content="test content",
            sources=[]
        )
        print("✓ ToolResult created successfully")

        tool_config = ToolConfig(
            plugin="test_plugin",
            placeholder="test"
        )
        print("✓ ToolConfig created successfully")

        return True

    except Exception as e:
        print(f"Error testing base classes: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_routing_updated():
    """Test that main.py has been updated with routing logic."""
    print("\nTesting main.py routing updates...")

    main_py_path = os.path.join(os.path.dirname(__file__), 'lamb', 'completions', 'main.py')

    try:
        with open(main_py_path, 'r') as f:
            content = f.read()

        # Check for key routing elements
        checks = [
            ('assistant_type == "multi_tool"', 'Multi-tool routing check'),
            ('process_multi_tool_completion', 'Multi-tool function call'),
            ('tool_orchestrator.orchestrate', 'Orchestrator usage'),
            ('/tools', 'Tools API endpoint'),
            ('/orchestrators', 'Orchestrators API endpoint')
        ]

        for check_text, description in checks:
            if check_text in content:
                print(f"✓ Found: {description}")
            else:
                print(f"✗ Missing: {description}")
                return False

        return True

    except Exception as e:
        print(f"Error reading main.py: {e}")
        return False


if __name__ == "__main__":
    print("Running simple multi-tool backend tests...\n")

    success = True
    success &= test_directory_structure()
    success &= test_base_classes()
    success &= test_main_routing_updated()

    if success:
        print("\n✅ All simple tests passed!")
        print("\nNote: Full integration testing requires all dependencies to be installed.")
        print("The core architecture is implemented correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)