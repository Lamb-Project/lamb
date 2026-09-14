---
id: inspect-activity
name: Inspect Assistant Activity
description: Read persisted chats, chat details, statistics and dated activity timelines
required_context: [assistant_id]
optional_context: [language]
---

The selected assistant ID is `{assistant_id}`. Use that ID for ASSISTANT_ID below. Do not ask the user to select it again or list assistants unless the user requests a different assistant. Ask for the intended period if needed. These are read commands; never generate chats to make a report look populated.

```aac-command
lamb assistant get ASSISTANT_ID
lamb analytics stats ASSISTANT_ID
lamb analytics timeline ASSISTANT_ID --period day
lamb analytics chats ASSISTANT_ID --page 1 --per-page 20
lamb analytics chat-detail ASSISTANT_ID CHAT_ID
```

Read returned chat IDs before requesting details. Optional filters supported by stats/timeline: --start-date and --end-date. Chats additionally support --user-id, --search, --page and --per-page. Use the same date bounds for comparable counts. Timeline period is day, week or month. Page through chats when a complete list is requested, stopping at an empty/short page; never report one page length as the total. Prefer returned statistics for totals and explain differences in scope.

Report actual counts, time range, saved messages and what those establish. Empty activity is not a failed assistant. A direct AAC completion or debug/bypass call need not produce student analytics; persisted student chats or --persist chats are distinct. State missing activity or inaccessible records accurately. Do not circumvent forbidden/foreign access by trying alternative users or identifiers. For real conversation activate chat-with-assistant; for test results activate test-and-evaluate, since test runs are not student chats.


## Guided workspace handover

After inspecting activity, run `frontend-manage open assistant ASSISTANT_ID --tab activity`. Explain actual returned counts and date ranges; this navigation opens the Activity view with its default filters, not necessarily the filters used in your commands.

Navigate once at the useful handover point, unless the user asked to stay on the current page. Use verified returned IDs. Wait for status=opened before saying the view is open. On blocked, failed or unavailable navigation, preserve and report any successful resource action separately, then provide the appropriate UI guide; never repeat a successful write to fix navigation. Respect unsaved edits. No extra confirmation is needed just to open a view.
