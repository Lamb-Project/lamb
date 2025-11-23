#!/bin/bash
# Diagnostic script for "KB (Not Found)" issues after migration
# Usage: ./diagnose_kb_display_issue.sh <assistant_id> <kb_id>

set -e

ASSISTANT_ID=${1:-19}
KB_ID=${2:-13}

echo "=========================================================================="
echo "KB Display Issue Diagnostic Tool"
echo "=========================================================================="
echo "Checking assistant $ASSISTANT_ID with KB $KB_ID"
echo ""

# Load environment variables
if [ -f /opt/lamb/backend/.env ]; then
    export $(cat /opt/lamb/backend/.env | grep -v '^#' | xargs)
    echo "✓ Loaded environment variables from /opt/lamb/backend/.env"
else
    echo "✗ Environment file not found at /opt/lamb/backend/.env"
    exit 1
fi

echo ""
echo "1. Checking KB Registry Entry"
echo "--------------------------------------------------------------------------"
DB_PATH="${LAMB_DB_PATH}/lamb_v4.db"
if [ -f "$DB_PATH" ]; then
    echo "Database: $DB_PATH"
    REGISTRY_RESULT=$(sqlite3 "$DB_PATH" "SELECT kb_id, kb_name, owner_user_id FROM LAMB_kb_registry WHERE kb_id = '$KB_ID';")
    if [ -n "$REGISTRY_RESULT" ]; then
        echo "✓ KB $KB_ID found in registry:"
        echo "  $REGISTRY_RESULT"
    else
        echo "✗ KB $KB_ID NOT found in registry"
        echo "  Run migration script to register it: python /opt/lamb/scripts/migrate_kb_registry.py"
    fi
else
    echo "✗ Database not found at $DB_PATH"
fi

echo ""
echo "2. Checking Assistant RAG Collections"
echo "--------------------------------------------------------------------------"
ASSISTANT_RESULT=$(sqlite3 "$DB_PATH" "SELECT id, name, RAG_collections FROM LAMB_assistants WHERE id = $ASSISTANT_ID;")
if [ -n "$ASSISTANT_RESULT" ]; then
    echo "✓ Assistant $ASSISTANT_ID found:"
    echo "  $ASSISTANT_RESULT"
else
    echo "✗ Assistant $ASSISTANT_ID NOT found"
fi

echo ""
echo "3. Checking KB Server Connectivity"
echo "--------------------------------------------------------------------------"
if [ -z "$LAMB_KB_SERVER" ]; then
    echo "✗ LAMB_KB_SERVER environment variable not set"
else
    echo "KB Server URL: $LAMB_KB_SERVER"
    
    if [ -z "$LAMB_KB_SERVER_TOKEN" ]; then
        echo "✗ LAMB_KB_SERVER_TOKEN environment variable not set"
    else
        echo "Testing KB Server endpoint..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer $LAMB_KB_SERVER_TOKEN" \
            "$LAMB_KB_SERVER/collections/$KB_ID")
        
        if [ "$HTTP_CODE" = "200" ]; then
            echo "✓ KB $KB_ID exists in KB Server (HTTP $HTTP_CODE)"
            KB_DATA=$(curl -s -H "Authorization: Bearer $LAMB_KB_SERVER_TOKEN" \
                "$LAMB_KB_SERVER/collections/$KB_ID" | python3 -m json.tool 2>/dev/null || echo "{}")
            echo "  KB Data:"
            echo "$KB_DATA" | head -20
        elif [ "$HTTP_CODE" = "404" ]; then
            echo "✗ KB $KB_ID NOT found in KB Server (HTTP $HTTP_CODE)"
            echo "  The KB was deleted from KB Server but is still referenced in assistants"
        else
            echo "⚠ KB Server returned HTTP $HTTP_CODE"
        fi
    fi
fi

echo ""
echo "4. Backend API Test"
echo "--------------------------------------------------------------------------"
if [ -z "$LAMB_BACKEND_HOST" ]; then
    echo "✗ LAMB_BACKEND_HOST environment variable not set"
else
    echo "Backend URL: $LAMB_BACKEND_HOST"
    echo "Testing backend KB endpoint..."
    
    # Note: This requires a valid user token to work
    echo "⚠ Skipping backend API test (requires user authentication)"
    echo "  To test manually, use:"
    echo "  curl -H 'Authorization: Bearer <user_token>' \\"
    echo "       $LAMB_BACKEND_HOST/creator/knowledgebases/user"
fi

echo ""
echo "=========================================================================="
echo "Diagnosis Summary"
echo "=========================================================================="

if [ -n "$REGISTRY_RESULT" ] && [ "$HTTP_CODE" = "200" ]; then
    echo "✓ KB is in registry AND KB Server - issue is likely:"
    echo "  1. Backend needs restart: docker restart lamb-backend-1"
    echo "  2. Browser cache: Hard refresh (Cmd+Shift+R or Ctrl+Shift+R)"
    echo "  3. Frontend not fetching KBs: Check browser console for errors"
elif [ -n "$REGISTRY_RESULT" ] && [ "$HTTP_CODE" = "404" ]; then
    echo "⚠ KB is in registry but NOT in KB Server:"
    echo "  - The KB was deleted from KB Server"
    echo "  - Remove it from assistant's RAG_collections"
    echo "  - Or recreate the KB with ID $KB_ID"
elif [ -z "$REGISTRY_RESULT" ] && [ "$HTTP_CODE" = "200" ]; then
    echo "✗ KB exists in KB Server but NOT in registry:"
    echo "  Run: python /opt/lamb/scripts/migrate_kb_registry.py"
else
    echo "✗ KB not found in registry OR KB Server"
    echo "  Check if the KB ID is correct"
fi

echo ""
echo "Next Steps:"
echo "  1. If migration hasn't run: python /opt/lamb/scripts/migrate_kb_registry.py"
echo "  2. Restart backend: docker restart lamb-backend-1"
echo "  3. Hard refresh browser"
echo "  4. Check browser console for API errors"
echo "=========================================================================="
