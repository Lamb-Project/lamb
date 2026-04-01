---
id: improve-assistant
name: Improve Assistant
description: Review and suggest improvements
required_context: [assistant_id]
optional_context: [language]
startup_actions:
  - "lamb assistant get {assistant_id}"
  - "lamb assistant config"
  - "lamb model list"
---

# Skill: Improve Assistant

Review the assistant and suggest improvements. Be brief.

## On startup

Present in MAX 5 lines:
- What the assistant does (1 line)
- 2-3 specific improvements, ranked by impact (1 line each)

Do NOT explain how RAG works, what models are, or what a system prompt is
unless the user asks. They know their assistant — just tell them what to fix.

## Workflow

One improvement at a time. For each:
1. State the change (1-2 sentences)
2. Apply if user approves
3. Verify with debug if RAG is involved

## If assistant uses rubric_rag

Load the rubric. Check prompt template has {context} and {user_input}.
Only mention this if there's an actual problem.

## If assistant uses simple_rag or context_aware_rag

Check RAG_collections is set and prompt template has {context}.
Only run debug if user asks or if you suspect retrieval issues.

## Testing

Always debug pipeline before real completions. But don't run tests
unless the user asks or you've just made a change worth verifying.
