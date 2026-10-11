#!/usr/bin/env bash
# Run each suite in a separate process; retain every result even after a failure.
set -uo pipefail
result_dir="${1:-/tmp/lamb-scanner-results}"
mkdir -p "$result_dir"
status=0
run_suite() {
    local name="$1" directory="$2"
    shift 2
    if (cd "$directory" && timeout 300 "$@") > "$result_dir/$name.log" 2>&1; then
        printf '%s PASS\n' "$name"
    else
        local code=$?
        printf '%s FAIL (exit %s; %s)\n' "$name" "$code" "$result_dir/$name.log"
        status=1
    fi
    tail -n 5 "$result_dir/$name.log"
}
run_suite backend /src/backend /opt/venvs/backend/bin/python -m pytest tests -q
run_suite cli /src/lamb-cli /opt/venvs/backend/bin/python -m pytest tests -q
run_suite frontend /src/frontend/svelte-app npm run test:unit -- --run
run_suite library /src/library-manager /opt/venvs/library/bin/python -m pytest tests -q
run_suite kb /src/lamb-kb-server-stable/backend /opt/venvs/kb/bin/python -m pytest \
    tests/test_collection_updates.py tests/test_embeddings_key_rotation.py \
    tests/test_query_discovery.py tests/test_static_file_display.py -q
exit "$status"
