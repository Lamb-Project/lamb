---
id: explain-assistant
name: Explain Configuration
description: Show how the assistant works internally
required_context: [assistant_id]
optional_context: [language]
startup_actions:
  - "lamb assistant get {assistant_id}"
---

# Skill: Explain Assistant

Show the educator how their assistant works. Be brief.

## On startup

Summarize in 3-4 short lines:
- Purpose (one sentence)
- Model + RAG setup (one line)
- How the prompt assembles (one line)
- Prompt template status: does it have `{user_input}`? If RAG, does it have `{context}`?

If the prompt_template is empty or missing critical placeholders, say so clearly:
- Empty template → "WARNING: prompt_template is empty. The pipeline will fail."
- RAG without `{context}` → "WARNING: RAG is enabled but template has no {context}. KB content will be discarded."
- Missing `{user_input}` → "WARNING: no {user_input} in template. Student messages won't be included."

Then offer options. Do NOT explain everything unprompted.

## If user asks for detail

Only then go deeper. Use `lamb assistant debug` to show real context.
Keep explanations short. Use bullet points, not paragraphs.

Adapt depth to the user: start minimal, add detail only when asked.


## Explicit knowledge and rubric bindings

Distinguish no_rag, simple_rag (retrieved KB chunks), single_file_rag (whole UTF-8 file), and context_aware_rag. Use --file-path with an owned uploaded reference for single_file_rag; a PDF requires KB ingestion instead. Use --rubric-id and --rubric-format for rubric_rag. Read back saved properties and verify retrieval/context before claiming success. Preserve unrelated fields during edits. Use manage-knowledge-base for KB creation/ingestion/query and manage-rubric for rubric creation/editing.
