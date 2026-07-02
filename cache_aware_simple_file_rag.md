# Implementation Log: Cache-Aware RAG & Grep RAG

Tracking all changes made per `IMPLEMENTATION_PLAN_CACHED_GREP_RAG.md`.

---

## Cache-Aware Single File RAG ✅

**Implementation choice: Option B** — Extended `simple_augment.py` with automatic cache-aware mode detection. When an assistant has `rag_processor: "single_file_rag"` in its metadata, `simple_augment` automatically splits the RAG context into a separate user message (before the question), enabling LLM provider prompt caching. No new prompt processor file needed. No auto-selection in `main.py` needed. Fully backward compatible.

### Files Changed

| File | Operation | Description |
|------|-----------|-------------|
| `backend/lamb/completions/pps/simple_augment.py` | **Edited** | Added `_is_single_file_rag()` helper + cache-aware logic. When assistant metadata has `rag_processor: "single_file_rag"`, context is emitted as a separate user message before conversation history. When not, existing template-based behavior is unchanged. |
| `testing/playwright/tests/single_file_rag.spec.js` | **Created** | Playwright E2E test: creates an assistant with `single_file_rag`, uploads a fixture file, sends two messages in the same chat session, and verifies both responses use file content (proving the cache-aware pipeline works across multiple turns). Cleans up the assistant afterward. |
| `testing/playwright/fixtures/single_file_rag_fixture.txt` | **Created** | Test fixture file containing fake LAMB platform facts ("Lambda" the mascot, "12,847" users) that the E2E test verifies in chat responses. |
| `docker-compose-example.yaml` | **Edited** | Changed `GLOBAL_LOG_LEVEL=WARNING` to `${GLOBAL_LOG_LEVEL:-WARNING}` so debug logs can be enabled from the project `.env` |

### Tests

**Playwright E2E** (`testing/playwright/tests/single_file_rag.spec.js`, 3 serial tests):

```bash
cd testing/playwright && npx playwright test tests/single_file_rag.spec.js
```

| # | Test | What it validates |
|---|------|-------------------|
| 1 | Create assistant with `single_file_rag` | Fills form, selects `single_file_rag` from RAG dropdown, uploads fixture file via `#file-upload`, selects the radio, saves |
| 2 | Chat: two messages in same session | Sends "What is the name of the platform mascot?" → asserts response contains "Lambda"/"llama". Then sends "How many registered users...?" → asserts response contains "12,847". Both in the same chat session (cache-aware prefix reused across turns) |
| 3 | Cleanup | Deletes the assistant via confirmation modal |

### Verified with real API call (OpenAI gpt-4o-mini)

**Integration test passed.** Ran `python tests/test_integration_cache.py --real --size 12000` against the live OpenAI API. Results:

| Call | Mode | prompt_tokens | cached_tokens | Result |
|------|------|:---:|:---:|--------|
| 1 | Cache (warm-up) | 2,060 | 0 | (expected) |
| 2 | Cache (test) | 2,058 | **1,920** | ✅ **CACHE HIT** |
| 3 | Standard (control) | 2,035 | **0** | ✅ No cache |

**Real cost savings: 46%** with gpt-4o-mini. With gpt-4o the savings would be ~88%.

### How it works
- `simple_augment` checks `assistant.metadata` for `rag_processor == "single_file_rag"`
- If true + RAG context exists: emits context as separate cached user message
- Messages: `[system] → [user: file context] → [prev msgs] → [user: question]`
- System + file context are byte-identical across requests → LLM provider caches them
- No new files, no config changes, no UI changes — just works

### Example: messages sent to the LLM

With prompt template: `"Responde la pregunta del usuario: --- {user_input} ---\n\nEste es el contexto:\n--- {context} ---"`

```
Message 1 — System (CACHED)
─────────────────────────────────────────────────────────────────────────┐
│ Eres un asistente de aprendizaje que ayuda a los estudiantes a        │
│ aprender sobre un tema específico. Utiliza el contexto para responder │
│ las preguntas del usuario.                                             │
└────────────────────────────────────────────────────────────────────────┘

Message 2 — User: file context (CACHED)
┌─────────────────────────────────────────────────────────────────────────┐
│ The user may ask you questions about the following document. Use this  │
│ content to answer their questions accurately.                          │
│                                                                         │
│ El programa de Dbizi es un sistema de préstamo de bicicletas públicas…│
│ [full file content — thousands of characters]                          │
└─────────────────────────────────────────────────────────────────────────┘

Message 3 — User: question + template (INPUT — only this changes)
┌─────────────────────────────────────────────────────────────────────────┐
│ Responde la pregunta del usuario: --- ¿Cuál es el tiempo máximo? ---   │
│                                                                         │
│ Este es el contexto:                                                    │
│                                                                         │
│ ---  ---                                                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Placeholder handling in cache mode

In cache mode, `{context}` is replaced with empty string (the actual file content is already in Message 2). The `---  ---` structure remains as a template artifact. This avoids duplicating the file in the prompt while keeping the template structure intact. `{user_input}` is replaced with the actual question as usual.

The replacement is language-agnostic — works regardless of what language the template is written in.

### Verified in production (Docker + backend logs)

Confirmed working via `docker compose -f docker-compose-example.yaml up -d --build` with `GLOBAL_LOG_LEVEL=DEBUG`. Backend log output:

```
DEBUG:lamb.completions:Processed messages: [
  {'role': 'system', 'content': 'Eres un asistente de aprendizaje...'},
  {'role': 'user',   'content': 'The user may ask you questions about the following document...[full file content]'},
  {'role': 'user',   'content': 'Este es el contexto:\n ---  --- \n\nAhora responde la pregunta del usuario: --- Cuáles son los precios? ---'}
]
```

Message [0] and [1] are identical across requests → cached. Only message [2] changes.

