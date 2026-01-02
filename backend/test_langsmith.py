#!/usr/bin/env python3
"""
Test script to verify LangSmith tracing integration

This script demonstrates:
1. How to check if tracing is enabled
2. How to use the @traceable decorator
3. How to add custom metadata
4. Example trace hierarchy
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.langsmith_config import (
    traceable_llm_call,
    add_trace_metadata,
    add_trace_tags,
    is_tracing_enabled,
    get_langsmith_client
)


def check_tracing_status():
    """Check if LangSmith tracing is configured"""
    print("=" * 60)
    print("LangSmith Tracing Status")
    print("=" * 60)
    
    print(f"\nTracing Enabled: {is_tracing_enabled()}")
    print(f"LangSmith Client: {get_langsmith_client()}")
    
    # Check environment variables
    print("\nEnvironment Variables:")
    print(f"  LANGCHAIN_TRACING_V2: {os.getenv('LANGCHAIN_TRACING_V2', 'not set')}")
    print(f"  LANGCHAIN_API_KEY: {'***' if os.getenv('LANGCHAIN_API_KEY') else 'not set'}")
    print(f"  LANGCHAIN_PROJECT: {os.getenv('LANGCHAIN_PROJECT', 'not set')}")
    print(f"  LANGCHAIN_ENDPOINT: {os.getenv('LANGCHAIN_ENDPOINT', 'not set (using default)')}")
    
    print("\n" + "=" * 60)
    return is_tracing_enabled()


@traceable_llm_call(name="dummy_llm_call", run_type="llm", tags=["test", "demo"])
async def dummy_llm_call(model: str, messages: list):
    """Simulated LLM call for testing"""
    # Add custom metadata
    add_trace_metadata("model", model)
    add_trace_metadata("message_count", len(messages))
    add_trace_metadata("test_mode", True)
    
    # Simulate processing
    await asyncio.sleep(0.1)
    
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "This is a test response from the dummy LLM"
            }
        }]
    }


@traceable_llm_call(name="dummy_pipeline", run_type="chain", tags=["test", "pipeline"])
async def dummy_pipeline(assistant_name: str, user_message: str):
    """Simulated completion pipeline for testing"""
    # Add pipeline metadata
    add_trace_metadata("assistant_name", assistant_name)
    add_trace_metadata("user_message", user_message)
    add_trace_tags("production", "test-run")
    
    # Prepare messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": user_message}
    ]
    
    # Call dummy LLM (creates nested trace)
    response = await dummy_llm_call(model="gpt-4o-mini", messages=messages)
    
    return response


async def run_test():
    """Run test traces"""
    print("\nRunning Test Traces...")
    print("-" * 60)
    
    # Test 1: Simple LLM call
    print("\n1. Testing simple LLM call...")
    result1 = await dummy_llm_call(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    print(f"   ✓ Completed: {result1['choices'][0]['message']['content'][:50]}...")
    
    # Test 2: Pipeline with nested trace
    print("\n2. Testing pipeline with nested traces...")
    result2 = await dummy_pipeline(
        assistant_name="Test Assistant",
        user_message="What is 2+2?"
    )
    print(f"   ✓ Completed: {result2['choices'][0]['message']['content'][:50]}...")
    
    print("\n" + "-" * 60)
    print("\nTest completed successfully!")
    
    if is_tracing_enabled():
        print("\n✅ Traces sent to LangSmith!")
        print("   View them at: https://smith.langchain.com/")
        print(f"   Project: {os.getenv('LANGCHAIN_PROJECT', 'lamb-assistants')}")
    else:
        print("\nℹ️  Tracing is disabled - no traces were sent")
        print("   To enable: export LANGCHAIN_TRACING_V2=true")


async def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print("LAMB LangSmith Tracing Test")
    print("=" * 60 + "\n")
    
    # Check tracing status
    tracing_enabled = check_tracing_status()
    
    if not tracing_enabled:
        print("\n⚠️  WARNING: Tracing is currently disabled")
        print("\nTo enable tracing, set these environment variables:")
        print("  export LANGCHAIN_TRACING_V2=true")
        print("  export LANGCHAIN_API_KEY=your-key-here")
        print("  export LANGCHAIN_PROJECT=lamb-assistants")
        print("\nThe test will still run, but traces won't be sent to LangSmith.")
        
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            print("\nExiting...")
            return
    
    # Run tests
    await run_test()
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
