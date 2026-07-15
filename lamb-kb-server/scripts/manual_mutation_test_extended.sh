#!/usr/bin/env bash
# Extended manual mutation testing — sneakier mutations that are more
# likely to survive. Combined with manual_mutation_test.sh's 17 critical
# mutations to gauge overall test sensitivity.
set -uo pipefail

cd "$(dirname "$0")/.."

RESULTS="mutation-results-extended.txt"
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
        echo "[$id] ERROR: pattern not found in $file" | tee -a "$RESULTS"
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

FILE_INGEST="backend/services/ingestion_service.py"
FILE_WORKER="backend/tasks/worker.py"

echo "=== Extended mutation testing — $(date) ===" | tee -a "$RESULTS"

# Sneakier — boundary conditions, off-by-one, equivalent-looking changes.
apply_mutation "$FILE_INGEST" \
    "_COMMIT_BATCH_SIZE = 5" \
    "_COMMIT_BATCH_SIZE = 4" \
    "batch size off-by-one (5 → 4)" \
    "EXT-1"

apply_mutation "$FILE_INGEST" \
    "_COMMIT_BATCH_SIZE = 5" \
    "_COMMIT_BATCH_SIZE = 6" \
    "batch size off-by-one (5 → 6)" \
    "EXT-2"

apply_mutation "$FILE_INGEST" \
    "_COMMIT_BATCH_SIZE = 5" \
    "_COMMIT_BATCH_SIZE = 1" \
    "batch size = 1 (commits every doc)" \
    "EXT-3"

apply_mutation "$FILE_INGEST" \
    "if deleted_count > 0:" \
    "if deleted_count > 1:" \
    "delete_vectors: counter update only when >=2 deleted" \
    "EXT-4"

apply_mutation "$FILE_INGEST" \
    "(Collection.document_count - 1 < 0, 0)," \
    "(Collection.document_count - 1 < 0, 1)," \
    "delete_vectors: document_count clamp returns 1 instead of 0 (atomic)" \
    "EXT-5"

apply_mutation "$FILE_INGEST" \
    "documents_processed=0," \
    "documents_processed=1," \
    "queue_add_content: documents_processed starts at 1" \
    "EXT-6"

apply_mutation "$FILE_INGEST" \
    "chunks_created=0," \
    "chunks_created=1," \
    "queue_add_content: chunks_created starts at 1" \
    "EXT-7"

apply_mutation "$FILE_INGEST" \
    'status="pending",' \
    'status="processing",' \
    "queue_add_content: initial status processing not pending" \
    "EXT-8"

apply_mutation "$FILE_INGEST" \
    "if chunks:" \
    "if not chunks:" \
    "execute: skip add_chunks when chunks present (negated)" \
    "EXT-9"

apply_mutation "$FILE_INGEST" \
    "n_stored = 0" \
    "n_stored = 1" \
    "execute: n_stored defaults to 1 instead of 0" \
    "EXT-10"

# worker.py
apply_mutation "$FILE_WORKER" \
    "_MAX_ATTEMPTS = " \
    "_MAX_ATTEMPTS = 99 #" \
    "stale-recovery max-attempts inflated" \
    "EXT-11"

apply_mutation "$FILE_WORKER" \
    "_POLL_INTERVAL_SECONDS = " \
    "_POLL_INTERVAL_SECONDS = 999 #" \
    "poll interval inflated to 999s" \
    "EXT-12"

apply_mutation "$FILE_WORKER" \
    "_dispatched.add" \
    "_dispatched.discard" \
    "dispatched-set add → discard (no dedup)" \
    "EXT-13"

apply_mutation "$FILE_WORKER" \
    "_dispatched.discard" \
    "_dispatched.add" \
    "dispatched-set discard → add (never clears)" \
    "EXT-14"

apply_mutation "$FILE_WORKER" \
    "if attempts >= _MAX_ATTEMPTS:" \
    "if attempts > _MAX_ATTEMPTS:" \
    "stale recovery: > instead of >= (off-by-one)" \
    "EXT-15"

echo | tee -a "$RESULTS"
echo "=== Extended Summary ===" | tee -a "$RESULTS"
killed=$(grep -c "KILLED:" "$RESULTS")
survived=$(grep -c "SURVIVED:" "$RESULTS")
errored=$(grep -c "ERROR:" "$RESULTS")
total=$((killed + survived))
echo "Total: $total (+ $errored errors)" | tee -a "$RESULTS"
echo "Killed:    $killed" | tee -a "$RESULTS"
echo "Survived:  $survived" | tee -a "$RESULTS"
if [ $total -gt 0 ]; then
    score=$(echo "scale=1; $killed * 100 / $total" | bc)
    echo "Score:     $score%" | tee -a "$RESULTS"
fi
