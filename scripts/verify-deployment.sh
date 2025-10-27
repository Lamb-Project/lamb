#!/bin/bash
# scripts/verify-deployment.sh - Verify LAMB deployment health

echo "🔍 LAMB Deployment Verification"
echo "================================"
echo ""

ERRORS=0

# Function to check endpoint
check_endpoint() {
    local NAME=$1
    local URL=$2
    local EXPECTED_CODE=${3:-200}
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "$EXPECTED_CODE" ]; then
        echo "✅ $NAME: OK ($HTTP_CODE)"
        return 0
    else
        echo "❌ $NAME: FAILED (got $HTTP_CODE, expected $EXPECTED_CODE)"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo "❌ curl is not installed. Please install curl to run this verification."
    exit 1
fi

# Check containers
echo "📦 Checking containers..."
REQUIRED_CONTAINERS=("lamb-frontend" "lamb-backend" "lamb-openwebui" "lamb-kb-server")
for container in "${REQUIRED_CONTAINERS[@]}"; do
    if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
        STATUS=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null)
        if [ "$STATUS" = "running" ]; then
            echo "✅ $container: running"
        else
            echo "❌ $container: $STATUS"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "❌ $container: not found"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
echo "🌐 Checking endpoints..."
check_endpoint "Frontend" "http://localhost:5173/" 200
check_endpoint "Backend Status" "http://localhost:9099/status" 200
check_endpoint "OpenWebUI" "http://localhost:8080/" 200
check_endpoint "KB Server Health" "http://localhost:9090/health" 200

# Check if OpenWebUI is serving frontend or API-only
echo ""
echo "🔍 Checking OpenWebUI frontend..."
OWI_CONTENT=$(curl -s http://localhost:8080/ 2>/dev/null)
if echo "$OWI_CONTENT" | grep -q "<!doctype html>"; then
    echo "✅ OpenWebUI: Serving frontend (web interface available)"
elif echo "$OWI_CONTENT" | grep -q "Not Found"; then
    echo "⚠️  OpenWebUI: Serving API-only (frontend not loaded)"
    echo "   Run: docker restart lamb-openwebui"
    ERRORS=$((ERRORS + 1))
else
    echo "❌ OpenWebUI: Unexpected response"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "🔗 Checking inter-service communication..."

# Backend to OpenWebUI
if docker exec lamb-backend python -c "
import requests
import sys
try:
    r = requests.get('http://openwebui:8080/api/config', timeout=5)
    if r.status_code == 200:
        sys.exit(0)
    else:
        sys.exit(1)
except Exception:
    sys.exit(1)
" &>/dev/null; then
    echo "✅ Backend → OpenWebUI: OK"
else
    echo "❌ Backend → OpenWebUI: FAILED"
    ERRORS=$((ERRORS + 1))
fi

# Backend to KB Server
if docker exec lamb-backend python -c "
import requests
import sys
try:
    r = requests.get('http://kb:9090/health', timeout=5)
    if r.status_code == 200:
        sys.exit(0)
    else:
        sys.exit(1)
except Exception:
    sys.exit(1)
" &>/dev/null; then
    echo "✅ Backend → KB Server: OK"
else
    echo "❌ Backend → KB Server: FAILED"
    ERRORS=$((ERRORS + 1))
fi

# Check LAMB_PROJECT_PATH
echo ""
echo "🔧 Checking environment..."
if [ -z "$LAMB_PROJECT_PATH" ]; then
    echo "⚠️  LAMB_PROJECT_PATH not set"
    echo "   Run: export LAMB_PROJECT_PATH=$(pwd)"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ LAMB_PROJECT_PATH=$LAMB_PROJECT_PATH"
fi

# Summary
echo ""
echo "================================"
if [ $ERRORS -eq 0 ]; then
    echo "✅ All checks passed! LAMB is ready to use."
    echo ""
    echo "🎉 Access LAMB:"
    echo "   • Creator Interface: http://localhost:5173"
    echo "   • OpenWebUI Chat: http://localhost:8080"
    echo "   • Backend API: http://localhost:9099"
    echo "   • KB Server Docs: http://localhost:9090/docs"
    echo ""
    echo "🔐 Default login: admin@owi.com / admin"
    echo "   (Change these in production!)"
    echo ""
    exit 0
else
    echo "❌ $ERRORS check(s) failed. Please review the errors above."
    echo ""
    echo "Common fixes:"
    echo "  • OpenWebUI API-only: docker restart lamb-openwebui"
    echo "  • Container not running: docker-compose up -d"
    echo "  • Missing LAMB_PROJECT_PATH: export LAMB_PROJECT_PATH=\$(pwd)"
    echo ""
    echo "For detailed troubleshooting, see: fix_launch.md"
    exit 1
fi



