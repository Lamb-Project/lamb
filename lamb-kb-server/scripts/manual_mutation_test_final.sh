#!/usr/bin/env bash
# Final two probes that the extended pass mis-named.
set -uo pipefail

cd "$(dirname "$0")/.."

RESULTS="mutation-results-final.txt"
: > "$RESULTS"

PYTEST="${PYTEST:-.venv/bin/pytest}"
RUNNER="$PYTEST tests/unit/test_services.py tests/integration/test_worker.py tests/integration/test_content_pipeline.py -x -q --no-header --tb=no -p no:cacheprovider"

apply_mutation() {
    local file="$1"
    local pattern="$2"
    local replacement="$3"
    local desc="$4"
    local id="$5"

    if ! grep -qF "$pattern" "$file"; then
        echo "[$id] ERROR: pattern not found" | tee -a "$RESULTS"
        return
    fi

    sed -i "s|$pattern|$replacement|" "$file"

    timeout 90 $RUNNER >/dev/null 2>&1
    local rc=$?

    git checkout -- "$file"

    if [ $rc -eq 0 ]; then
        echo "[$id] SURVIVED: $desc" | tee -a "$RESULTS"
    else
        echo "[$id] KILLED:   $desc — exit $rc" | tee -a "$RESULTS"
    fi
}

FILE_WORKER="backend/tasks/worker.py"

echo "=== Final probes — $(date) ===" | tee -a "$RESULTS"

apply_mutation "$FILE_WORKER" \
    "_POLL_INTERVAL = 2.0" \
    "_POLL_INTERVAL = 999.0" \
    "poll interval inflated to 999s" \
    "FINAL-1"

apply_mutation "$FILE_WORKER" \
    "if job.attempts >= _MAX_ATTEMPTS:" \
    "if job.attempts > _MAX_ATTEMPTS:" \
    "stale recovery boundary: >= → > (off-by-one)" \
    "FINAL-2"

echo | tee -a "$RESULTS"
echo "=== Final Summary ===" | tee -a "$RESULTS"
killed=$(grep -c "KILLED:" "$RESULTS")
survived=$(grep -c "SURVIVED:" "$RESULTS")
total=$((killed + survived))
echo "Killed:   $killed / $total"  | tee -a "$RESULTS"
echo "Survived: $survived"          | tee -a "$RESULTS"
