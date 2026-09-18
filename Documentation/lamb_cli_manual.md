
### Learning scenarios (AAC, 0.7)

A learning scenario is optional, personal teaching context shared across AAC conversations. It is distinct from an assistant test case. Use inline text; none of these commands requires a local file.

```bash
lamb learning-scenario create "Introduction to attention" --content "Learners: beginners. Goal: explain Q, K and V."
lamb learning-scenario list
lamb learning-scenario get SCENARIO_UUID
lamb learning-scenario update SCENARIO_UUID --revision 1 --content "Revised goals"
lamb learning-scenario duplicate SCENARIO_UUID --title "Another course"
lamb learning-scenario default SCENARIO_UUID
lamb aac start --scenario default
lamb aac start --scenario SCENARIO_UUID
lamb aac start --scenario none
lamb learning-scenario selected SESSION_UUID
lamb learning-scenario select SESSION_UUID none
lamb learning-scenario remove SCENARIO_UUID --revision 2
lamb learning-scenario default none
```

Commands return JSON. Read the current revision before updating or removing; stale revisions return a conflict and require review. Duplication creates an independent document. Removal archives the document, clears its default selection, and preserves historical conversations. Changing the default does not change existing conversations. Selecting context requires an idle session without a pending approval. AAC applies changed context once on the next eligible turn, preserving conversation history.

Omitting `--scenario` starts empty. The frontend new-conversation picker offers Empty, Default (when configured), or a saved scenario. AAC writes require approval of the proposed command. The authenticated API keeps file paths out of the command contract; Library-backed storage is planned for 1.0-alpha (#484).

## Assistant test cases

A learning scenario describes creator context. A test case stores an assistant input and expected behaviour; a test run records its execution. Use `lamb test cases ASSISTANT_ID`, `lamb test case-detail CASE_ID ASSISTANT_ID`, `lamb test delete-case CASE_ID ASSISTANT_ID`, and `lamb test run ASSISTANT_ID --case CASE_ID`. Create and update remain `lamb test add` and `lamb test update`. The old `scenarios`, `scenario-detail`, `delete-scenario` commands and `--scenario` option remain compatibility aliases. Existing saved IDs, API paths and JSON fields are unchanged.
