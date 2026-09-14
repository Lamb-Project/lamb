---
id: manage-knowledge-base
name: Manage Knowledge Base
description: Create and inspect knowledge bases, check files and ingestion status, and verify retrieval
required_context: []
optional_context: [language]
startup_actions:
  - "lamb kb list"
---

Help the user create and populate a knowledge base. Ask for the intended source and purpose, then use `lamb kb create NAME --description TEXT`. Creation requires user approval.

For frontend users who need to supply local files, read `lamb docs read ui-knowledge-bases` and guide them through the existing Knowledge Bases UI. The user opens the file picker, selects the file and presses Upload File. Display the documented screenshot when useful or requested, using its exact Markdown URL. Do not replace this tutorial with an AAC attachment request or ask for a local path. Wait for the user's response, then verify status/retrieval with read tools if the KB is known. Do not execute a write merely because you are explaining its steps.

Frontend liteshell cannot upload files, including staged server references. Do not run `lamb aac attach` or `lamb kb upload`, offer to perform ingestion, or ask for approval for these operations. Show the illustrated KB UI guide and let the user select and ingest the file. Then inspect KB status and query the content.

For PDFs use `--plugin markitdown_ingest`; for UTF-8 text/Markdown use `--plugin simple_ingest`. If the service reports the plugin unavailable, report the actual failure. Do not substitute a placeholder or retyped summary for the user's file.

Submission alone is not completed ingestion. Inspect `lamb kb jobs KB_ID`, `lamb kb status KB_ID` and `lamb kb get KB_ID` and query a distinctive fact with `lamb kb query KB_ID "question" --top-k 3`. Check source identity and actual retrieved text. Report empty/pending/error results accurately; do not loop indefinitely. Suggest a retry only after identifying the cause.

For a KB-backed assistant use simple_rag or context_aware_rag with explicit collection IDs and a prompt template containing {user_input} and {context}. Single-file RAG binds a UTF-8 upload through the assistant UI; --file-path is unavailable in frontend liteshell. PDFs must first be ingested into a KB through the UI.


## Inspect a knowledge base or verify a user-operated upload

Load this skill for requests such as "what is in this KB?", "did my file finish ingesting?", or "check the KB after I cancelled upload".

1. If the KB ID is unknown, run `lamb kb list` and identify the intended KB with the user. Never guess an ID.
2. Run `lamb kb get KB_ID` for details and any file information returned by the service.
3. Run `lamb kb jobs KB_ID` and `lamb kb status KB_ID` for ingestion jobs, failures and progress. Distinguish queued/running jobs from completed ingestion.
4. When retrieval should be available, run `lamb kb query KB_ID "a distinctive question from the user's file" --top-k 3`. Inspect returned source names and text. An empty query result alone does not prove there are no files.
5. Report only what these responses establish. If a complete file inventory is unavailable, read `lamb docs read ui-knowledge-bases` and guide the user to the documented KB file view. Do not invent a file-list command.

`lamb kb files` does not exist in the AAC shell. If a command returns "Unknown command", read its supported-command suggestions or run `lamb help`, then use a supported command. Do not ask the user to approve or repeat the nonexistent command. These inspection commands are reads and do not need write confirmation. Do not create or ingest anything just to inspect a KB, including after the user cancelled a UI upload.

When an unsupported command is rejected, report that it was rejected before execution. Do not describe the failed attempt as a successfully executed command. The following supported read can proceed in the same session.
