# Multitool RAG context dump

- timestamp: 2026-04-22 14:55:40
- assistant_id: None
- owner: t***@example.com

## Orchestrator raw

```
{"intent": "SEARCH", "rationale": "r", "tools": [{"name": "kb_query", "arguments": {}}]}
```

## Parsed plan

```json
{
  "tools": [
    {
      "name": "kb_query",
      "arguments": {}
    }
  ],
  "rationale": "r",
  "intent": "SEARCH"
}
```

## Tool execution

```json
[
  {
    "name": "kb_query",
    "merged_args": {
      "collections": [
        "c1"
      ],
      "assistant_owner": "test@example.com",
      "query": "hi"
    },
    "ok": true
  }
]
```

## Full multitool_debug (JSON)

```json
{
  "assistant_id": null,
  "owner_masked": "t***@example.com",
  "allowed_tools": [
    "kb_query"
  ],
  "rejected_by_registry": [],
  "user_query_stats": {
    "len": 2,
    "head": "hi",
    "tail": ""
  },
  "kb_desc_keys": [
    "c1"
  ],
  "rubric_desc_keys": [],
  "per_tool_config_summary": {
    "kb_query": {
      "collections": [
        "c1"
      ]
    }
  },
  "orchestrator": {
    "raw_llm_text": "{\"intent\": \"SEARCH\", \"rationale\": \"r\", \"tools\": [{\"name\": \"kb_query\", \"arguments\": {}}]}",
    "parsed": {
      "tools": [
        {
          "name": "kb_query",
          "arguments": {}
        }
      ],
      "rationale": "r",
      "intent": "SEARCH"
    }
  },
  "executed": [
    {
      "name": "kb_query",
      "merged_args": {
        "collections": [
          "c1"
        ],
        "assistant_owner": "test@example.com",
        "query": "hi"
      },
      "ok": true
    }
  ],
  "timings_ms": {
    "orchestrate_ms": 0.163,
    "tools_total_ms": 0.267
  },
  "skipped_no_executor": []
}
```

## Final injected context

=== Tool: kb_query (ok) ===
ctx
