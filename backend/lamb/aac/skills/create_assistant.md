---
id: create-assistant
name: Create New Assistant
description: Guide through creating a new assistant
required_context: []
optional_context: [language]
startup_actions:
  - "lamb assistant config"
  - "lamb model list"
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

## Workflow

1. Gather requirements (2 exchanges max)
2. Propose config in a compact summary (name, model, RAG, prompt)
3. Create after approval
4. Verify with `lamb assistant get`
5. Run one debug check with a sample query

If RAG is enabled, ALWAYS set prompt_template with {context} and {user_input}.
Default model: gpt-4o-mini unless task is complex.
