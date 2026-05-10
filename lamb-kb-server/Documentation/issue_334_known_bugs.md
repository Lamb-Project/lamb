# Known bugs in the new KB Server (#334)

Surfaced during the three-tier test suite (commit `fa532bfe`). Each bug had a regression-guard test that asserted current (incorrect) behavior; those tests have since been flipped to assert the correct behavior alongside the fix.

**Status:** all four issues fixed. This document is preserved as a record of what was wrong and how it was addressed — see the `fix(#334):` commits referenced in each section below.

| # | Bug | Fix commit |
|---|---|---|
| 1 | Latin-1 bearer-token bytes return 500 instead of 401 | `65a9cced` |
| 2 | `extra_metadata` accepts None / nested dicts but ChromaDB rejects them | `3b7eefbd` |
| 3 | `collection.chunk_count` race under concurrent ingestion | `4792f24c` |
| 4 | `chunking_params` silently ignores unknown keys | `434a6bcb` |

---

## 1. Latin-1 bearer-token bytes return 500 instead of 401

**Severity:** low
**Location:** `backend/dependencies.py` (bearer-auth dependency)

When the `Authorization: Bearer <token>` header contains bytes that are valid Latin-1 but not valid for `hmac.compare_digest`'s strict comparison, the comparison raises `TypeError` and FastAPI surfaces it as a 500 instead of the intended 401.

**Trigger:** non-ASCII characters in the bearer token. In production only LAMB sends tokens (controlled input), so this is unlikely to fire — but the wrong status code masks the real cause when it does.

**Fix sketch:** wrap `compare_digest` in a try/except, or normalize both sides to bytes via `.encode("utf-8", errors="replace")` before comparison and let mismatched bytes fall through the equality branch as a normal 401.

---

## 2. `extra_metadata` accepts None / nested dicts but ChromaDB rejects them

**Severity:** medium (bad UX, not data loss)
**Location:** `backend/schemas/` (ingestion request models) → `backend/plugins/vector_db/chromadb_backend.py`

The Pydantic schema declares `extra_metadata: dict[str, Any]`, which accepts `None`-valued keys and nested dicts. ChromaDB only accepts flat `dict[str, str | int | float | bool]`. The mismatch isn't caught until the chunker tries to persist, so the caller gets a confusing 500 from deep inside the pipeline instead of a 422 at the request boundary.

**Fix sketch:** narrow the schema type to `dict[str, str | int | float | bool]` and add a validator that rejects nested dicts and `None` values explicitly. Translate the early validation failure to a 422 with a clear message.

---

## 3. `collection.chunk_count` race under concurrent ingestion

**Severity:** medium — counter drifts, vectors stay correct
**Location:** `backend/services/ingestion_service.py` (chunk-count update path)

The counter update is a read-modify-write against the SQLite row without `SELECT … FOR UPDATE` or an atomic increment. Under concurrent ingestion jobs against the same collection, two workers can both read N, both compute N+k, both write N+k — losing one update's contribution. Vectors land in ChromaDB correctly; only the displayed `chunk_count` drifts low.

**Trigger:** two or more workers ingesting into the same collection at the same time. The 20-job concurrency e2e test exercises this path.

**Fix sketch:** replace the RMW with an atomic `UPDATE collections SET chunk_count = chunk_count + :delta WHERE id = :id` so SQLite serializes the increment. Optional: add a periodic reconciliation that recomputes `chunk_count` from the vector store as a self-heal.

**This is the bug most likely to be flagged in PR review.**

---

## 4. `chunking_params` silently ignores unknown keys

**Severity:** low
**Location:** `backend/plugins/chunking/` (each strategy's parameter handling)

Chunking strategies accept a `chunking_params` dict and read only the keys they recognize. A typo (e.g. `chunk_overlap_size` instead of `chunk_overlap`) or a key meant for a different strategy is silently dropped — the chunker runs with defaults and the caller has no signal that their configuration was ignored.

**Fix sketch:** each strategy declares its accepted parameter names; the entry point validates the incoming dict against that allow-list and 422s on unknown keys. Alternatively, log a warning per unknown key with the strategy name so callers can grep for misconfiguration.

---

## Suggested fix order

1. **#3 (chunk_count race)** — concurrency correctness, most visible to operators.
2. **#2 (extra_metadata schema)** — improves error messages for API consumers.
3. **#4 (silent chunking_params)** — prevents silent misconfiguration; cheap to fix.
4. **#1 (Latin-1 token)** — only matters once auth tokens are user-supplied; safe to defer.

Each can ship as a separate `fix(#<N>):` commit with the matching regression test flipped from "asserts buggy behavior" to "asserts correct behavior".
