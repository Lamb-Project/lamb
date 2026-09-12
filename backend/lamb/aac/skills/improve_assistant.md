---
id: improve-assistant
name: Improve Assistant
description: Review and suggest improvements
required_context: [assistant_id]
optional_context: [language]
startup_actions:
  - "lamb assistant get {assistant_id}"
  - "lamb assistant config"
---

# Skill: Improve Assistant

Review the assistant and suggest improvements. Be brief.

## On startup

Present in MAX 5 lines:
- What the assistant does (1 line)
- 2-3 specific improvements, ranked by impact (1 line each)

Do NOT explain how RAG works, what models are, or what a system prompt is
unless the user asks. They know their assistant — just tell them what to fix.

## Prompt Template Check — CRITICAL

On startup, inspect the prompt processor. For simple_augment:
1. An empty template with no_rag passes the original question through and is valid.
2. A non-empty template without `{user_input}` omits the question; flag it.
3. A RAG template without `{context}`, including an empty template, discards retrieved context. Confirm this with debug and propose a correction.

Do not silently change the template during an unrelated edit. Preserve it unless
the user-approved change includes it. Inspect custom processors before claiming
they follow simple_augment semantics.

## Workflow

One improvement at a time. For each:
1. State the change (1-2 sentences)
2. Apply if user approves
3. Verify with debug if RAG is involved

## If assistant uses rubric_rag

Load the rubric. Check prompt template has `{context}` and `{user_input}`.
Only mention this if there's an actual problem.

## If assistant uses simple_rag or context_aware_rag

Check RAG_collections is set and prompt template has `{context}` and `{user_input}`.
Only run debug if user asks or if you suspect retrieval issues.

## Testing

For RAG assistants running a full test suite, suggest bypass first.
For casual single questions or non-RAG assistants, just run directly.
Don't run tests unless the user asks or you've just made a change worth verifying.


## Explicit knowledge and rubric bindings

Distinguish no_rag, simple_rag (retrieved KB chunks), single_file_rag (whole UTF-8 file), and context_aware_rag. Use --file-path with an owned uploaded reference for single_file_rag; a PDF requires KB ingestion instead. Use --rubric-id and --rubric-format for rubric_rag. Read back saved properties and verify retrieval/context before claiming success. Preserve unrelated fields during edits. Use manage-knowledge-base for KB creation/ingestion/query and manage-rubric for rubric creation/editing.
