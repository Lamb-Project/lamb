---
id: create-assistant
name: Create New Assistant
description: Guide through creating a new assistant
required_context: []
optional_context: [language]
---

# Skill: Create New Assistant

Help the educator create an assistant. Be brief and direct.

## On startup

Use context already given. Ask only for missing choices, briefly (not a checklist):
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

1. Use the stated purpose, audience and sources; ask only for a missing choice.
2. Prepare the complete configuration. Include the purpose and intended audience in --description. Do not ask the user to approve a prose draft first.
3. Once the name is chosen, rename the session so it's findable later:
   `lamb session rename "Create: <name>"`
4. Invoke ONE complete create command now to prepare the application approval card. Nothing is created until the user approves that card. Include:
   - `--system-prompt`, `--llm`, `--prompt-template` (always)
   - `--rag-processor`, `--rag-collections` (if using a KB)
   - `--connector PROVIDER` (or whatever the org default is)
   Do NOT create first and then update to add RAG. Put everything in one command.
5. Verify with `lamb assistant get ASSISTANT_ID`
6. Offer to run a quick test with a sample question

Do NOT run debug/bypass after creation just to "verify" — for non-RAG assistants it returns
the raw prompt assembly which is expected and not useful to show the user. Just offer a real test.

Model discovery: run `lamb assistant config`. `global_default_model` is the configured org default; `global_default_available` says whether discovery lists it. `capabilities.connectors` lists models currently reported available. `defaults.connector` and `defaults.llm` are the reconciled new-assistant form choice. `form_defaults` are raw saved form values and may be stale: never call them the global default. If discovery is empty or fails, report that models could not be verified; do not invent availability or infer licensing. Answer model questions directly from this tool, not guessed documentation topics. Listing models is read-only and needs no confirmation.
If RAG is enabled, ALWAYS include --rag-processor and --rag-collections in the create command.
ALWAYS include --connector (from the organization configuration) and --prompt-processor simple_augment.


## Explicit knowledge and rubric bindings

Distinguish no_rag, simple_rag (retrieved KB chunks), single_file_rag (whole UTF-8 file), and context_aware_rag. For single_file_rag, an existing owned upload returned by Moodle import can be bound using --file-reference OWNED_REFERENCE. This is an ownership-validated server reference, never a local path. If no owned reference exists, show the illustrated assistant UI guide and let the user select and bind the file in the form. The --file-path option remains unavailable in frontend liteshell; PDFs require KB ingestion (a connected Moodle import can do that after approval). Use --rubric-id and --rubric-format for rubric_rag. Read back saved properties and verify retrieval/context before claiming success. Preserve unrelated fields during edits. Use manage-knowledge-base for KB creation/ingestion/query and manage-rubric for rubric creation/editing.

## UI tutorial requests

For user-operated configuration or single-file selection, read `lamb docs read ui-assistants`. Show its relevant screenshot and full-size link. Single File Rag uses Upload New File in the assistant form, not KB Ingest Content. A tutorial request is not authorization to create or edit resources.


## Validated creation recipes

First run `lamb assistant config`. Use the returned reconciled `defaults.connector` and `defaults.llm` for PROVIDER and MODEL, unless the user selects another listed model. Never use raw `form_defaults` as the organization default. Replace uppercase placeholders with the requested content and verified returned IDs. The application will review the complete proposal with the user. Select ONE mode. These examples use simple_augment; do not mix file, KB and rubric bindings.

```aac-command
lamb assistant create NAME --description "Purpose and audience" --system-prompt "Assistant instructions" --connector PROVIDER --llm MODEL --prompt-processor simple_augment --rag-processor no_rag --prompt-template "{user_input}"
lamb assistant create NAME --description "Purpose and audience" --system-prompt "Answer using the supplied sources" --connector PROVIDER --llm MODEL --prompt-processor simple_augment --rag-processor simple_rag --rag-collections KB_ID --rag-top-k 3 --prompt-template "Context: {context} Question: {user_input}"
lamb docs read ui-assistants
lamb assistant create NAME --description "Purpose and audience" --system-prompt "Answer using relevant supplied context" --connector PROVIDER --llm MODEL --prompt-processor simple_augment --rag-processor context_aware_rag --rag-collections KB_ID --rag-top-k 3 --prompt-template "Context: {context} Question: {user_input}"
lamb assistant create NAME --description "Assessment purpose and audience" --system-prompt "Assess the submission against the supplied rubric" --connector PROVIDER --llm MODEL --prompt-processor simple_augment --rag-processor rubric_rag --rubric-id RUBRIC_ID --rubric-format markdown --prompt-template "Rubric: {context} Submission: {user_input}"
```

Create requires confirmation. Keep the returned assistant ID. Read back `lamb assistant get ASSISTANT_ID` and compare every requested setting. Do not create twice after an unclear response; inspect the list first. If no existing owned reference was supplied, for single-file frontend selection show the ui-assistants guide and let the user choose/upload through the form; let the user finish saving the binding in the form, then inspect the assistant; never invent a reference or use --file-path in liteshell. For KB setup activate manage-knowledge-base, and for a missing rubric activate manage-rubric. Return to this recipe after that prerequisite exists. A readback proves configuration, not behavior: use chat-with-assistant and test-and-evaluate for real responses and saved tests.

## Show the user the workspace

After successful creation and readback, use `frontend-manage open assistant ASSISTANT_ID --tab properties` to show the result. This requires a connected frontend. Claim navigation only after an opened result. A blocked/unavailable result means guide the user instead; do not retry automatically.


## Guided workspace handover

If the user asks to open the creation form, run `frontend-manage open assistant-create` immediately, then explain fields only as needed. Do not start the creation interview or issue a create command for a navigation-only request. For the assistant list run `frontend-manage open assistants`. After an approved creation, read back the saved assistant and run `frontend-manage open assistant ASSISTANT_ID --tab properties`.

Navigate once at the useful handover point, unless the user asked to stay on the current page. Use verified returned IDs. Wait for status=opened before saying the view is open. On blocked, failed or unavailable navigation, preserve and report any successful resource action separately, then provide the appropriate UI guide; never repeat a successful write to fix navigation. Respect unsaved edits. No extra confirmation is needed just to open a view.


For an existing owned single-file import, use the returned reference directly and request the normal application confirmation once:
```aac-command
lamb assistant create NAME --rag-processor single_file_rag --file-reference OWNED_REFERENCE
```
Do not omit the reference and then claim single-file assistants require browser creation. Validate by reading the saved metadata and actually chatting with the assistant.


## One prepared proposal, one decision

If the user selects “create with your proposal”, prepare the create command immediately. Never answer with another “shall I create it?” menu. The application shows a plain-language review and Create / Edit proposal / Cancel controls. The command is only queued at this point. A Create click runs that exact saved action once. An edit makes a new proposal; it is not approval of the old one. After a successful creation, verify and open the assistant, without asking for creation again. Do not display commands, processor names or full configuration in chat unless the user asks for technical details.
