# MVP: Assistant-Level Token Quota Enforcement

**Date:** March 12, 2026  
**Status:** Plan / Pre-implementation

---

## Goal

Estimate token usage per assistant well enough to block an assistant after it crosses a configured cost threshold. Track usage in dollars so operators can establish per-assistant spend limits.

### Design biases

- **Assistant-level aggregation**, not per-user accuracy
- Check threshold **before** each completion
- Store raw per-request estimates so aggregates can be recomputed later
- Separate pricing table per LLM model
- **Ollama connectors are free** — skip tracking and quota checks entirely

---

## Key observations from the code

- **Non-streaming** (`stream=False`): `openai.py` already returns `response.model_dump()` which includes a `usage` key (`prompt_tokens`, `completion_tokens`, `total_tokens`). Easy to capture.
- **Streaming** (`stream=True`): `_generate_experimental_stream` yields raw chunks via `chunk.model_dump_json()`. By default OpenAI does **not** include usage in chunks; adding `stream_options: {"include_usage": true}` causes the final non-`[DONE]` chunk to carry a `usage` object.
- **`usage_logs` table already exists** with `assistant_id`, `org_id`, `usage_data JSON`, `created_at`. It is never written to today — we extend and populate it.
- **Assistant metadata** lives in `api_callback` column (aliased as `metadata` in application code), stored as JSON.
- **Ollama connector** is a separate file — no changes needed there.

---

## Schema changes

### 1. Extend `usage_logs` with two new columns (migration)

```sql
ALTER TABLE usage_logs ADD COLUMN model_name TEXT;
ALTER TABLE usage_logs ADD COLUMN provider   TEXT;
```

These allow joining against the pricing table at query time. The existing `usage_data` JSON column stores:
```json
{"prompt_tokens": N, "completion_tokens": M, "total_tokens": X}
```

Add one new index:

```sql
CREATE INDEX IF NOT EXISTS idx_usage_logs_assistant
    ON usage_logs(assistant_id);
```

(The table currently only indexes on `org+date` and `user+date`.)

### 2. New `model_pricing` table

```sql
CREATE TABLE IF NOT EXISTS model_pricing (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    provider         TEXT    NOT NULL,           -- 'openai', 'anthropic'
    model_name       TEXT    NOT NULL,           -- 'gpt-4o', 'gpt-4o-mini', ...
    input_per_1m     REAL    NOT NULL DEFAULT 0, -- USD per 1M input tokens
    output_per_1m    REAL    NOT NULL DEFAULT 0, -- USD per 1M output tokens
    notes            TEXT,
    updated_at       INTEGER NOT NULL,
    UNIQUE(provider, model_name)
);
```

Seed with known models at migration time. Operators can `UPDATE` rows as prices change. Unknown models produce `NULL` cost — treated as $0.00, logged but not blocked.

**Suggested seed data (prices as of early 2026, verify before shipping):**

| provider | model_name | input_per_1m | output_per_1m |
|---|---|---|---|
| openai | gpt-4.1 | 2.00 | 8.00 |
| openai | gpt-4.1-mini | 0.40 | 1.60 |
| openai | gpt-4.1-nano | 0.10 | 0.40 |
| openai | gpt-4o | 2.50 | 10.00 |
| openai | gpt-4o-mini | 0.15 | 0.60 |
| openai | gpt-4-turbo | 10.00 | 30.00 |
| openai | gpt-4 | 30.00 | 60.00 |
| openai | o3-mini | 1.10 | 4.40 |
| anthropic | claude-3-5-sonnet-20241022 | 3.00 | 15.00 |
| anthropic | claude-3-5-haiku-20241022 | 0.80 | 4.00 |

---

## Assistant metadata: quota config

No new column needed. Add a `quota` key to the existing `api_callback` JSON:

```json
{
  "connector": "openai",
  "llm": "gpt-4o-mini",
  "prompt_processor": "default",
  "rag_processor": "",
  "quota": {
    "enabled": true,
    "cost_limit_usd": 5.00
  }
}
```

- `enabled: false` or missing `quota` key → no enforcement (safe default, fully backward compatible)
- `cost_limit_usd` is a **lifetime cap** in this MVP (no reset periods — see Risks)

---

## Changes per file

### `backend/lamb/database_manager.py`

Two new methods:

```python
def log_token_usage(self, assistant_id, org_id, model_name, provider, usage_data: dict):
    """
    Write one row to usage_logs for a completed request.
    usage_data: {"prompt_tokens": N, "completion_tokens": M, "total_tokens": X}
    Called fire-and-forget — errors are caught and logged, never propagated.
    """
    try:
        with self._get_connection() as conn:
            conn.execute(
                f"""INSERT INTO {self.table_prefix}usage_logs
                    (organization_id, assistant_id, usage_data, model_name, provider, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                (org_id, assistant_id, json.dumps(usage_data),
                 model_name, provider, int(time.time()))
            )
    except Exception as e:
        logger.error(f"Failed to log token usage for assistant {assistant_id}: {e}")


def get_assistant_cost_usd(self, assistant_id: int) -> float:
    """
    Sum estimated cost in USD for all logged requests for this assistant.
    Returns 0.0 if no pricing data or no usage logged.
    Uses SQLite json_extract to pull token counts from the JSON blob.
    """
    query = f"""
        SELECT
          COALESCE(SUM(
            COALESCE(json_extract(ul.usage_data, '$.prompt_tokens'), 0)
              * COALESCE(mp.input_per_1m, 0) / 1000000.0
            +
            COALESCE(json_extract(ul.usage_data, '$.completion_tokens'), 0)
              * COALESCE(mp.output_per_1m, 0) / 1000000.0
          ), 0.0)
        FROM {self.table_prefix}usage_logs ul
        LEFT JOIN {self.table_prefix}model_pricing mp
               ON ul.model_name = mp.model_name
              AND ul.provider   = mp.provider
        WHERE ul.assistant_id = ?
    """
    with self._get_connection() as conn:
        row = conn.execute(query, (assistant_id,)).fetchone()
        return float(row[0]) if row else 0.0
```

Also add the migration logic for the two new columns and the `model_pricing` table inside the existing `_run_migrations` method.

---

### `backend/lamb/completions/connectors/openai.py`

**Change 1**: In `_generate_experimental_stream`, request usage in stream and expose it via a shared mutable dict (side-channel — simplest approach without refactoring the generator protocol):

```python
async def _generate_experimental_stream(usage_out: dict | None = None):
    # Request usage in the final chunk
    stream_params = params.copy()
    stream_params["stream_options"] = {"include_usage": True}

    stream_obj = await _make_api_call_with_fallback(stream_params)

    async for chunk in stream_obj:
        # Capture usage when it appears (final chunk before [DONE])
        if usage_out is not None and hasattr(chunk, "usage") and chunk.usage:
            usage_out["prompt_tokens"]     = chunk.usage.prompt_tokens
            usage_out["completion_tokens"] = chunk.usage.completion_tokens
            usage_out["total_tokens"]      = chunk.usage.total_tokens
        yield f"data: {chunk.model_dump_json()}\n\n"

    yield "data: [DONE]\n\n"
```

**Change 2**: Update the streaming call site to return both the generator and the usage dict:

```python
if stream:
    usage_out = {}
    return _generate_experimental_stream(usage_out=usage_out), usage_out
else:
    response = await _make_api_call_with_fallback(params)
    return response.model_dump()
```

> **Ollama connector**: no changes. The quota check in `main.py` skips ollama by connector name.

---

### `backend/lamb/completions/main.py`

**Add two helper functions:**

```python
def _check_quota(assistant_id: int, assistant_details) -> None:
    """Raises HTTP 429 if the assistant has exceeded its configured cost limit."""
    try:
        metadata = json.loads(assistant_details.metadata or "{}")
    except Exception:
        return  # malformed metadata → skip check silently

    quota = metadata.get("quota", {})
    if not quota.get("enabled"):
        return

    limit = quota.get("cost_limit_usd")
    if limit is None:
        return

    spent = db_manager.get_assistant_cost_usd(assistant_id)
    if spent >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "message": f"This assistant has reached its usage quota (${limit:.2f} USD).",
                    "type": "quota_exceeded",
                    "code": "assistant_quota_exceeded"
                }
            }
        )


def _provider_for_connector(connector: str) -> str | None:
    return {"openai": "openai", "anthropic": "anthropic"}.get(connector)
```

**Update `create_completion`** to wire quota check + usage logging:

```python
@router.post("/")
async def create_completion(request, assistant, credentials):
    assistant_details = get_assistant_details(assistant)
    plugin_config     = parse_plugin_config(assistant_details)

    # --- Quota pre-check (skipped for ollama) ---
    if plugin_config["connector"] != "ollama":
        _check_quota(assistant, assistant_details)

    pps, connectors, rag_processors = load_and_validate_plugins(plugin_config)
    rag_context = await get_rag_context(...)
    messages    = process_completion_request(...)
    stream      = request.get("stream", False)
    connector   = plugin_config["connector"]
    llm         = plugin_config["llm"]
    provider    = _provider_for_connector(connector)

    if stream:
        if connector == "ollama":
            # Ollama: no tracking
            return StreamingResponse(
                connectors[connector](messages, stream=True, body=request,
                                      llm=llm, assistant_owner=assistant_details.owner),
                media_type="text/event-stream"
            )

        # OpenAI / Anthropic streaming: get usage side-channel
        generator, usage_out = connectors[connector](
            messages, stream=True, body=request,
            llm=llm, assistant_owner=assistant_details.owner
        )

        async def _tracked_stream():
            async for chunk in generator:
                yield chunk
            # Stream finished — log usage (fire-and-forget)
            if usage_out:
                db_manager.log_token_usage(
                    assistant_id=assistant,
                    org_id=assistant_details.organization_id,
                    model_name=llm,
                    provider=provider,
                    usage_data=usage_out
                )

        return StreamingResponse(_tracked_stream(), media_type="text/event-stream")

    else:
        result = await connectors[connector](
            messages, stream=False, body=request,
            llm=llm, assistant_owner=assistant_details.owner
        )
        if connector != "ollama" and isinstance(result, dict) and result.get("usage"):
            db_manager.log_token_usage(
                assistant_id=assistant,
                org_id=assistant_details.organization_id,
                model_name=llm,
                provider=provider,
                usage_data=result["usage"]
            )
        return result
```

---

## Summary of file touches

| File | Change |
|---|---|
| `database_manager.py` | 2 new methods (`log_token_usage`, `get_assistant_cost_usd`); 2 `ALTER TABLE` in migration; 1 new `model_pricing` table with seed data; 1 new index on `assistant_id` |
| `connectors/openai.py` | Add `stream_options: {include_usage: true}`; expose `usage_out` side-channel from streaming path; update return signature |
| `connectors/ollama.py` | No changes |
| `completions/main.py` | `_check_quota()` and `_provider_for_connector()` helpers; quota check before pipeline; stream wrapper + non-stream branch for `log_token_usage` |

No schema changes to the assistants table. No frontend changes needed for enforcement. Admin UI to configure `quota.cost_limit_usd` in assistant metadata is a separate ticket.

---

## Risks and limitations

| Risk | Severity | Note |
|---|---|---|
| **Streaming usage is best-effort** | Medium | If the stream is interrupted before the final chunk, `usage_out` stays empty and nothing is logged. The completion ran but wasn't billed toward the quota. |
| **Race condition on quota check** | Low-medium | Two concurrent requests for the same assistant can both pass the pre-check before either logs. Overrun is bounded to ~2× concurrent requests at the boundary crossing. Acceptable for rough enforcement. |
| **Anthropic connector not covered** | Medium | Plan covers OpenAI only. Anthropic's streaming API also exposes usage in the final event (`message_delta.usage`) but needs a parallel change in `connectors/anthropic.py`. |
| **Model not in pricing table** | Low | Cost is computed as $0.00, so the quota never triggers for that model. The `model_name` is still logged. A warning log when `mp.input_per_1m IS NULL` is recommended. |
| **No cost reset / billing period** | Design gap | `cost_limit_usd` is a lifetime cap in this MVP. Adding a `reset_at` timestamp and filtering `WHERE created_at > reset_at` is the natural extension. Omitted for MVP. |
| **`_generate_original_stream` not covered** | Low | The original stream generator is commented out but still present. If re-enabled, usage tracking silently drops. Add a code comment to warn about this. |
| **SQLite WAL + concurrent writes** | Low | SQLite handles this fine under normal load for this use case. |
