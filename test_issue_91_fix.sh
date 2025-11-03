#!/bin/bash

# Test script for Issue #91 fix
# Verifies that "LAMB System Organization" and "API Status Overview" sections
# appear after page reload on Settings view

echo "========================================="
echo "Testing Issue #91 Fix"
echo "========================================="
echo ""

# Backend URL
BACKEND_URL="http://localhost:9099"

# Test credentials
EMAIL="admin@owi.com"
PASSWORD="admin"

echo "Step 1: Login with admin credentials..."
LOGIN_RESPONSE=$(curl -s -X POST "${BACKEND_URL}/creator/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=${EMAIL}&password=${PASSWORD}")

# Extract token
TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.token // empty')

if [ -z "$TOKEN" ]; then
    echo "❌ FAILED: Could not login. Response:"
    echo "$LOGIN_RESPONSE" | jq '.'
    exit 1
fi

echo "✅ Successfully logged in"
echo ""

echo "Step 2: Test Dashboard endpoint (for API status data)..."
DASHBOARD_RESPONSE=$(curl -s -X GET "${BACKEND_URL}/creator/admin/org-admin/dashboard" \
  -H "Authorization: Bearer ${TOKEN}")

# Check if dashboard has api_status
HAS_API_STATUS=$(echo "$DASHBOARD_RESPONSE" | jq 'has("api_status")')

if [ "$HAS_API_STATUS" = "true" ]; then
    echo "✅ Dashboard endpoint returns api_status"
    echo "   API Status data:"
    echo "$DASHBOARD_RESPONSE" | jq '.api_status.providers | keys'
else
    echo "⚠️  Dashboard endpoint does not return api_status"
    echo "   This is expected if no API providers are configured"
fi

# Check if dashboard has organization info
HAS_ORG=$(echo "$DASHBOARD_RESPONSE" | jq 'has("organization")')

if [ "$HAS_ORG" = "true" ]; then
    ORG_NAME=$(echo "$DASHBOARD_RESPONSE" | jq -r '.organization.name')
    ORG_SLUG=$(echo "$DASHBOARD_RESPONSE" | jq -r '.organization.slug')
    echo "✅ Dashboard endpoint returns organization data"
    echo "   Organization: $ORG_NAME ($ORG_SLUG)"
else
    echo "❌ FAILED: Dashboard endpoint does not return organization data"
    exit 1
fi

echo ""

echo "Step 3: Test Settings endpoints..."
SIGNUP_RESPONSE=$(curl -s -X GET "${BACKEND_URL}/creator/admin/org-admin/settings/signup" \
  -H "Authorization: Bearer ${TOKEN}")

HAS_SIGNUP=$(echo "$SIGNUP_RESPONSE" | jq 'has("signup_enabled")')

if [ "$HAS_SIGNUP" = "true" ]; then
    echo "✅ Signup settings endpoint working"
else
    echo "❌ FAILED: Signup settings endpoint failed"
    echo "$SIGNUP_RESPONSE" | jq '.'
    exit 1
fi

API_RESPONSE=$(curl -s -X GET "${BACKEND_URL}/creator/admin/org-admin/settings/api" \
  -H "Authorization: Bearer ${TOKEN}")

HAS_API=$(echo "$API_RESPONSE" | jq 'has("openai_api_key_set")')

if [ "$HAS_API" = "true" ]; then
    echo "✅ API settings endpoint working"
else
    echo "❌ FAILED: API settings endpoint failed"
    echo "$API_RESPONSE" | jq '.'
    exit 1
fi

echo ""
echo "========================================="
echo "✅ All backend endpoints are working!"
echo "========================================="
echo ""
echo "Summary of the fix:"
echo "-------------------"
echo "The fetchSettings() function in org-admin/+page.svelte"
echo "now calls fetchDashboard() to ensure both:"
echo "  1. Organization Header (showing org name)"
echo "  2. API Status Overview (showing provider status)"
echo "are populated even when the page is refreshed directly"
echo "on the Settings view."
echo ""
echo "Manual testing steps:"
echo "1. Navigate to http://localhost:5173"
echo "2. Login with admin@owi.com / admin"
echo "3. Go to Org Admin > Settings"
echo "4. Verify you see organization header and API status sections"
echo "5. Refresh the page (F5 or Ctrl+F5)"
echo "6. ✅ Both sections should still be visible (this was the bug)"
echo ""

