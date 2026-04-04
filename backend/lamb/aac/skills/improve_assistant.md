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

On startup, ALWAYS check:
1. Does the assistant have a non-empty prompt_template? If empty → WARN immediately, this is broken.
2. Does the prompt_template contain `{user_input}`? If missing → WARN, student messages are lost.
3. If RAG is enabled (rag_processor is NOT no_rag): does the template contain `{context}`? If missing → WARN, KB content is silently discarded.

This is the FIRST thing to check. A missing prompt_template is more critical than model choice or system prompt wording.

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
