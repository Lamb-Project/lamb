#!/usr/bin/env bash
# Run all three test tiers and gate on combined coverage.
#
# Per-tier requirement: every test must pass (no per-tier coverage gate
# because the e2e tier launches a subprocess that pytest-cov cannot
# instrument reliably from the parent process — see plan §3 "Risks").
#
# Combined-tier requirement: line + branch coverage on backend/ >= 95%.
# When all three tiers run together, the in-process unit and integration
# tests cover everything that's reachable; the e2e tier proves the same
# code paths work over real HTTP, real Ollama, and real Qdrant containers.
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p htmlcov
rm -f .coverage* htmlcov/index.html

echo "==> Tier 1: unit"
pytest tests/unit/ -q --no-header

echo "==> Tier 2: integration"
pytest tests/integration/ -q --no-header

echo "==> Tier 3: e2e"
pytest tests/e2e/ -q --no-header

echo "==> Combined coverage gate (>=95%)"
pytest tests/unit/ tests/integration/ tests/e2e/ \
    --cov=backend --cov-branch \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-fail-under=95 \
    -q --no-header

echo "All tiers passed; combined coverage >= 95%."
