# Document RAG Cache Impact Test

Measures the latency impact of the in-memory TTL cache for document RAG (Library Manager responses). Compares two runs: one with cache disabled, one with cache enabled.

## Prerequisites

1. Backend running with `DOCUMENT_RAG_CACHE_ENABLED` and `DOCUMENT_RAG_CACHE_TTL_SECONDS` configured in `backend/.env`
2. An assistant with `single_file_rag` as `document_rag`, pointing to a Library document
3. Python dependencies: `pip install -r requirements.txt`

## Workflow

### Run 1: Without cache

1. Set `DOCUMENT_RAG_CACHE_ENABLED=false` in `backend/.env`
2. Recreate backend container: `docker compose up -d backend` (restart is NOT sufficient for .env changes)
3. Run simulation:
```bash
python cache_test_simulation.py --label no_cache
```

### Run 2: With cache

1. Set `DOCUMENT_RAG_CACHE_ENABLED=true` in `backend/.env`
2. Recreate backend container: `docker compose up -d backend`
3. Run simulation:
```bash
python cache_test_simulation.py --label with_cache
```

### Analyze

```bash
python analyze_cache_impact.py results/no_cache_*/  results/with_cache_*/
```

Generates:
- `cache_comparison.png` — box plot comparing total latency and doc RAG latency
- `comparison.json` — side-by-side summary with deltas

## What gets measured

| Metric | Source |
|--------|--------|
| `total_time_ms` | End-to-end request latency (client-side) |
| `doc_rag_time_ms` | Time spent fetching document (from `X-Doc-RAG-Time-Ms` header) |
| `doc_rag_cache` | Cache status: `hit`, `miss`, or `skip` (from `X-Doc-RAG-Cache` header) |

## Interpreting results

The **primary metric** is `doc_rag_time_ms` — this directly measures the cache impact. The `total_time_ms` boxplot is included for context but may show small differences because LLM inference time (~30-60s) dominates total latency, while doc fetch is typically 50-500ms.

**Cold start behavior:** On the first few requests with cache enabled, multiple concurrent students may all experience cache misses before the first `set()` completes (the lock protects the dict but not the full get→fetch→set sequence). The hit rate will be low initially and increase as the cache warms. This is expected and does not invalidate the benchmark.

### Expected results

- **No cache run**: Every request fetches from Library Manager → `doc_rag_time_ms` ~50-500ms, all `miss`
- **With cache run**: First requests are `miss`, then `hit` rate increases → `doc_rag_time_ms` <1ms for hits
- **Total time**: May show small improvement; the real win is in doc RAG time

## Known limitations

- **In-memory per process:** cache is not shared across multiple backend workers/replicas. Each process has its own cache. For multi-instance deployments, a distributed cache (Redis/Memcached) would be needed.
- **No invalidation on document edit:** cache entries expire only via TTL (default 5 min). If a document is edited in the Library Manager, the old version is served until TTL expires.
- **Synchronous httpx.get:** the Library Manager call is synchronous within the async pipeline. The cache mitigates this by avoiding the call on hits, but a full fix would require async httpx.
- **deepcopy on each access:** `get()` and `set()` use `copy.deepcopy()` to prevent mutation of cached entries. With large documents (~16k tokens), this adds CPU overhead per hit. Acceptable for the classroom scenario; for very large documents (>50MB), a shallow-copy + immutability approach would be needed.
- **Config immutable at runtime:** `_CACHE_ENABLED` and `_CACHE_TTL` are read from `config.py` at module import time. Changing env vars requires a backend recreate to take effect. Tests bypass this by patching module-level variables directly.
- **Headers only on run_lamb_assistant:** timing headers (`X-Doc-RAG-*`) are only emitted by the `/creator/assistant/{id}/chat/completions` endpoint. Direct calls to `/lamb/v1/chat/completions` (`create_completion`) do not include these headers.
- **Proxy loses headers with persist_chat=true:** the test uses `persist_chat: false`. If changed to `true`, the proxy in `learning_assistant_proxy.py` reconstructs the Response without copying original headers, so timing headers would be lost.
