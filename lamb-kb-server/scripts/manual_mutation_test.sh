#!/usr/bin/env bash
# Manual mutation testing — apply targeted mutations to backend/ source,
# run the test subset, observe whether the suite catches each mutation,
# then revert via git checkout. Records results to mutation-results.txt.
#
# Mutmut3 auto-discovery doesn't link our class-based tests to mutated
# lines, so this script does targeted mutation testing by hand on a
# curated set of high-impact mutations rather than the full mutant
# space.
set -uo pipefail

cd "$(dirname "$0")/.."

RESULTS="mutation-results.txt"
: > "$RESULTS"

# Test runner: unit + worker + content_pipeline. -x stops on first failure
# so killed mutants exit fast.
RUNNER="pytest tests/unit/test_services.py tests/integration/test_worker.py tests/integration/test_content_pipeline.py -x -q --no-header --tb=no -p no:cacheprovider"

apply_mutation() {
    local file="$1"
    local pattern="$2"
    local replacement="$3"
    local desc="$4"
    local id="$5"

    # Apply via sed.
    if ! grep -qF "$pattern" "$file"; then
        echo "[$id] ERROR: pattern not found in $file: $pattern" | tee -a "$RESULTS"
        return
    fi

    sed -i "s|$pattern|$replacement|" "$file"

    # Run tests with timeout.
    timeout 90 $RUNNER >/dev/null 2>&1
    local rc=$?

    # Revert.
    git checkout -- "$file"

    if [ $rc -eq 0 ]; then
        echo "[$id] SURVIVED: $desc — tests passed despite mutation" | tee -a "$RESULTS"
    else
        echo "[$id] KILLED:   $desc — exit $rc" | tee -a "$RESULTS"
    fi
}

FILE_INGEST="backend/services/ingestion_service.py"
FILE_WORKER="backend/tasks/worker.py"

echo "=== Manual mutation testing — $(date) ===" | tee -a "$RESULTS"
echo "Source files: $FILE_INGEST + $FILE_WORKER" | tee -a "$RESULTS"
echo | tee -a "$RESULTS"

# ----- ingestion_service.py mutations -----
apply_mutation "$FILE_INGEST" \
    "if collection is None:" \
    "if collection is not None:" \
    "queue_add_content: negate collection-not-found guard" \
    "INGEST-1"

apply_mutation "$FILE_INGEST" \
    "if not req.documents:" \
    "if req.documents:" \
    "queue_add_content: negate empty-documents guard" \
    "INGEST-2"

apply_mutation "$FILE_INGEST" \
    "documents_total=len(req.documents)," \
    "documents_total=0," \
    "queue_add_content: documents_total reports 0" \
    "INGEST-3"

apply_mutation "$FILE_INGEST" \
    "attempts=0," \
    "attempts=1," \
    "queue_add_content: initial attempts off-by-one" \
    "INGEST-4"

apply_mutation "$FILE_INGEST" \
    "if strategy is None:" \
    "if strategy is not None:" \
    "execute_ingestion_job: negate strategy-missing guard" \
    "INGEST-5"

apply_mutation "$FILE_INGEST" \
    "if backend is None:" \
    "if backend is not None:" \
    "execute/delete: negate backend-missing guard (first occurrence)" \
    "INGEST-6"

apply_mutation "$FILE_INGEST" \
    "job.documents_processed += 1" \
    "job.documents_processed += 0" \
    "execute_ingestion_job: documents_processed never advances" \
    "INGEST-7"

apply_mutation "$FILE_INGEST" \
    "job.chunks_created += n_stored" \
    "job.chunks_created -= n_stored" \
    "execute_ingestion_job: chunks_created decremented instead of incremented" \
    "INGEST-8"

apply_mutation "$FILE_INGEST" \
    "if (i + 1) % _COMMIT_BATCH_SIZE == 0:" \
    "if (i + 1) % _COMMIT_BATCH_SIZE != 0:" \
    "execute_ingestion_job: commits inverted (always commits except batch boundary)" \
    "INGEST-9"

apply_mutation "$FILE_INGEST" \
    "collection.document_count = (collection.document_count or 0) + len(docs_list)" \
    "collection.document_count = (collection.document_count or 0) - len(docs_list)" \
    "execute_ingestion_job: document_count decremented" \
    "INGEST-10"

apply_mutation "$FILE_INGEST" \
    "collection.chunk_count = (collection.chunk_count or 0) + total_chunks_added" \
    "collection.chunk_count = (collection.chunk_count or 0) - total_chunks_added" \
    "execute_ingestion_job: chunk_count decremented" \
    "INGEST-11"

apply_mutation "$FILE_INGEST" \
    "if deleted_count > 0:" \
    "if deleted_count >= 0:" \
    "delete_vectors: counter-update guard widened" \
    "INGEST-12"

apply_mutation "$FILE_INGEST" \
    "max(0, (collection.chunk_count or 0) - deleted_count)" \
    "min(0, (collection.chunk_count or 0) - deleted_count)" \
    "delete_vectors: chunk_count clamp inverted (max → min)" \
    "INGEST-13"

apply_mutation "$FILE_INGEST" \
    "max(0, (collection.document_count or 0) - 1)" \
    "max(0, (collection.document_count or 0) - 0)" \
    "delete_vectors: document_count never decrements" \
    "INGEST-14"

# ----- worker.py mutations (high-impact only) -----
apply_mutation "$FILE_WORKER" \
    'job.status = "completed"' \
    'job.status = "failed"' \
    "_process_job_sync: success path marks failed" \
    "WORKER-1"

apply_mutation "$FILE_WORKER" \
    'job.status = "failed"' \
    'job.status = "completed"' \
    "_process_job_sync: failure path marks completed" \
    "WORKER-2"

apply_mutation "$FILE_WORKER" \
    "job.attempts += 1" \
    "job.attempts -= 1" \
    "stale recovery: attempts decremented instead of incremented" \
    "WORKER-3"

echo | tee -a "$RESULTS"
echo "=== Summary ===" | tee -a "$RESULTS"
killed=$(grep -c "KILLED:" "$RESULTS")
survived=$(grep -c "SURVIVED:" "$RESULTS")
errored=$(grep -c "ERROR:" "$RESULTS")
total=$((killed + survived))
echo "Total mutations: $total (+ $errored errors)" | tee -a "$RESULTS"
echo "Killed:    $killed" | tee -a "$RESULTS"
echo "Survived:  $survived" | tee -a "$RESULTS"
if [ $total -gt 0 ]; then
    score=$(echo "scale=1; $killed * 100 / $total" | bc)
    echo "Score:     $score%" | tee -a "$RESULTS"
fi
