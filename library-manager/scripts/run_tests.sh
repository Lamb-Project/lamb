#!/usr/bin/env bash
#
# Library Manager test runner.
#
# Runs the three tiers separately (each must pass on its own), then a combined
# coverage-gated run over the in-process tiers (unit + integration). The e2e
# tier is a behavioural signal, not a coverage number: its work happens in a
# uvicorn subprocess / Docker container that the parent pytest-cov cannot
# instrument.
#
# Usage:
#   ./scripts/run_tests.sh            # all tiers + 95% combined gate
#   ./scripts/run_tests.sh fast       # skip slow tests (no subprocess/Docker)
#
set -euo pipefail

cd "$(dirname "$0")/.."

PYTEST="${PYTEST:-python -m pytest}"
COV_MIN="${COV_MIN:-95}"

if [[ "${1:-}" == "fast" ]]; then
    echo "== Fast run (skipping slow / e2e) =="
    $PYTEST tests/unit/ tests/integration/ -m "not slow" -q \
        --cov=backend --cov-branch --cov-report=term-missing
    exit 0
fi

echo "== Tier 1: unit =="
$PYTEST tests/unit/ -q

echo "== Tier 2: integration =="
$PYTEST tests/integration/ -q

echo "== Tier 3: e2e =="
$PYTEST tests/e2e/ -q

echo "== Combined coverage gate (unit + integration, fail-under ${COV_MIN}%) =="
$PYTEST tests/unit/ tests/integration/ \
    --cov=backend --cov-branch \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-fail-under="${COV_MIN}" \
    -q --no-header

echo "All tiers passed and coverage gate (>=${COV_MIN}%) satisfied."
