#!/bin/bash
# scripts/setup.sh - First-time LAMB setup automation

set -e  # Exit on error

echo "🚀 LAMB Setup Script"
echo "===================="
echo ""

# 1. Detect project path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
echo "📁 Detected project root: $PROJECT_ROOT"

# 2. Check for .env files
echo ""
echo "🔍 Checking environment files..."

if [ ! -f "$PROJECT_ROOT/backend/.env" ]; then
    echo "⚠️  Backend .env not found. Creating from example..."
    cp "$PROJECT_ROOT/backend/.env.example" "$PROJECT_ROOT/backend/.env"
    echo "✅ Created backend/.env"
    echo "⚠️  IMPORTANT: Edit backend/.env and add your API keys!"
else
    echo "✅ backend/.env exists"
fi

if [ ! -f "$PROJECT_ROOT/lamb-kb-server-stable/backend/.env" ]; then
    echo "⚠️  KB server .env not found. Creating from example..."
    cp "$PROJECT_ROOT/lamb-kb-server-stable/backend/.env.example" \
       "$PROJECT_ROOT/lamb-kb-server-stable/backend/.env"
    echo "✅ Created lamb-kb-server-stable/backend/.env"
else
    echo "✅ KB server .env exists"
fi

# Root .env — required by docker-compose.next.yaml
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "⚠️  Root .env not found. Creating from .env.next.example..."
    cp "$PROJECT_ROOT/.env.next.example" "$PROJECT_ROOT/.env"
    echo "✅ Created .env"
    echo "⚠️  IMPORTANT: edit .env and set your secrets/API keys!"
else
    echo "✅ Root .env exists"
fi

# 3. Validate .env files for common typos
echo ""
echo "🔍 Validating .env files for common issues..."

if grep -q "host\.docker\.internalt" "$PROJECT_ROOT/lamb-kb-server-stable/backend/.env" 2>/dev/null; then
    echo "⚠️  Found typo in KB server .env: 'host.docker.internalt'"
    echo "   Fixing automatically..."
    sed -i.bak 's/host\.docker\.internalt/host.docker.internal/g' \
        "$PROJECT_ROOT/lamb-kb-server-stable/backend/.env"
    echo "✅ Fixed: host.docker.internal"
fi

if grep -q "host\.docker\.internalt" "$PROJECT_ROOT/backend/.env" 2>/dev/null; then
    echo "⚠️  Found typo in backend .env: 'host.docker.internalt'"
    echo "   Fixing automatically..."
    sed -i.bak 's/host\.docker\.internalt/host.docker.internal/g' \
        "$PROJECT_ROOT/backend/.env"
    echo "✅ Fixed: host.docker.internal"
fi

# 4. Create frontend config.js
echo ""
echo "🔍 Checking frontend configuration..."

if [ ! -f "$PROJECT_ROOT/frontend/svelte-app/static/config.js" ]; then
    echo "⚠️  Frontend config.js not found. Creating from sample..."
    cp "$PROJECT_ROOT/frontend/svelte-app/static/config.js.sample" \
       "$PROJECT_ROOT/frontend/svelte-app/static/config.js"
    echo "✅ Created frontend/svelte-app/static/config.js"
else
    echo "✅ frontend config.js exists"
fi

# 5. Set LAMB_PROJECT_PATH
echo ""
echo "🔧 Setting LAMB_PROJECT_PATH..."
export LAMB_PROJECT_PATH="$PROJECT_ROOT"
echo "✅ LAMB_PROJECT_PATH=$LAMB_PROJECT_PATH"

# 6. Add to shell profile for persistence
SHELL_PROFILE=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_PROFILE="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_PROFILE="$HOME/.bashrc"
fi

if [ -n "$SHELL_PROFILE" ]; then
    if ! grep -q "LAMB_PROJECT_PATH" "$SHELL_PROFILE"; then
        echo "" >> "$SHELL_PROFILE"
        echo "# LAMB Project Path" >> "$SHELL_PROFILE"
        echo "export LAMB_PROJECT_PATH=\"$PROJECT_ROOT\"" >> "$SHELL_PROFILE"
        echo "✅ Added LAMB_PROJECT_PATH to $SHELL_PROFILE"
        echo "   Run: source $SHELL_PROFILE"
    else
        echo "✅ LAMB_PROJECT_PATH already in $SHELL_PROFILE"
    fi
fi

# 7. Check Docker
echo ""
echo "🐳 Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon not running. Please start Docker."
    exit 1
fi

echo "✅ Docker is ready"

# 8. Summary
echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Edit .env and set your secrets/API keys"
echo "      nano $PROJECT_ROOT/.env"
echo ""
echo "   2. Launch LAMB services:"
echo "      cd $PROJECT_ROOT"
echo "      docker compose -f docker-compose.next.yaml up -d"
echo ""
echo "      Add local Ollama inference with:  --profile ollama"
echo "      On a GPU host also add:           -f docker-compose.next.gpu.yaml"
echo ""
echo "   3. Verify deployment:"
echo "      $PROJECT_ROOT/scripts/verify-deployment.sh"
echo ""
echo "   4. Access LAMB at http://localhost:9099"
echo "      Default login: admin@owi.com / admin"
echo ""



