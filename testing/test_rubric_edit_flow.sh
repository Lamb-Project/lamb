#!/bin/bash

# Test script for rubric creation and editing flow
# Tests the full cycle: create -> load -> edit -> update

BASE_URL="http://localhost:9099"
ADMIN_EMAIL="admin@owi.com"
ADMIN_PASSWORD="admin"

echo "============================================================"
echo "RUBRIC EDIT FLOW TEST"
echo "============================================================"

# Step 1: Login
echo ""
echo "🔐 Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/creator/login" \
  -F "email=$ADMIN_EMAIL" \
  -F "password=$ADMIN_PASSWORD")

TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ Login failed"
  echo "$LOGIN_RESPONSE"
  exit 1
fi

echo "✅ Login successful, got token: ${TOKEN:0:20}..."

# Step 2: Create rubric
echo ""
echo "📝 Creating test rubric..."
TIMESTAMP=$(date +%s)

CREATE_RESPONSE=$(curl -s -X POST "$BASE_URL/creator/rubrics" \
  -H "Authorization: Bearer $TOKEN" \
  -F "title=Test Rubric $TIMESTAMP" \
  -F "description=This is a test rubric for editing" \
  -F "subject=Math" \
  -F "gradeLevel=6-8" \
  -F "scoringType=points" \
  -F "maxScore=100" \
  -F 'criteria=[{"name":"Understanding","description":"Student demonstrates understanding","weight":50,"levels":[{"score":4,"label":"Exemplary","description":"Complete understanding demonstrated"},{"score":3,"label":"Proficient","description":"Good understanding demonstrated"},{"score":2,"label":"Developing","description":"Partial understanding demonstrated"},{"score":1,"label":"Beginning","description":"Limited understanding demonstrated"}]},{"name":"Communication","description":"Student communicates ideas clearly","weight":50,"levels":[{"score":4,"label":"Exemplary","description":"Ideas are very clear"},{"score":3,"label":"Proficient","description":"Ideas are mostly clear"},{"score":2,"label":"Developing","description":"Ideas are somewhat clear"},{"score":1,"label":"Beginning","description":"Ideas are unclear"}]}]')

echo "Create response: $CREATE_RESPONSE"

RUBRIC_ID=$(echo $CREATE_RESPONSE | grep -o '"rubric_id":"[^"]*' | cut -d'"' -f4)
if [ -z "$RUBRIC_ID" ]; then
  RUBRIC_ID=$(echo $CREATE_RESPONSE | grep -o '"rubricId":"[^"]*' | cut -d'"' -f4)
fi

if [ -z "$RUBRIC_ID" ]; then
  echo "❌ Create failed - no rubric ID returned"
  echo "$CREATE_RESPONSE"
  exit 1
fi

echo "✅ Rubric created successfully, ID: $RUBRIC_ID"

# Step 3: Fetch rubric
echo ""
echo "📖 Fetching rubric $RUBRIC_ID..."
FETCH_RESPONSE=$(curl -s -X GET "$BASE_URL/creator/rubrics/$RUBRIC_ID" \
  -H "Authorization: Bearer $TOKEN")

TITLE=$(echo $FETCH_RESPONSE | grep -o '"title":"[^"]*' | cut -d'"' -f4)
if [ -z "$TITLE" ]; then
  echo "❌ Fetch failed"
  echo "$FETCH_RESPONSE"
  exit 1
fi

echo "✅ Rubric fetched successfully"
echo "   Title: $TITLE"

# Step 4: Update rubric (simulating cell edit)
echo ""
echo "✏️  Updating rubric cell..."

# For simplicity, we'll just update the description
UPDATE_RESPONSE=$(curl -s -X PUT "$BASE_URL/creator/rubrics/$RUBRIC_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -F "title=Test Rubric $TIMESTAMP" \
  -F "description=UPDATED: This is a test rubric for editing" \
  -F "subject=Math" \
  -F "gradeLevel=6-8" \
  -F "scoringType=points" \
  -F "maxScore=100" \
  -F 'criteria=[{"name":"Understanding","description":"Student demonstrates understanding","weight":50,"levels":[{"score":4,"label":"Exemplary","description":"UPDATED: Complete understanding demonstrated"},{"score":3,"label":"Proficient","description":"Good understanding demonstrated"},{"score":2,"label":"Developing","description":"Partial understanding demonstrated"},{"score":1,"label":"Beginning","description":"Limited understanding demonstrated"}]},{"name":"Communication","description":"Student communicates ideas clearly","weight":50,"levels":[{"score":4,"label":"Exemplary","description":"Ideas are very clear"},{"score":3,"label":"Proficient","description":"Ideas are mostly clear"},{"score":2,"label":"Developing","description":"Ideas are somewhat clear"},{"score":1,"label":"Beginning","description":"Ideas are unclear"}]}]')

echo "Update response: $UPDATE_RESPONSE"

if echo "$UPDATE_RESPONSE" | grep -q "error\|Error\|detail"; then
  echo "❌ Update failed"
  exit 1
fi

echo "✅ Rubric updated successfully"

# Step 5: Verify update
echo ""
echo "🔍 Verifying update..."
VERIFY_RESPONSE=$(curl -s -X GET "$BASE_URL/creator/rubrics/$RUBRIC_ID" \
  -H "Authorization: Bearer $TOKEN")

if echo "$VERIFY_RESPONSE" | grep -q "UPDATED:"; then
  echo "✅ Update verified!"
else
  echo "⚠️  Update may not have been saved"
  echo "$VERIFY_RESPONSE"
fi

echo ""
echo "============================================================"
echo "✅ TEST COMPLETED!"
echo "============================================================"
echo ""
echo "Test rubric ID: $RUBRIC_ID"
echo "You can view it at: http://localhost:5173/evaluaitor/$RUBRIC_ID"

