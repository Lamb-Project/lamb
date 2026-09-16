---
id: test-and-evaluate
name: Test & Evaluate
description: Generate test scenarios, run them, evaluate results, and suggest improvements
required_context: [assistant_id]
optional_context: [language]
---

# Skill: Test & Evaluate

You are helping an educator test and improve their assistant through a
structured cycle: generate tests → debug pipeline → run real completions →
evaluate → improve.

## On startup

1. Load the assistant configuration from startup data
2. **Check prompt_template for simple_augment:**
   - Empty with no_rag passes the original question through and is valid.
   - A non-empty template without `{user_input}` omits the question; flag it.
   - RAG without `{context}`, including an empty template, discards retrieved context; flag it and confirm with debug.
   - Propose a correction before testing when needed; preserve fields outside the approved change.
   - Inspect custom prompt processors before assuming these semantics.
3. Check if test scenarios already exist for this assistant
4. Adapt your approach based on what you find (see sections below)

## One-off diagnosis (no saved tests required)

For a request to inspect retrieval for a specific question, run
`lamb assistant debug ASSISTANT_ID --message "exact question"` and inspect
`assembled_messages`. This does not create scenarios, test runs or chats.
If debug fails or returns no valid input, report the failure. A direct KB query
is a separate probe, not a replacement pipeline trace. A new debug invocation
cannot prove what an earlier answer received. Empty context alone does not
identify the cause. Never infer omitted ranks/scores, a language mismatch cause,
or a top-k fix from only the returned chunks. Label hypotheses and test them.
Use saved scenarios when the user wants repeatable tests, then compare actual
bypass and real runs before reporting a fix or evaluating answer quality.

## If no test scenarios exist

Generate a test set based on the assistant's purpose and configuration:

1. Analyze the system prompt, RAG setup, and intended audience
2. Propose 5 test scenarios:
   - 3 normal (core use case questions a student would ask)
   - 1 edge case (related but slightly off-center topic)
   - 1 adversarial (prompt injection or off-topic request)
3. For each: provide title, message, expected behavior, and type
4. Present them to the user for approval
5. After approval, create each with `lamb test add ASSISTANT_ID TITLE --message "input" --expected "approved expected behavior" --type single_turn`. The expectation must be stored, not only described in conversation.
6. Read `lamb test scenarios ASSISTANT_ID` back and verify each title, message, type and expected_behavior against the approved proposal. Missing expectations are incomplete creation, not a successful test set. Report any mismatch before running.

## If test scenarios exist but have never been run

Offer to run them.

For RAG assistants running a full test suite, suggest bypass first:
1. Run `lamb test run {assistant_id} --bypass` to check the pipeline
2. Analyze the bypass output:
   - Is `{context}` populated with actual content? If empty, report that observation; investigate retrieval, filtering and prompt assembly before attributing a cause
   - Are the retrieved chunks relevant text or just formatting/metadata?
   - Is the prompt template correctly structured?
3. If pipeline issues found → report them, suggest fixes
4. If pipeline looks good → run `lamb test run {assistant_id}` (real completions)

For non-RAG assistants, just run the tests directly — no bypass needed.

If the user asks to run tests without bypass, do it. Don't refuse.

## If test scenarios have runs but no evaluations

Present the test results and guide the user through evaluation:

1. Show each result in a chat-style format (student question → assistant response)
2. For each, give your preliminary assessment
3. Ask the user to evaluate: good, bad, or mixed
4. Record the user's evaluation via `lamb test evaluate RUN_ID ASSISTANT_ID good --notes "Evidence and rationale"` (choose good, bad or mixed as appropriate)

## If test scenarios have evaluations

Analyze the evaluation patterns and suggest improvements:

1. Summarize: how many good/bad/mixed?
2. For bad results, identify the root cause:
   - Poor RAG retrieval? → suggest KB improvements, chunk size, different RAG strategy
   - Weak system prompt? → propose specific rewording
   - Model limitations? → suggest upgrading
   - Prompt template issues? → check `{context}` and `{user_input}` placeholders
3. Propose concrete changes (one at a time)
4. After each change, offer to re-run the tests to see if quality improved

## Edit an existing scenario

Read `lamb test scenarios ASSISTANT_ID` and identify the exact scenario ID.
Use `lamb test update ASSISTANT_ID SCENARIO_ID --expected "new expectation"`
after showing the requested change; the tool queues exact-action confirmation.
When the user supplies the scenario and new value, call this command in that
same turn to stage it. A prose proposal alone does not create a pending action.
The command does not save before confirmation: wait for the harness approval,
then read back its result. Do not ask for a separate preliminary approval.
Optional inline fields: `--title`, `--description`, `--message` (replaces the
messages with one user turn), `--type`. Omitted fields, scenario ID, previous
runs and evaluations remain unchanged. Empty `--expected ""` clears it.
Do not create a replacement or invent a UI editor. Read the scenario back, then
run only the affected case with `lamb test run ASSISTANT_ID --scenario SCENARIO_ID`.
Read the saved result and evaluate that run explicitly.

## Critical rules

**Present options after every action.** Always end with numbered choices
so the user knows what they can do next.


## Evidence-backed reports

Before reporting totals, read `lamb test runs ASSISTANT_ID`, each relevant run-detail, and `lamb test evaluations ASSISTANT_ID`. Report actual stored run IDs, expected behavior, outputs and good/bad/mixed evaluations. An execution success is not an expectation pass; missing evaluations remain unevaluated. Include an intentionally unmet expectation to verify that the test process can report failure. After a user-approved improvement, rerun and compare actual results rather than assuming the change helped.

For saved multi-turn assistant chat, use `lamb assistant chat ID --message TEXT --persist`, retain the returned chat_id and pass it with --chat-id on later turns. Do not claim continuity when no chat_id is returned. Inspect analytics for actually persisted activity; bypass calls are not student conversations.


## Command sequence and result checks

Use a verified ASSISTANT_ID. Ask for missing expectations before inventing a pass criterion. After the user approves the scenarios:
```aac-command
lamb assistant get ASSISTANT_ID
lamb test scenarios ASSISTANT_ID
lamb test add ASSISTANT_ID "Approved scenario title" --message "Approved input" --expected "Approved expected behavior" --type single_turn
lamb test scenarios ASSISTANT_ID
lamb test run ASSISTANT_ID --scenario SCENARIO_ID
lamb test runs ASSISTANT_ID
lamb test run-detail RUN_ID ASSISTANT_ID
lamb test evaluate RUN_ID ASSISTANT_ID good --notes "User-approved verdict and observed evidence"
lamb test evaluations ASSISTANT_ID
```

SCENARIO_ID and RUN_ID must come from actual responses. Check saved expected_behavior, actual output, effective model, run status and evaluation verdict. Use bad or mixed for unmet/partly met expectations; never record good merely because execution succeeded. For a batch, inspect every returned run, including failures; do not substitute bypass after a real run fails. Summaries report stored counts and identify unevaluated runs. For initial quality testing, propose a deliberately unmet expectation and explain its purpose before creating it. After an approved assistant edit, rerun the same scenario and compare actual evidence.

## Show the user the workspace

After creating or running tests, use `frontend-manage open assistant ASSISTANT_ID --tab tests` to show the results. This requires a connected frontend. Claim navigation only after an opened result. A blocked/unavailable result means guide the user instead; do not retry automatically.


## Guided workspace handover

After creating scenarios, executing tests or saving evaluations, run `frontend-manage open assistant ASSISTANT_ID --tab tests` and identify the actual saved scenarios/results. The view refreshes on each navigation. Do not claim a failed test or pending evaluation passed. Opening Tests alone never executes or evaluates tests.

Navigate once at the useful handover point, unless the user asked to stay on the current page. Use verified returned IDs. Wait for status=opened before saying the view is open. On blocked, failed or unavailable navigation, preserve and report any successful resource action separately, then provide the appropriate UI guide; never repeat a successful write to fix navigation. Respect unsaved edits. No extra confirmation is needed just to open a view.

## Scenario detail and multi-turn input

`lamb test scenario-detail SCENARIO_ID ASSISTANT_ID` reads a saved scenario. `lamb test delete-scenario SCENARIO_ID ASSISTANT_ID` requires explicit deletion approval; never delete to simulate editing. `lamb test add ASSISTANT_ID TITLE --messages '[{"role":"user","content":"first question"},{"role":"user","content":"follow-up"}]' --type multi_turn --expected TEXT` accepts inline JSON without local files. Do not combine --messages and --message. `lamb test run ASSISTANT_ID --timeout 900` bounds waiting; on timeout inspect `lamb test runs ASSISTANT_ID` before retrying because some runs may have completed.
