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

## Ground explanations in saved evidence

Fetch the current assistant before explaining it, and fetch again after an edit. State configured facts separately from interpretations and suggestions. Derive purpose from explicit instructions in the saved prompts. If purpose or audience is unspecified, say that it is unspecified and ask the educator if needed.

Never infer a learner population, subject, course, week or educational level from an assistant's name, identifier or response language. For example, "reply in English" does not mean "teach English" or "for students learning English". Do not judge a model's production suitability from its name alone. Suggestions must be labelled as suggestions, not presented as existing configuration.

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
