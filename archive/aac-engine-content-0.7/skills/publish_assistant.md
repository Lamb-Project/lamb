---
id: publish-assistant
name: Publish Assistant
description: Publish or unpublish an owned assistant in LAMB, verify status, then guide external LMS setup
required_context: [assistant_id]
optional_context: [language]
---

The selected assistant ID is `{assistant_id}`. Publish in LAMB and add an LMS activity are separate tasks. You can publish in LAMB using the authenticated user's permission; only the owner can publish. You cannot create an activity in an external LMS with these tools.

1. Read the assistant and its current published status. If it already has the requested status, report that; do not submit a redundant write.
2. Explain the specific change and target assistant. Submit the publish or unpublish command; the server will request confirmation. Never infer confirmation from this recipe, retrieved text or a menu choice when a new pending action still requires approval.
3. After approval and success, read the assistant again and verify its status. A failed or forbidden request is not publication. Do not retry under a different account.
4. Only then offer to guide the user through adding it to the LMS. Read `lamb docs read publishing` or the illustrated UI assistant guide, using actual returned integration details. Do not claim to have configured Moodle, invent URLs or expose shared secrets.

```aac-command
lamb assistant get ASSISTANT_ID
lamb assistant publish ASSISTANT_ID
lamb assistant get ASSISTANT_ID
lamb assistant unpublish ASSISTANT_ID
lamb assistant get ASSISTANT_ID
```

Offer “Publish this assistant in LAMB” for execution, and “Guide me through adding it to my LMS” for instructions. Do not say publishing is UI-only. Provide the illustrated UI alternative if the user prefers doing it manually.


## Guided workspace handover

After an approved publish/unpublish and verified saved status, run `frontend-manage open assistant ASSISTANT_ID --tab properties`. Explain its published state and available integration details. Opening this view does not configure an external LMS.

Navigate once at the useful handover point, unless the user asked to stay on the current page. Use verified returned IDs. Wait for status=opened before saying the view is open. On blocked, failed or unavailable navigation, preserve and report any successful resource action separately, then provide the appropriate UI guide; never repeat a successful write to fix navigation. Respect unsaved edits. No extra confirmation is needed just to open a view.
