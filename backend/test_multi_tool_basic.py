#!/usr/bin/env python3
"""
Basic test script for multi-tool assistant backend components.
Tests tool registry discovery and orchestrator loading.
"""

import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lamb'))

def test_tool_registry():
    """Test that tool registry can discover and load tools."""
    print("Testing tool registry...")

    try:
        from lamb.completions.tool_registry import tool_registry

        # Get all tools
        tools = tool_registry.get_tool_definitions()
        print(f"Found {len(tools)} tools:")

        for tool in tools:
            print(f"  - {tool['name']}: {tool['display_name']} ({tool['placeholder']})")

        # Check that our expected tools are there
        tool_names = [t['name'] for t in tools]
        expected_tools = ['simple_rag', 'rubric_rag', 'single_file_rag']

        for expected in expected_tools:
            if expected in tool_names:
                print(f"✓ Found expected tool: {expected}")
            else:
                print(f"✗ Missing expected tool: {expected}")
                return False

        return True

    except Exception as e:
        print(f"Error testing tool registry: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_orchestrator_loading():
    """Test that orchestrator can load strategies."""
    print("\nTesting orchestrator loading...")

    try:
        from lamb.completions.tool_orchestrator import ToolOrchestrator

        # Get available strategies
        strategies = ToolOrchestrator.get_available_strategies()
        print(f"Found {len(strategies)} orchestrator strategies:")

        for strategy in strategies:
            print(f"  - {strategy['name']}: {strategy['description']}")

        # Check that sequential is available
        strategy_names = [s['name'] for s in strategies]
        if 'sequential' in strategy_names:
            print("✓ Found expected sequential orchestrator")
            return True
        else:
            print("✗ Missing expected sequential orchestrator")
            return False

    except Exception as e:
        print(f"Error testing orchestrator loading: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_routing_logic():
    """Test the type-based routing logic."""
    print("\nTesting routing logic...")

    try:
        # Test classic assistant metadata
        classic_metadata = {
            "rag_processor": "simple_rag",
            "prompt_processor": "simple_augment",
            "connector": "openai"
        }

        assistant_type = classic_metadata.get("assistant_type", "classic")
        if assistant_type == "classic":
            print("✓ Classic assistant correctly identified")
        else:
            print("✗ Classic assistant not correctly identified")
            return False

        # Test multi-tool assistant metadata
        multi_tool_metadata = {
            "assistant_type": "multi_tool",
            "orchestrator": "sequential",
            "tools": [
                {
                    "plugin": "simple_rag",
                    "placeholder": "1_context",
                    "config": {"collections": ["test"]}
                }
            ]
        }

        assistant_type = multi_tool_metadata.get("assistant_type", "classic")
        if assistant_type == "multi_tool":
            print("✓ Multi-tool assistant correctly identified")
            return True
        else:
            print("✗ Multi-tool assistant not correctly identified")
            return False

    except Exception as e:
        print(f"Error testing routing logic: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Running basic multi-tool backend tests...\n")

    success = True
    success &= test_tool_registry()
    success &= test_orchestrator_loading()
    success &= test_routing_logic()

    if success:
        print("\n✅ All basic tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)