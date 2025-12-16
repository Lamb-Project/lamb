#!/bin/bash

# Multi-Tool Assistant Endpoint Testing Script
# This script tests the endpoint fixes we applied

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║     Multi-Tool Assistant Endpoint Testing Script             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:9099}"
TOKEN="${USER_TOKEN}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
PASSED=0
FAILED=0
SKIPPED=0

# Helper functions
test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local expected_status="$4"
    local data="$5"
    
    echo -n "Testing: ${name}... "
    
    if [ -z "$TOKEN" ]; then
        echo -e "${YELLOW}SKIPPED${NC} (no auth token)"
        ((SKIPPED++))
        return
    fi
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" -X GET \
            -H "Authorization: Bearer ${TOKEN}" \
            "${BACKEND_URL}${endpoint}" 2>/dev/null)
    else
        response=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Authorization: Bearer ${TOKEN}" \
            -H "Content-Type: application/json" \
            -d "${data}" \
            "${BACKEND_URL}${endpoint}" 2>/dev/null)
    fi
    
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}✅ PASS${NC} (HTTP ${status_code})"
        ((PASSED++))
        if [ ! -z "$body" ] && [ "$body" != "null" ]; then
            echo "   Response preview: $(echo "$body" | head -c 100)..."
        fi
    elif [ "$status_code" = "404" ]; then
        echo -e "${RED}❌ FAIL${NC} (HTTP ${status_code} - Endpoint not found)"
        ((FAILED++))
    elif [ "$status_code" = "401" ]; then
        echo -e "${YELLOW}⚠️  AUTH${NC} (HTTP ${status_code} - Authentication required)"
        ((SKIPPED++))
    else
        echo -e "${YELLOW}⚠️  WARN${NC} (HTTP ${status_code})"
        ((FAILED++))
        echo "   Response: $body"
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Phase 1: Basic Connectivity Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 1.1: Tools Discovery
test_endpoint \
    "Tools Discovery" \
    "GET" \
    "/lamb/v1/completions/tools" \
    "200"

echo ""

# Test 1.2: Orchestrators Discovery  
test_endpoint \
    "Orchestrators Discovery" \
    "GET" \
    "/lamb/v1/completions/orchestrators" \
    "200"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Phase 2: Assistant Creation Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 2.1: Create Multi-Tool Assistant (minimal config)
test_data='{
  "name": "Test_Multi_Tool_Assistant",
  "description": "Testing multi-tool endpoint fix",
  "system_prompt": "You are a helpful assistant.",
  "prompt_template": "Context: {1_context}\n\nUser: {user_input}\nAssistant:",
  "metadata": "{\"assistant_type\":\"multi_tool\",\"orchestrator\":\"sequential\",\"connector\":\"openai\",\"llm\":\"gpt-4o-mini\",\"verbose\":false,\"tools\":[{\"plugin\":\"simple_rag\",\"placeholder\":\"1_context\",\"enabled\":true,\"config\":{\"collections\":[],\"top_k\":3}}]}"
}'

test_endpoint \
    "Create Multi-Tool Assistant" \
    "POST" \
    "/creator/assistant/create_assistant" \
    "201" \
    "$test_data"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Phase 3: Verification Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 3.1: Verify backend file exists
echo -n "Checking backend completions router... "
if [ -f "/opt/lamb/backend/lamb/completions/main.py" ]; then
    if grep -q "def get_multi_tool_completion" "/opt/lamb/backend/lamb/completions/main.py"; then
        echo -e "${GREEN}✅ PASS${NC} (multi-tool routing found)"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️  WARN${NC} (file exists but multi-tool routing not found)"
        ((FAILED++))
    fi
else
    echo -e "${RED}❌ FAIL${NC} (completions main.py not found)"
    ((FAILED++))
fi

echo ""

# Test 3.2: Verify frontend file exists and has correct endpoints
echo -n "Checking frontend service file... "
if [ -f "/opt/lamb/frontend/svelte-app/src/lib/services/multiToolAssistantService.js" ]; then
    if grep -q "/creator/assistant/create_assistant" "/opt/lamb/frontend/svelte-app/src/lib/services/multiToolAssistantService.js"; then
        echo -e "${GREEN}✅ PASS${NC} (create endpoint fixed)"
        ((PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC} (create endpoint not fixed)"
        ((FAILED++))
    fi
else
    echo -e "${RED}❌ FAIL${NC} (service file not found)"
    ((FAILED++))
fi

echo ""

echo -n "Checking update endpoint fix... "
if grep -q "/creator/assistant/update_assistant" "/opt/lamb/frontend/svelte-app/src/lib/services/multiToolAssistantService.js"; then
    echo -e "${GREEN}✅ PASS${NC} (update endpoint fixed)"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC} (update endpoint not fixed)"
    ((FAILED++))
fi

echo ""

echo -n "Checking tools endpoint fix... "
if grep -q "/lamb/v1/completions/tools" "/opt/lamb/frontend/svelte-app/src/lib/services/multiToolAssistantService.js"; then
    echo -e "${GREEN}✅ PASS${NC} (tools endpoint fixed)"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC} (tools endpoint not fixed)"
    ((FAILED++))
fi

echo ""

echo -n "Checking orchestrators endpoint fix... "
if grep -q "/lamb/v1/completions/orchestrators" "/opt/lamb/frontend/svelte-app/src/lib/services/multiToolAssistantService.js"; then
    echo -e "${GREEN}✅ PASS${NC} (orchestrators endpoint fixed)"
    ((PASSED++))
else
    echo -e "${RED}❌ FAIL${NC} (orchestrators endpoint not fixed)"
    ((FAILED++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Test Results Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  ${GREEN}Passed:${NC}  $PASSED"
echo -e "  ${RED}Failed:${NC}  $FAILED"
echo -e "  ${YELLOW}Skipped:${NC} $SKIPPED"
echo ""

TOTAL=$((PASSED + FAILED))
if [ $TOTAL -gt 0 ]; then
    SUCCESS_RATE=$((PASSED * 100 / TOTAL))
    echo -e "  Success Rate: ${SUCCESS_RATE}%"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Notes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
if [ -z "$TOKEN" ]; then
    echo "⚠️  No authentication token provided."
    echo "   To test API endpoints, set USER_TOKEN environment variable:"
    echo "   export USER_TOKEN='your-jwt-token'"
    echo ""
fi

if [ $FAILED -gt 0 ]; then
    echo "❌ Some tests failed. Check the output above for details."
    exit 1
else
    echo "✅ All file-based tests passed!"
    if [ $SKIPPED -gt 0 ]; then
        echo "⚠️  API endpoint tests skipped (requires running services + auth token)"
        echo ""
        echo "To run full tests:"
        echo "  1. Start services: docker-compose up -d"
        echo "  2. Get auth token from login"
        echo "  3. Run: USER_TOKEN='token' ./test_multi_tool_endpoints.sh"
    fi
    exit 0
fi
