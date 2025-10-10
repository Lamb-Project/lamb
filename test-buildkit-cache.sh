#!/bin/bash

# Test script to demonstrate Docker BuildKit cache functionality
# This script builds a Dockerfile twice to show cache benefits

set -e

echo "=========================================="
echo "Docker BuildKit Cache Test"
echo "=========================================="
echo ""

# Check if Docker and BuildKit are available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

echo "✓ Docker version: $(docker --version)"
echo "✓ BuildKit version: $(docker buildx version 2>/dev/null || echo 'N/A')"
echo ""

# Select a simple Dockerfile to test
DOCKERFILE_PATH="lamb-kb-server-stable/Dockerfile.server"
CONTEXT_PATH="lamb-kb-server-stable"

if [ ! -f "$DOCKERFILE_PATH" ]; then
    echo "Error: Dockerfile not found at $DOCKERFILE_PATH"
    exit 1
fi

echo "Testing with: $DOCKERFILE_PATH"
echo ""

# Enable BuildKit
export DOCKER_BUILDKIT=1

echo "=========================================="
echo "First build (cold cache)"
echo "=========================================="
echo ""

# First build - should download packages
time docker build \
    -f "$DOCKERFILE_PATH" \
    -t test-buildkit-cache:v1 \
    --progress=plain \
    "$CONTEXT_PATH" 2>&1 | grep -E "(Downloading|Installing|CACHED|cache|mount)" || true

echo ""
echo "=========================================="
echo "Second build (warm cache)"
echo "=========================================="
echo "Note: Dependencies should use cache now"
echo ""

# Modify build args or add a comment to force rebuild without cache invalidation
time docker build \
    -f "$DOCKERFILE_PATH" \
    -t test-buildkit-cache:v2 \
    --progress=plain \
    "$CONTEXT_PATH" 2>&1 | grep -E "(Downloading|Installing|CACHED|cache|mount)" || true

echo ""
echo "=========================================="
echo "Cache verification"
echo "=========================================="
echo ""

# Check cache usage
if command -v docker &> /dev/null && docker buildx version &> /dev/null 2>&1; then
    echo "Build cache usage:"
    docker buildx du | head -20 || echo "Could not retrieve cache usage"
else
    echo "BuildKit not available for cache inspection"
fi

echo ""
echo "=========================================="
echo "Test complete!"
echo "=========================================="
echo ""
echo "The second build should be faster due to cached pip downloads."
echo "BuildKit cache mounts preserve downloaded packages between builds."
echo ""
