#!/bin/bash

# LAMB Playwright Test Runner
# Updated tests using MCP exploration

echo "🚀 LAMB Updated Playwright Test Suite"
echo "====================================="
echo ""

BASE_URL="http://localhost:5173"

# Check if services are running
echo "🔍 Checking service availability..."

if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Frontend available at $BASE_URL"
else
    echo "❌ Frontend not available at $BASE_URL"
    echo "   Please start the LAMB services first:"
    echo "   docker-compose up -d"
    exit 1
fi

if curl -s http://localhost:9099/status > /dev/null 2>&1; then
    echo "✅ Backend available at http://localhost:9099"
else
    echo "❌ Backend not available at http://localhost:9099"
    exit 1
fi

if curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo "✅ OpenWebUI available at http://localhost:8080"
else
    echo "⚠️  OpenWebUI not available at http://localhost:8080"
fi

if curl -s http://localhost:9090/api/status > /dev/null 2>&1; then
    echo "✅ Knowledge Base server available at http://localhost:9090"
else
    echo "⚠️  Knowledge Base server not available at http://localhost:9090"
fi

echo ""
echo "🧪 Running Tests..."
echo "=================="

# Test 1: Organization & LLM Configuration
echo ""
echo "🏢 Running Organization & LLM Configuration Test..."
node organization_llm_test.js "$BASE_URL"
ORG_EXIT_CODE=$?

# Test 2: Comprehensive Test (commented out by default as it's more complex)
echo ""
echo "🤖 Comprehensive Test (MCP-based)... (Skipped - run manually if needed)"
echo "   To run: node mcp_comprehensive_test.js $BASE_URL"
# node mcp_comprehensive_test.js "$BASE_URL"
# COMP_EXIT_CODE=$?

echo ""
echo "📊 Test Results Summary"
echo "======================="
echo "🏢 Organization & LLM Test: $([ $ORG_EXIT_CODE -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
# echo "🤖 Comprehensive Test: $([ $COMP_EXIT_CODE -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"

echo ""
echo "📝 Notes:"
echo "- Tests create real data in the system"
echo "- Check admin panel for created organizations and users"
echo "- Tests use unique timestamps to avoid conflicts"
echo "- Some tests may fail if UI elements change"

if [ $ORG_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "🎉 All tests completed successfully!"
    exit 0
else
    echo ""
    echo "❌ Some tests failed. Check output above for details."
    exit 1
fi
