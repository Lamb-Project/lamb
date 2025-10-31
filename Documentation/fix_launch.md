# LAMB Launch Issues & Prevention Guide

**Document Version:** 1.0  
**Date:** October 17, 2025  
**Purpose:** Prevent common deployment issues when redistributing the LAMB project

---

## 🎯 Executive Summary

This document addresses critical issues discovered during fresh LAMB deployments and provides solutions to prevent them in future distributions. All issues are related to timing, configuration, and environment setup.

---

## 🐛 Issues Discovered

### Issue 1: KB Server Configuration Typo
**Severity:** Medium  
**Impact:** KB server fails to connect to Ollama for embeddings

**Problem:**
```bash
# In /lamb-kb-server-stable/backend/.env
EMBEDDINGS_ENDPOINT=http://host.docker.internalt:11434/api/embeddings
#                                          ^ typo here
```

**Root Cause:** Typographical error in `.env.example` template that propagates to user configurations.

**Solution:**
```bash
# Correct configuration
EMBEDDINGS_ENDPOINT=http://host.docker.internal:11434/api/embeddings
```

---

### Issue 2: Missing Frontend Configuration File
**Severity:** High  
**Impact:** Frontend fails to connect to backend services

**Problem:**
The `frontend/svelte-app/static/config.js` file is not automatically created from the sample template.

**Root Cause:** 
- `.gitignore` excludes `config.js` (correct for security)
- No automated setup step creates it from `config.js.sample`
- Users may not realize they need to manually copy the file

**Solution:**
Users must manually create the file:
```bash
cd frontend/svelte-app/static
cp config.js.sample config.js
```

---

### Issue 3: Missing LAMB_PROJECT_PATH Environment Variable
**Severity:** Critical  
**Impact:** Docker Compose cannot resolve volume mount paths

**Problem:**
`docker-compose.yaml` references `${LAMB_PROJECT_PATH}` but this variable is not set in the user's environment.

**Root Cause:**
- Documentation mentions setting it but doesn't emphasize its criticality
- No validation check before `docker-compose up`
- Variable not persisted across shell sessions

**Solution:**
```bash
export LAMB_PROJECT_PATH=/opt/lamb
# Or set to your actual installation path
```

---

### Issue 4: OpenWebUI Starts Before Build Completes
**Severity:** High  
**Impact:** OpenWebUI serves API-only mode, no web interface available

**Problem:**
The `docker-compose.yaml` has `depends_on: openwebui-build` but Docker Compose's `depends_on` only waits for container **start**, not **completion**.

**Timeline:**
1. `lamb-openwebui-build` container starts (~1s)
2. `lamb-openwebui` container starts immediately after (~2s)
3. OpenWebUI checks for `/opt/lamb/open-webui/build` directory
4. Directory not found → logs "Frontend build directory not found, serving API only"
5. Build completes 45 seconds later
6. OpenWebUI never re-checks for the directory

**Root Cause:**
Docker Compose `depends_on` does not support waiting for **task completion**, only container startup.

**Current Workaround:**
```bash
# After initial docker-compose up
docker restart lamb-openwebui
```

---

## ✅ Prevention Strategies for Distribution

### Strategy 1: Pre-Commit Validation Script

Create `.env.example` validation to catch typos:

```bash
#!/bin/bash
# scripts/validate-env-examples.sh

echo "Validating .env.example files..."

# Check KB server .env.example
if grep -q "host\.docker\.internalt" lamb-kb-server-stable/backend/.env.example; then
    echo "❌ ERROR: Typo found in KB server .env.example"
    echo "   Found: host.docker.internalt (should be: host.docker.internal)"
    exit 1
fi

# Check backend .env.example
if grep -q "host\.docker\.internalt" backend/.env.example; then
    echo "❌ ERROR: Typo found in backend .env.example"
    exit 1
fi

echo "✅ All .env.example files validated"
```

Add to `.git/hooks/pre-commit` or CI/CD pipeline.

---

### Strategy 2: Automated Setup Script

Create `scripts/setup.sh` to automate first-time setup:

```bash
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
if [ -f "$HOME/.bashrc" ]; then
    SHELL_PROFILE="$HOME/.bashrc"
elif [ -f "$HOME/.zshrc" ]; then
    SHELL_PROFILE="$HOME/.zshrc"
fi

if [ -n "$SHELL_PROFILE" ]; then
    if ! grep -q "LAMB_PROJECT_PATH" "$SHELL_PROFILE"; then
        echo "" >> "$SHELL_PROFILE"
        echo "# LAMB Project Path" >> "$SHELL_PROFILE"
        echo "export LAMB_PROJECT_PATH=\"$PROJECT_ROOT\"" >> "$SHELL_PROFILE"
        echo "✅ Added LAMB_PROJECT_PATH to $SHELL_PROFILE"
        echo "   Run: source $SHELL_PROFILE"
    fi
fi

# 7. Summary
echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Edit backend/.env and add your OpenAI API key (or other LLM keys)"
echo "   2. Run: export LAMB_PROJECT_PATH=\"$PROJECT_ROOT\""
echo "   3. Run: docker-compose up -d"
echo "   4. Wait 2-3 minutes for builds to complete"
echo "   5. Run: docker restart lamb-openwebui"
echo "   6. Access LAMB at http://localhost:5173"
echo ""
```

---

### Strategy 3: Improved docker-compose.yaml with Health Checks

Add health checks and proper build wait conditions:

```yaml
services:
  openwebui-build:
    image: node:20-alpine
    container_name: lamb-openwebui-build
    working_dir: ${LAMB_PROJECT_PATH}/open-webui
    volumes:
      - ${LAMB_PROJECT_PATH}:${LAMB_PROJECT_PATH}
    environment:
      - NODE_OPTIONS=--max-old-space-size=4096
    command: >
      sh -lc "if [ ! -d ${LAMB_PROJECT_PATH}/open-webui/build ] || [ -z \"$(ls -A ${LAMB_PROJECT_PATH}/open-webui/build 2>/dev/null)\" ]; then 
        npm install && npm run build && touch /tmp/build-complete; 
      else 
        echo 'Build folder already exists, skipping build.' && touch /tmp/build-complete; 
      fi"
    healthcheck:
      test: ["CMD", "test", "-f", "/tmp/build-complete"]
      interval: 5s
      timeout: 3s
      retries: 60
      start_period: 10s

  openwebui:
    image: python:3.11-slim
    container_name: lamb-openwebui
    depends_on:
      openwebui-build:
        condition: service_healthy  # Wait for build to complete!
    # ... rest of config
```

**Note:** This requires Docker Compose v2.20+ for `condition: service_healthy` support.

---

### Strategy 4: Post-Launch Validation Script

Create `scripts/verify-deployment.sh`:

```bash
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
    else
        echo "❌ $NAME: FAILED (got $HTTP_CODE, expected $EXPECTED_CODE)"
        ERRORS=$((ERRORS + 1))
    fi
}

# Check containers
echo "📦 Checking containers..."
CONTAINERS=$(docker ps --filter "name=lamb-" --format "{{.Names}}" | grep -v build)
for container in $CONTAINERS; do
    STATUS=$(docker inspect -f '{{.State.Status}}' "$container")
    if [ "$STATUS" = "running" ]; then
        echo "✅ $container: running"
    else
        echo "❌ $container: $STATUS"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
echo "🌐 Checking endpoints..."
check_endpoint "Frontend" "http://localhost:5173/" 200
check_endpoint "Backend" "http://localhost:9099/status" 200
check_endpoint "OpenWebUI" "http://localhost:8080/" 200
check_endpoint "KB Server Health" "http://localhost:9090/health" 200

echo ""
echo "🔗 Checking inter-service communication..."
docker exec lamb-backend python -c "
import requests
import sys
try:
    r = requests.get('http://openwebui:8080/api/config', timeout=5)
    print('✅ Backend → OpenWebUI: OK')
    sys.exit(0)
except Exception as e:
    print(f'❌ Backend → OpenWebUI: FAILED - {e}')
    sys.exit(1)
" || ERRORS=$((ERRORS + 1))

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "✅ All checks passed! LAMB is ready to use."
    echo ""
    echo "🎉 Access LAMB:"
    echo "   • Creator Interface: http://localhost:5173"
    echo "   • OpenWebUI Chat: http://localhost:8080"
    echo "   • Default login: admin@owi.com / admin"
    exit 0
else
    echo "❌ $ERRORS check(s) failed. Please review the errors above."
    exit 1
fi
```

---

### Strategy 5: Enhanced Documentation

Update README.md with prominent quick-start section:

```markdown
## 🚀 Quick Start (First-Time Setup)

### Automated Setup (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/Lamb-Project/lamb.git
cd lamb

# 2. Run automated setup
./scripts/setup.sh

# 3. Edit configuration files
nano backend/.env  # Add your OpenAI API key

# 4. Launch LAMB
export LAMB_PROJECT_PATH=$(pwd)
docker-compose up -d

# 5. Wait for builds (2-3 minutes)
# Watch progress with: docker logs lamb-openwebui-build -f

# 6. Restart OpenWebUI after build completes
docker restart lamb-openwebui

# 7. Verify deployment
./scripts/verify-deployment.sh

# 8. Access LAMB
open http://localhost:5173
```

### Manual Setup

If you prefer manual setup, follow these steps carefully:

**Step 1: Create .env files**
```bash
cp backend/.env.example backend/.env
cp lamb-kb-server-stable/backend/.env.example lamb-kb-server-stable/backend/.env
```

**Step 2: Create frontend config**
```bash
cp frontend/svelte-app/static/config.js.sample frontend/svelte-app/static/config.js
```

**Step 3: Validate configuration**
```bash
# Check for common typos in KB server .env
grep "host.docker.internal" lamb-kb-server-stable/backend/.env
# Should show: EMBEDDINGS_ENDPOINT=http://host.docker.internal:11434/api/embeddings
```

**Step 4: Set environment variable**
```bash
export LAMB_PROJECT_PATH=$(pwd)
# Add to ~/.bashrc or ~/.zshrc for persistence
```

**Step 5: Launch services**
```bash
docker-compose up -d
```

**Step 6: Wait and verify**
```bash
# Wait 2-3 minutes for builds
# Then restart OpenWebUI
docker restart lamb-openwebui
```
```

---

## 📋 Pre-Distribution Checklist

Before releasing a new version of LAMB, verify:

- [ ] All `.env.example` files validated for typos
- [ ] `config.js.sample` contains correct development URLs
- [ ] `setup.sh` script tested on fresh clone
- [ ] `verify-deployment.sh` script passes on clean deployment
- [ ] README.md Quick Start section updated
- [ ] Documentation mentions LAMB_PROJECT_PATH requirement prominently
- [ ] GitHub issue template includes deployment verification steps
- [ ] CI/CD pipeline includes `.env.example` validation

---

## 🔧 Maintenance Commands

### If OpenWebUI doesn't show frontend
```bash
# Check if build exists
ls -la /opt/lamb/open-webui/build/

# If exists, restart container
docker restart lamb-openwebui

# If not, rebuild
docker-compose up -d openwebui-build
sleep 60  # Wait for build
docker restart lamb-openwebui
```

### If KB server connection fails
```bash
# Check configuration
grep EMBEDDINGS_ENDPOINT lamb-kb-server-stable/backend/.env

# Test connectivity
docker exec lamb-kb-server python -c "import requests; print(requests.get('http://localhost:9090/health').json())"
```

### Complete reset
```bash
# Stop all services
docker-compose down

# Remove build artifacts (optional)
rm -rf open-webui/build
rm -rf frontend/svelte-app/build

# Restart
export LAMB_PROJECT_PATH=$(pwd)
docker-compose up -d
sleep 120  # Wait for builds
docker restart lamb-openwebui
```

---

## 🎯 Future Improvements

### Short-term (v1.1)
1. Add `scripts/setup.sh` to repository
2. Add `scripts/verify-deployment.sh` to repository
3. Update README.md with prominent setup warnings
4. Add pre-commit hook for `.env.example` validation

### Medium-term (v1.2)
1. Implement health checks in `docker-compose.yaml`
2. Create interactive setup wizard
3. Add startup dependency logic to wait for builds
4. Automated post-deployment verification

### Long-term (v2.0)
1. Single-binary installer with embedded validation
2. Web-based setup wizard
3. Automatic configuration repair on startup
4. Built-in deployment health dashboard

---

## 📚 Related Documentation

- [LAMB Architecture](Documentation/lamb_architecture.md)
- [Product Requirements](Documentation/prd.md)
- [Deployment Guide](Documentation/deployment.md)
- [Installation Guide](Documentation/installationguide.md)

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-17 | Initial document creation based on real deployment issues |

---

**Document Maintainer:** LAMB Development Team  
**Last Verified:** October 17, 2025  
**Status:** Active

