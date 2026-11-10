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

Navigate once at the useful handover point, unless the user asked to stay on the current page. Use verified returned IDs. Wait for status=opened before saying the view is open. On blocked, failed or unavailable navigation, preserve and report any successful resource action separately, then provide the appropriate UI guide; never repeat a successful write to fix navigation. Respect unsaved edits. No extra confirmation is needed just to open a view.
