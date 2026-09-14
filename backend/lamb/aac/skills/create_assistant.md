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

For simple_augment, use an explicit template as shown below. A new RAG assistant also receives a context-bearing default if you omit the template. Inspect the saved configuration.

**Non-RAG assistant** (no knowledge base):
```
--prompt-template "{user_input}"
```

**RAG assistant** (with knowledge base):
```
--prompt-template "Context:\n{context}\n\nStudent question: {user_input}\n\nAnswer using the provided context."
```

- In a non-empty template, `{user_input}` inserts the student's message.
- `{context}` = where KB content goes. Required when RAG is enabled.
- A non-empty template without `{user_input}` omits the question; an empty template passes the original message through.
- Without `{context}` on a RAG assistant, KB content is silently discarded.

An empty template is valid for no_rag but does not inject RAG context. For a custom prompt processor, inspect its behavior before applying these simple_augment rules.

## Workflow

1. Gather requirements (2 exchanges max)
2. Propose config in a compact summary (name, model, RAG, prompt template)
3. Once the name is chosen, rename the session so it's findable later:
   `lamb session rename "Create: <name>"`
4. Create after approval — include ALL config in a SINGLE create command:
   - `--system-prompt`, `--llm`, `--prompt-template` (always)
   - `--rag-processor`, `--rag-collections` (if using a KB)
   - `--connector PROVIDER` (or whatever the org default is)
   Do NOT create first and then update to add RAG. Put everything in one command.
5. Verify with `lamb assistant get`
6. Offer to run a quick test with a sample question

Do NOT run debug/bypass after creation just to "verify" — for non-RAG assistants it returns
the raw prompt assembly which is expected and not useful to show the user. Just offer a real test.

Model discovery: run `lamb assistant config`. `global_default_model` is the configured org default; `global_default_available` says whether discovery lists it. `capabilities.connectors` lists models currently reported available. `defaults.connector` and `defaults.llm` are the reconciled new-assistant form choice. `form_defaults` are raw saved form values and may be stale: never call them the global default. If discovery is empty or fails, report that models could not be verified; do not invent availability or infer licensing. Answer model questions directly from this tool, not guessed documentation topics. Listing models is read-only and needs no confirmation.
If RAG is enabled, ALWAYS include --rag-processor and --rag-collections in the create command.
ALWAYS include --connector (from the organization configuration) and --prompt-processor simple_augment.


## Explicit knowledge and rubric bindings

Distinguish no_rag, simple_rag (retrieved KB chunks), single_file_rag (whole UTF-8 file), and context_aware_rag. For single_file_rag, show the illustrated assistant UI guide and let the user select and bind the file in the form. The --file-path option is unavailable in frontend liteshell; a PDF requires user-operated KB ingestion instead. Use --rubric-id and --rubric-format for rubric_rag. Read back saved properties and verify retrieval/context before claiming success. Preserve unrelated fields during edits. Use manage-knowledge-base for KB creation/ingestion/query and manage-rubric for rubric creation/editing.

## UI tutorial requests

For user-operated configuration or single-file selection, read `lamb docs read ui-assistants`. Show its relevant screenshot and full-size link. Single File Rag uses Upload New File in the assistant form, not KB Ingest Content. A tutorial request is not authorization to create or edit resources.


## Validated creation recipes

First run `lamb assistant config`. Use the returned reconciled `defaults.connector` and `defaults.llm` for PROVIDER and MODEL, unless the user selects another listed model. Never use raw `form_defaults` as the organization default. Replace uppercase placeholders with user-approved content and verified returned IDs. Select ONE mode. These examples use simple_augment; do not mix file, KB and rubric bindings.

```aac-command
lamb assistant create NAME --description "Approved purpose" --system-prompt "Approved assistant instructions" --connector PROVIDER --llm MODEL --prompt-processor simple_augment --rag-processor no_rag --prompt-template "{user_input}"
lamb assistant create NAME --description "Approved purpose" --system-prompt "Answer using the supplied sources" --connector PROVIDER --llm MODEL --prompt-processor simple_augment --rag-processor simple_rag --rag-collections KB_ID --rag-top-k 3 --prompt-template "Context: {context} Question: {user_input}"
lamb docs read ui-assistants
lamb assistant create NAME --description "Approved purpose" --system-prompt "Answer using relevant supplied context" --connector PROVIDER --llm MODEL --prompt-processor simple_augment --rag-processor context_aware_rag --rag-collections KB_ID --rag-top-k 3 --prompt-template "Context: {context} Question: {user_input}"
lamb assistant create NAME --description "Approved assessment purpose" --system-prompt "Assess the submission against the supplied rubric" --connector PROVIDER --llm MODEL --prompt-processor simple_augment --rag-processor rubric_rag --rubric-id RUBRIC_ID --rubric-format markdown --prompt-template "Rubric: {context} Submission: {user_input}"
```

Create requires confirmation. Keep the returned assistant ID. Read back `lamb assistant get ASSISTANT_ID` and compare every requested setting. Do not create twice after an unclear response; inspect the list first. For single-file frontend selection, show the ui-assistants guide and let the user choose/upload through the form; let the user finish saving the binding in the form, then inspect the assistant; never invent a reference or use --file-path in liteshell. For KB setup activate manage-knowledge-base, and for a missing rubric activate manage-rubric. Return to this recipe after that prerequisite exists. A readback proves configuration, not behavior: use chat-with-assistant and test-and-evaluate for real responses and saved tests.

## Show the user the workspace

After successful creation and readback, use `frontend-manage open assistant ASSISTANT_ID --tab properties` to show the result. This requires a connected frontend. Claim navigation only after an opened result. A blocked/unavailable result means guide the user instead; do not retry automatically.


## Guided workspace handover

If the user asks to open the creation form, run `frontend-manage open assistant-create` immediately, then explain fields only as needed. Do not start the creation interview or issue a create command for a navigation-only request. For the assistant list run `frontend-manage open assistants`. After an approved creation, read back the saved assistant and run `frontend-manage open assistant ASSISTANT_ID --tab properties`.

Navigate once at the useful handover point, unless the user asked to stay on the current page. Use verified returned IDs. Wait for status=opened before saying the view is open. On blocked, failed or unavailable navigation, preserve and report any successful resource action separately, then provide the appropriate UI guide; never repeat a successful write to fix navigation. Respect unsaved edits. No extra confirmation is needed just to open a view.
