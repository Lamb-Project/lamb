---
id: explain-assistant
name: Explain Configuration
description: Show how the assistant works internally
required_context: [assistant_id]
optional_context: [language]
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

For simple_augment: an empty template with no_rag is valid and passes the user message through. A nonempty template without {user_input} omits the question. RAG requires {context}, including when a default template was used. Inspect custom processors before applying these rules. A configured model preference may fall back to an enabled organization model at completion; distinguish saved preference from the effective model reported by a run.

Then offer options. Do NOT explain everything unprompted.

## If user asks for detail

Only then go deeper. Use `lamb assistant debug` to show real context.
Keep explanations short. Use bullet points, not paragraphs.

Adapt depth to the user: start minimal, add detail only when asked.


## Explicit knowledge and rubric bindings

Distinguish no_rag, simple_rag (retrieved KB chunks), single_file_rag (whole UTF-8 file), and context_aware_rag. For single_file_rag, show the illustrated assistant UI guide and let the user select and bind the file in the form. The --file-path option is unavailable in frontend liteshell; a PDF requires user-operated KB ingestion instead. Use --rubric-id and --rubric-format for rubric_rag. Read back saved properties and verify retrieval/context before claiming success. Preserve unrelated fields during edits. Use manage-knowledge-base for KB creation/ingestion/query and manage-rubric for rubric creation/editing.


## Read recipe

Use a verified ASSISTANT_ID from the selected resource or `lamb assistant list`; never guess.
```aac-command
lamb assistant get ASSISTANT_ID
```
Summarize saved name, description, prompts, connector/model preference, RAG processor and bindings. State absent values as unspecified. For a requested pipeline inspection:
```aac-command
lamb assistant debug ASSISTANT_ID --message "A representative question"
```
Debug shows assembled input, not an assistant answer or a quality evaluation. On missing/forbidden resources stop and ask the user to select an accessible assistant. For an edit, activate improve-assistant; for actual conversation, chat-with-assistant.


## Guided workspace handover

After inspecting the selected assistant, run `frontend-manage open assistant ASSISTANT_ID --tab properties` and explain the saved properties beside that view.

Navigate once at the useful handover point, unless the user asked to stay on the current page. Use verified returned IDs. Wait for status=opened before saying the view is open. On blocked, failed or unavailable navigation, preserve and report any successful resource action separately, then provide the appropriate UI guide; never repeat a successful write to fix navigation. Respect unsaved edits. No extra confirmation is needed just to open a view.

For the complete saved configuration as inline JSON use `lamb assistant export ASSISTANT_ID`. This reads the existing resource and does not write a local file. For caller identity use `lamb whoami`; do not infer roles from resource names.
