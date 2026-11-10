---
id: improve-assistant
name: Improve Assistant
description: Review and suggest improvements
required_context: [assistant_id]
optional_context: [language]
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
1. State the change in one or two sentences. When the user has asked for it, queue the complete update command in the same turn: the application shows the review with Approve, Edit and Cancel. Do not wait for a prose "yes" first; that creates two approval steps.
2. After approval, read back the saved assistant
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

Distinguish no_rag, simple_rag (retrieved KB chunks), single_file_rag (whole UTF-8 file), and context_aware_rag. For single_file_rag, an existing owned upload returned by Moodle import can be bound using --file-reference OWNED_REFERENCE. This is an ownership-validated server reference, never a local path. If no owned reference exists, show the illustrated assistant UI guide and let the user select and bind the file in the form. The --file-path option remains unavailable in frontend liteshell; PDFs require KB ingestion (a connected Moodle import can do that after approval). Use --rubric-id and --rubric-format for rubric_rag. Read back saved properties and verify retrieval/context before claiming success. Preserve unrelated fields during edits. Use manage-knowledge-base for KB creation/ingestion/query and manage-rubric for rubric creation/editing.

## UI tutorial requests

For user-operated configuration or single-file selection, read `lamb docs read ui-assistants`. Show its relevant screenshot and full-size link. Single File Rag uses Upload New File in the assistant form, not KB Ingest Content. A tutorial request is not authorization to create or edit resources.


## Exact edit sequence

Use an actual selected/listed ASSISTANT_ID. Read its full current state first:
```aac-command
lamb assistant get ASSISTANT_ID
```
Translate the user's suggestion into specific fields and queue the complete update command in the same turn; the application's review is the proposal, so never present a separate prose proposal and wait for a reply. Copy user-supplied text exactly, character for character. A rejection changes nothing. For an approved request to shorten answers, retain the original prompt's other instructions and add only the requested constraint:
```aac-command
lamb assistant update ASSISTANT_ID --system-prompt "Original instructions plus the approved shorter-answer constraint"
lamb assistant get ASSISTANT_ID
```
Compare requested changes and unrelated model/RAG/rubric/template settings with the original. On an error, report it and inspect before retrying. Never reset model or RAG settings during a text-only edit. Use chat-with-assistant for the same representative question before/after; use test-and-evaluate to rerun the user's selected saved scenarios. A debug result is not a behavioral pass.

Deletion is separate from improvement. Only for an explicit deletion request, identify the assistant and explain the deletion before the normal confirmation:
```aac-command
lamb assistant delete ASSISTANT_ID
```
Do not recreate or delete an assistant as a workaround for an edit failure.


## Guided workspace handover

After an approved edit and saved-state readback, run `frontend-manage open assistant ASSISTANT_ID --tab properties`. If the user wants to edit manually, run `frontend-manage open assistant ASSISTANT_ID --tab edit`; opening the form does not edit or save anything.

Navigate once at the useful handover point, unless the user asked to stay on the current page. Use verified returned IDs. Wait for status=opened before saying the view is open. On blocked, failed or unavailable navigation, preserve and report any successful resource action separately, then provide the appropriate UI guide; never repeat a successful write to fix navigation. Respect unsaved edits. No extra confirmation is needed just to open a view.


## Retrieval evidence limits

For one-off pipeline inspection use `lamb assistant debug ASSISTANT_ID --message "exact question"`.
Only valid assembled_messages demonstrate this new invocation's input, not a historical trace.
An empty/failed debug result is not a successful inspection. Report the failure before
substituting a direct `lamb kb query KB_ID "QUESTION"`, and label that as a separate KB probe.
Do not invent omitted chunk ranks/scores, claim language mismatch as a proven cause,
or promise that a larger top-k fixes the problem. Distinguish observations from
hypotheses and proposed experiments. Saved tests require actual scenario/run IDs;
a bypass inspection alone does not evaluate answer quality.


For an existing owned single-file import, use the returned reference directly and request the normal application confirmation once:
```aac-command
lamb assistant update ASSISTANT_ID --rag-processor single_file_rag --file-reference OWNED_REFERENCE
```
Do not omit the reference and then claim single-file assistants require browser creation. Validate by reading the saved metadata and actually chatting with the assistant.
