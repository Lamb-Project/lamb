---
id: chat-with-assistant
name: Chat with Assistant
description: Run real assistant conversations, preserve chat history and verify behavior
required_context: [assistant_id]
optional_context: [language]
---

Use a verified assistant ID from the selected resource or assistant list. Read its purpose first. Ask for the user's message if missing; do not replace it with a benchmark. Replace uppercase placeholders with actual returned IDs and user text.

```aac-command
lamb assistant get ASSISTANT_ID
lamb assistant chat ASSISTANT_ID --message "User's first question" --persist
lamb assistant chat ASSISTANT_ID --message "User's follow-up question" --persist --chat-id CHAT_ID
```

Keep the returned chat_id and reuse it for follow-ups, including a third turn requiring earlier context. Never invent a chat ID or claim continuity without a returned saved ID. A normal direct chat without --persist may not appear in student activity. Read real returned answer and effective model when supplied. Report errors, timeouts or unavailable model configuration; bypass is not an answer. A saved unavailable model preference can resolve through the owner organization's configured fallback.

Only continue a chat the caller is allowed to continue; a shared assistant does not authorize appending to another person's chat. A 404/403 is not permission to use a guessed ID. Offer a new conversation when appropriate. For an improvement activate improve-assistant; for a saved quality evaluation activate test-and-evaluate. Before/after comparisons must use the same representative question and report observed differences.


## Guided workspace handover

When the user wants to try the assistant in the UI, run `frontend-manage open assistant ASSISTANT_ID --tab chat`. Opening chat does not send a message. After an AAC-run chat, offer this view for the user to try it; do not claim the frontend has loaded the CLI conversation or its chat_id.

At completion, expose the verified destination through lamb plan finish --resource TYPE --id ID --tab TAB, or the saved report. The Show me button navigates only when clicked and respects unsaved edits. Use frontend-manage open only when the user explicitly asks to open a view now; wait for status=opened before claiming it opened. A failed navigation never justifies repeating a successful write.


## System prompt filters

Random filters resolve {{RANDOM:minimum-maximum}} in the system prompt once at conversation start. Values remain fixed across turns, reloads and forks. Preview with `lamb assistant preview-filters ASSISTANT_ID`: this is a sample only, with no model call or saved realization. For a saved interview, use `lamb assistant chat ASSISTANT_ID --message "Hello" --persist` and reuse its --chat-id with --persist for follow-ups. Stateless debug and saved tests initialize temporary context and support enabled filters without saved chat IDs. Use create-assistant or improve-assistant to configure filters through normal application approval, or Advanced Mode > Prompt filters in the UI. Configuration edits affect new conversations. Privacy sanitization is not implemented.
