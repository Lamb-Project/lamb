---
id: manage-knowledge-base
name: Manage Knowledge Base
description: Create knowledge bases, ingest attached files and verify retrieval
required_context: []
optional_context: [language]
startup_actions:
  - "lamb kb list"
---

Help the user create and populate a knowledge base. Ask for the intended source and purpose, then use `lamb kb create NAME --description TEXT`. Creation requires user approval.

For frontend users who need to supply local files, read `lamb docs read ui-knowledge-bases` and guide them through the existing Knowledge Bases UI. The user opens the file picker, selects the file and presses Upload File. Display the documented screenshot when useful or requested, using its exact Markdown URL. Do not replace this tutorial with an AAC attachment request or ask for a local path. Wait for the user's response, then verify status/retrieval with read tools if the KB is known. Do not execute a write merely because you are explaining its steps.

For an explicit CLI workflow, `lamb aac attach LOCAL_FILE` stages the user's file. Only when an actual owned reference is already supplied and ingestion by the agent is explicitly requested, use `lamb kb upload KB_ID REFERENCE` with approval. Never invent a reference or read an arbitrary server path.

For PDFs use `--plugin markitdown_ingest`; for UTF-8 text/Markdown use `--plugin simple_ingest`. If the service reports the plugin unavailable, report the actual failure. Do not substitute a placeholder or retyped summary for the user's file.

Submission alone is not completed ingestion. Inspect `lamb kb jobs KB_ID`, `lamb kb status KB_ID` and `lamb kb get KB_ID` and query a distinctive fact with `lamb kb query KB_ID "question" --top-k 3`. Check source identity and actual retrieved text. Report empty/pending/error results accurately; do not loop indefinitely. Suggest a retry only after identifying the cause.

For a KB-backed assistant use simple_rag or context_aware_rag with explicit collection IDs and a prompt template containing {user_input} and {context}. Single-file RAG is different: it binds one owned UTF-8 upload through --file-path; PDFs must first be ingested into a KB.
