#!/bin/bash
# scripts/validate-env-examples.sh - Validate .env.example files for common errors

echo "🔍 Validating .env.example files..."
echo ""

ERRORS=0

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check KB server .env.example
echo "Checking: lamb-kb-server-stable/.env.example"
KB_ENV_FILE="$PROJECT_ROOT/lamb-kb-server-stable/.env.example"

if [ ! -f "$KB_ENV_FILE" ]; then
    echo "❌ ERROR: File not found: $KB_ENV_FILE"
    ERRORS=$((ERRORS + 1))
else
    # Check for typo: host.docker.internalt
    if grep -q "host\.docker\.internalt" "$KB_ENV_FILE"; then
        echo "❌ ERROR: Typo found in KB server .env.example"
        echo "   Found: host.docker.internalt (should be: host.docker.internal)"
        grep -n "host\.docker\.internalt" "$KB_ENV_FILE"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ No 'host.docker.internalt' typos found"
    fi
    
    # Check that it contains the correct version
    if grep -q "host\.docker\.internal" "$KB_ENV_FILE"; then
        echo "✅ Contains correct 'host.docker.internal'"
    else
        echo "⚠️  WARNING: No 'host.docker.internal' reference found (might be okay)"
    fi
fi

echo ""

# Check backend .env.example
echo "Checking: backend/.env.example"
BACKEND_ENV_FILE="$PROJECT_ROOT/backend/.env.example"

if [ ! -f "$BACKEND_ENV_FILE" ]; then
    echo "❌ ERROR: File not found: $BACKEND_ENV_FILE"
    ERRORS=$((ERRORS + 1))
else
    # Check for typo: host.docker.internalt
    if grep -q "host\.docker\.internalt" "$BACKEND_ENV_FILE"; then
        echo "❌ ERROR: Typo found in backend .env.example"
        echo "   Found: host.docker.internalt (should be: host.docker.internal)"
        grep -n "host\.docker\.internalt" "$BACKEND_ENV_FILE"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ No 'host.docker.internalt' typos found"
    fi
    
    # Check for required variables
    REQUIRED_VARS=("LAMB_WEB_HOST" "LAMB_BACKEND_HOST" "OWI_BASE_URL" "LAMB_DB_PATH")
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "^${var}=" "$BACKEND_ENV_FILE"; then
            echo "✅ Required variable present: $var"
        else
            echo "⚠️  WARNING: Required variable missing: $var"
        fi
    done
fi

echo ""

# Check for common mistakes
echo "Checking for common configuration mistakes..."

# Check if any .env files (not .example) are being committed
if git rev-parse --is-inside-work-tree &>/dev/null; then
    STAGED_ENV_FILES=$(git diff --cached --name-only | grep -E '\.env$' | grep -v '\.example$' || true)
    if [ -n "$STAGED_ENV_FILES" ]; then
        echo "⚠️  WARNING: .env files staged for commit (should be in .gitignore):"
        echo "$STAGED_ENV_FILES"
    else
        echo "✅ No .env files staged for commit"
    fi
fi

# Summary
echo ""
echo "================================"
if [ $ERRORS -eq 0 ]; then
    echo "✅ All .env.example files validated successfully"
    exit 0
else
    echo "❌ $ERRORS error(s) found in .env.example files"
    echo ""
    echo "Please fix the errors above before committing."
    exit 1
fi



