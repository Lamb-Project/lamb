---
id: create-assistant
name: Create New Assistant
description: Guide through creating a new assistant
required_context: []
optional_context: [language]
startup_actions:
  - "lamb assistant config"
  - "lamb kb list"
  - "lamb rubric list"
---

# Skill: Create New Assistant

Help the educator create an assistant. Be brief and direct.

## On startup

Ask 2-3 quick questions (not a checklist):
- What topic/subject?
- Who uses it? (level)
- Should it use a knowledge base or rubric?

## Prompt Template — CRITICAL

EVERY assistant MUST have a prompt_template. Set it with --prompt-template during creation.

**Non-RAG assistant** (no knowledge base):
```
--prompt-template "{user_input}"
```

**RAG assistant** (with knowledge base):
```
--prompt-template "Context:\n{context}\n\nStudent question: {user_input}\n\nAnswer using the provided context."
```

- `{user_input}` = where the student's message goes. Always required.
- `{context}` = where KB content goes. Required when RAG is enabled.
- Without `{user_input}`, the student's question is lost.
- Without `{context}` on a RAG assistant, KB content is silently discarded.

NEVER create an assistant with an empty prompt_template. NEVER.

## Workflow

1. Gather requirements (2 exchanges max)
2. Propose config in a compact summary (name, model, RAG, prompt template)
3. Once the name is chosen, rename the session so it's findable later:
   `lamb session rename "Create: <name>"`
4. Create after approval — ALWAYS include --prompt-template
5. Verify with `lamb assistant get`
6. Offer to run a quick test with a sample question

Do NOT run debug/bypass after creation just to "verify" — for non-RAG assistants it returns
the raw prompt assembly which is expected and not useful to show the user. Just offer a real test.

Default model: use `lamb assistant config` to pick the org default.
If RAG is enabled, ALWAYS set prompt_template with {context} and {user_input}.
