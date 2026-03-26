#!/bin/bash

# Test script for Prompt Templates API endpoints
# This script tests all CRUD operations for the prompt templates feature

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${LAMB_BACKEND_HOST:-http://localhost:9099}"
CREATOR_URL="$BASE_URL/creator"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@lamb.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Prompt Templates API Test Suite${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "Testing against: $BASE_URL"
echo ""

# Function to print test results
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2${NC}"
    else
        echo -e "${RED}✗ $2${NC}"
        exit 1
    fi
}

# Function to make API call and check response
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3
    local expected_status=$4
    
    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            "$CREATOR_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$CREATOR_URL$endpoint")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected_status" ]; then
        echo "$body"
        return 0
    else
        echo "Expected status $expected_status but got $http_code"
        echo "Response: $body"
        return 1
    fi
}

# Step 1: Login to get token
echo -e "${YELLOW}Step 1: Authenticating...${NC}"
login_response=$(curl -s -X POST "$CREATOR_URL/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "email=$ADMIN_EMAIL&password=$ADMIN_PASSWORD")

TOKEN=$(echo "$login_response" | grep -o '"token":"[^"]*' | sed 's/"token":"//')

if [ -z "$TOKEN" ]; then
    echo -e "${RED}Failed to authenticate${NC}"
    echo "Response: $login_response"
    exit 1
fi

print_result 0 "Authentication successful"
echo ""

# Step 2: Create a prompt template
echo -e "${YELLOW}Step 2: Creating a prompt template...${NC}"
create_data='{
    "name": "Socratic Mathematics Tutor",
    "description": "Guide students through problem-solving with questions",
    "system_prompt": "You are a Socratic mathematics tutor. Instead of giving direct answers, guide students to discover solutions through thoughtful questions. Focus on understanding rather than just answers.",
    "prompt_template": "Student Question: {user_message}\n\nGuide the student with questions:",
    "is_shared": false,
    "metadata": {
        "subject": "mathematics",
        "style": "socratic",
        "level": "high_school"
    }
}'

create_response=$(api_call "POST" "/prompt-templates/create" "$create_data" "201")
TEMPLATE_ID=$(echo "$create_response" | grep -o '"id":[0-9]*' | head -1 | sed 's/"id"://')

if [ -z "$TEMPLATE_ID" ]; then
    echo -e "${RED}Failed to create template${NC}"
    echo "Response: $create_response"
    exit 1
fi

print_result 0 "Template created with ID: $TEMPLATE_ID"
echo ""

# Step 3: Get the template by ID
echo -e "${YELLOW}Step 3: Retrieving template by ID...${NC}"
get_response=$(api_call "GET" "/prompt-templates/$TEMPLATE_ID" "" "200")
template_name=$(echo "$get_response" | grep -o '"name":"[^"]*' | head -1 | sed 's/"name":"//')

if [ "$template_name" = "Socratic Mathematics Tutor" ]; then
    print_result 0 "Template retrieved successfully"
else
    print_result 1 "Template name mismatch"
fi
echo ""

# Step 4: List user's templates
echo -e "${YELLOW}Step 4: Listing user templates...${NC}"
list_response=$(api_call "GET" "/prompt-templates/list?limit=10&offset=0" "" "200")
template_count=$(echo "$list_response" | grep -o '"total":[0-9]*' | sed 's/"total"://')

if [ -n "$template_count" ] && [ "$template_count" -gt 0 ]; then
    print_result 0 "Found $template_count template(s)"
else
    print_result 1 "No templates found"
fi
echo ""

# Step 5: Update the template
echo -e "${YELLOW}Step 5: Updating template...${NC}"
update_data='{
    "description": "Updated: Guide students through mathematical problem-solving with Socratic questioning",
    "is_shared": true
}'

update_response=$(api_call "PUT" "/prompt-templates/$TEMPLATE_ID" "$update_data" "200")
is_shared=$(echo "$update_response" | grep -o '"is_shared":[a-z]*' | sed 's/"is_shared"://')

if [ "$is_shared" = "true" ]; then
    print_result 0 "Template updated and shared successfully"
else
    print_result 1 "Template sharing status not updated"
fi
echo ""

# Step 6: List shared templates
echo -e "${YELLOW}Step 6: Listing shared templates...${NC}"
shared_response=$(api_call "GET" "/prompt-templates/shared?limit=10&offset=0" "" "200")
# This should be empty or less because we're looking at templates shared by others
print_result 0 "Shared templates list retrieved"
echo ""

# Step 7: Duplicate the template
echo -e "${YELLOW}Step 7: Duplicating template...${NC}"
duplicate_data='{"new_name": "Copy of Socratic Math Tutor"}'
duplicate_response=$(api_call "POST" "/prompt-templates/$TEMPLATE_ID/duplicate" "$duplicate_data" "201")
DUPLICATE_ID=$(echo "$duplicate_response" | grep -o '"id":[0-9]*' | head -1 | sed 's/"id"://')

if [ -n "$DUPLICATE_ID" ] && [ "$DUPLICATE_ID" != "$TEMPLATE_ID" ]; then
    print_result 0 "Template duplicated with new ID: $DUPLICATE_ID"
else
    print_result 1 "Template duplication failed"
fi
echo ""

# Step 8: Export templates
echo -e "${YELLOW}Step 8: Exporting templates...${NC}"
export_data="{\"template_ids\": [$TEMPLATE_ID, $DUPLICATE_ID]}"
export_response=$(api_call "POST" "/prompt-templates/export" "$export_data" "200")
export_version=$(echo "$export_response" | grep -o '"export_version":"[^"]*' | sed 's/"export_version":"//')

if [ "$export_version" = "1.0" ]; then
    print_result 0 "Templates exported successfully"
    echo "Export preview:"
    echo "$export_response" | head -n 5
else
    print_result 1 "Template export failed"
fi
echo ""

# Step 9: Toggle sharing off
echo -e "${YELLOW}Step 9: Toggling sharing off...${NC}"
share_data='{"is_shared": false}'
share_response=$(api_call "PUT" "/prompt-templates/$TEMPLATE_ID/share" "$share_data" "200")
is_shared_off=$(echo "$share_response" | grep -o '"is_shared":[a-z]*' | sed 's/"is_shared"://')

if [ "$is_shared_off" = "false" ]; then
    print_result 0 "Template sharing toggled off"
else
    print_result 1 "Template sharing toggle failed"
fi
echo ""

# Step 10: Delete the duplicate template
echo -e "${YELLOW}Step 10: Deleting duplicate template...${NC}"
if api_call "DELETE" "/prompt-templates/$DUPLICATE_ID" "" "204" > /dev/null 2>&1; then
    print_result 0 "Duplicate template deleted"
else
    print_result 1 "Failed to delete duplicate template"
fi
echo ""

# Step 11: Delete the original template
echo -e "${YELLOW}Step 11: Deleting original template...${NC}"
if api_call "DELETE" "/prompt-templates/$TEMPLATE_ID" "" "204" > /dev/null 2>&1; then
    print_result 0 "Original template deleted"
else
    print_result 1 "Failed to delete original template"
fi
echo ""

# Step 12: Verify deletion
echo -e "${YELLOW}Step 12: Verifying deletion...${NC}"
verify_response=$(curl -s -w "\n%{http_code}" -X GET \
    -H "Authorization: Bearer $TOKEN" \
    "$CREATOR_URL/prompt-templates/$TEMPLATE_ID")
verify_code=$(echo "$verify_response" | tail -n1)

if [ "$verify_code" = "404" ]; then
    print_result 0 "Template successfully deleted (404 confirmed)"
else
    print_result 1 "Template still exists after deletion"
fi
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All tests passed successfully! ✓${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Summary:"
echo "  - Authentication: ✓"
echo "  - Create template: ✓"
echo "  - Get template: ✓"
echo "  - List templates: ✓"
echo "  - Update template: ✓"
echo "  - Share template: ✓"
echo "  - List shared: ✓"
echo "  - Duplicate template: ✓"
echo "  - Export templates: ✓"
echo "  - Toggle sharing: ✓"
echo "  - Delete template: ✓"
echo "  - Verify deletion: ✓"
echo ""
echo -e "${GREEN}Week 1 Backend Implementation: COMPLETE${NC}"

