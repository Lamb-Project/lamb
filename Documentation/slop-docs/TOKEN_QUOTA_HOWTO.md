# How to Set a Token Cost Quota on an Assistant

The quota lives in the assistant's `metadata` JSON (the `api_callback` column).  
There is no UI for it yet — set it via SQL or the API.

---

## Option 1 — SQLite directly (quickest for testing)

```sql
UPDATE assistants
SET api_callback = json_patch(
    COALESCE(api_callback, '{}'),
    '{"quota": {"enabled": true, "cost_limit_usd": 5.0}}'
)
WHERE id = 42;
```

Run via `sqlite3 $LAMB_DB_PATH/lamb_v4.db` or any SQLite client.

---

## Option 2 — via the assistant update API

`PUT /creator/assistant/{id}` accepts a `metadata` body field. Send the full merged metadata JSON with the `quota` key added:

```bash
curl -X PUT http://localhost:9099/creator/assistant/42 \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "connector": "openai",
      "llm": "gpt-4o-mini",
      "prompt_processor": "default",
      "rag_processor": "",
      "quota": {
        "enabled": true,
        "cost_limit_usd": 5.0
      }
    }
  }'
```

---

## Disabling the quota

Set `enabled: false` or remove the `quota` key entirely — the check is skipped in both cases, with no effect on behaviour.

---

## Checking current spend for an assistant

```sql
SELECT
  ul.assistant_id,
  ROUND(SUM(
    COALESCE(json_extract(ul.usage_data, '$.prompt_tokens'), 0)
      * COALESCE(mp.input_per_1m, 0) / 1000000.0
    +
    COALESCE(json_extract(ul.usage_data, '$.completion_tokens'), 0)
      * COALESCE(mp.output_per_1m, 0) / 1000000.0
  ), 4) AS cost_usd
FROM usage_logs ul
LEFT JOIN model_pricing mp
       ON ul.model_name = mp.model_name
      AND ul.provider   = mp.provider
WHERE ul.assistant_id = 42
GROUP BY ul.assistant_id;
```

---

## Next steps

A proper admin UI endpoint (`GET /creator/assistant/{id}/usage`) returning current spend and quota config would be the natural follow-up to this MVP.
