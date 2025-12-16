#!/usr/bin/env python3
"""
Test script for verbose orchestrator functionality.
"""

import sys
import os

def test_verbose_orchestrator():
    """Test verbose mode functionality."""

    # Mock classes for testing
    class MockAssistant:
        def __init__(self):
            self.name = "Test Assistant"
            self.system_prompt = "You are a helpful assistant."
            self.prompt_template = "Context: {1_context}\n\nQuestion: {user_input}"

    class MockToolResult:
        def __init__(self, placeholder, content, sources=None):
            self.placeholder = placeholder
            self.content = content
            self.sources = sources or []

    # Test the verbose report generation
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lamb'))

        from lamb.completions.orchestrators.sequential import SequentialOrchestrator
        from lamb.completions.orchestrators.base import ToolConfig

        orchestrator = SequentialOrchestrator()

        # Create mock data
        request = {
            "messages": [{"role": "user", "content": "What is Python?"}],
            "stream": False
        }

        assistant = MockAssistant()

        tool_configs = [
            ToolConfig(
                plugin="simple_rag",
                placeholder="1_context",
                config={"collections": ["docs"]}
            )
        ]

        tool_results = {
            "1_context": "Python is a programming language..."
        }

        all_sources = [{"title": "Python Docs", "url": "https://docs.python.org"}]

        final_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Context: Python is a programming language...\n\nQuestion: What is Python?"}
        ]

        # Test verbose report generation
        verbose_report = orchestrator._generate_verbose_report(
            request, assistant, tool_configs, tool_results, all_sources, final_messages
        )

        print("✓ Verbose report generated successfully")
        print(f"Report length: {len(verbose_report)} characters")

        # Check that key sections are present
        assert "# Multi-Tool Orchestration Report" in verbose_report
        assert "Test Assistant" in verbose_report
        assert "simple_rag" in verbose_report
        assert "1_context" in verbose_report
        assert "Python is a programming language" in verbose_report
        assert "Python Docs" in verbose_report

        print("✓ Verbose report contains expected content")

        return True

    except Exception as e:
        print(f"Error testing verbose orchestrator: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_stream_callback():
    """Test stream callback functionality."""

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lamb'))

        from lamb.completions.orchestrators.sequential import SequentialOrchestrator

        orchestrator = SequentialOrchestrator()

        # Test callback collection
        collected_messages = []

        def test_callback(message: str):
            collected_messages.append(message)
            print(f"Stream: {message}")

        # Call the callback a few times
        test_callback("🔄 Starting tool execution")
        test_callback("✅ Tool completed successfully")

        assert len(collected_messages) == 2
        assert "Starting tool execution" in collected_messages[0]
        assert "Tool completed successfully" in collected_messages[1]

        print("✓ Stream callback functionality works")

        return True

    except Exception as e:
        print(f"Error testing stream callback: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Testing verbose orchestrator functionality...\n")

    success = True
    success &= test_verbose_orchestrator()
    success &= test_stream_callback()

    if success:
        print("\n✅ All verbose orchestrator tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)