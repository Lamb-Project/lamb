---
id: test-and-evaluate
name: Test & Evaluate
description: Generate test cases, run them, evaluate results, and suggest improvements
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
3. Check if test cases already exist for this assistant
4. Adapt your approach based on what you find (see sections below)

## One-off diagnosis (no saved tests required)

For a request to inspect retrieval for a specific question, run
`lamb assistant debug ASSISTANT_ID --message "exact question"` and inspect
`assembled_messages`. This does not create test cases, test runs or chats.
If debug fails or returns no valid input, report the failure. A direct KB query
is a separate probe, not a replacement pipeline trace. A new debug invocation
cannot prove what an earlier answer received. Empty context alone does not
identify the cause. Never infer omitted ranks/scores, a language mismatch cause,
or a top-k fix from only the returned chunks. Label hypotheses and test them.
Use saved test cases when the user wants repeatable tests, then compare actual
bypass and real runs before reporting a fix or evaluating answer quality.

## If no test cases exist

Generate a test set based on the assistant's purpose and configuration:

1. Analyze the system prompt, RAG setup, and intended audience
2. Propose 5 test cases:
   - 3 normal (core use case questions a student would ask)
   - 1 edge case (related but slightly off-center topic)
   - 1 adversarial (prompt injection or off-topic request)
3. For each: provide title, message, expected behavior, and type
4. In Auto, include creation and execution of the cases in one concrete plan, with their expectations and the analysis/report steps. The application asks once because this saves resources.
5. After approval, execute the plan. Its creation commands use `lamb test add ASSISTANT_ID TITLE --message "input" --expected "approved expected behavior" --type single_turn`. The expectation must be stored, not only described in conversation.
6. Read `lamb test cases ASSISTANT_ID` back and verify each title, message, type and expected_behavior against the approved proposal. Missing expectations are incomplete creation, not a successful test set. Report any mismatch before running.

## If test cases exist but have never been run

When running them is already requested, include their verified IDs in the plan and run them after its one approval. Do not offer the already-requested work back as a choice.

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

## If test cases have runs but no evaluations

Present and evaluate the actual test results:

1. Show each result in a chat-style format (student question → assistant response)
2. For each, give your preliminary assessment
3. In Auto, evaluate each result against its stored expectation and explain your reasoning. Do not require a human verdict to complete the requested workflow. Human review remains optional.
4. Record your LEGATUS evaluation via `lamb test evaluate RUN_ID ASSISTANT_ID good --notes "Evidence and rationale"` (choose good, bad or mixed as appropriate)

## If test cases have evaluations

Analyze the evaluation patterns and suggest improvements:

1. Summarize: how many good/bad/mixed?
2. For bad results, identify the root cause:
   - Poor RAG retrieval? → suggest KB improvements, chunk size, different RAG strategy
   - Weak system prompt? → propose specific rewording
   - Model limitations? → suggest upgrading
   - Prompt template issues? → check `{context}` and `{user_input}` placeholders
3. Propose concrete changes. Apply only changes already covered by the user-approved plan; otherwise prepare one extension.
4. Run the affected cases when rerunning is part of the request or approved branch. Compare actual outputs without another menu.

## Edit an existing test case

Read `lamb test cases ASSISTANT_ID` and identify the exact test case ID.
Use `lamb test update ASSISTANT_ID CASE_ID --expected "new expectation"`
after showing the requested change; the tool queues exact-action confirmation.
When the user supplies the test case and new value, call this command in that
same turn to stage it. A prose proposal alone does not create a pending action.
The command does not save before confirmation: wait for the harness approval,
then read back its result. Do not ask for a separate preliminary approval.
Optional inline fields: `--title`, `--description`, `--message` (replaces the
messages with one user turn), `--type`. Omitted fields, test case ID, previous
runs and evaluations remain unchanged. Empty `--expected ""` clears it.
Do not create a replacement or invent a UI editor. Read the test case back, then
run only the affected case with `lamb test run ASSISTANT_ID --case CASE_ID`.
Read the saved result and evaluate that run explicitly.

## Critical rules

**Finish the requested workflow.** Progress updates never require a reply. Optional next-step suggestions belong only after the request is satisfied.


## Evidence-backed reports

Before reporting totals, read `lamb test runs ASSISTANT_ID`, each relevant run-detail, and `lamb test evaluations ASSISTANT_ID`. Report actual stored run IDs, expected behavior, outputs and good/bad/mixed evaluations. An execution success is not an expectation pass; missing evaluations remain unevaluated. Include an intentionally unmet expectation to verify that the test process can report failure. After a user-approved improvement, rerun and compare actual results rather than assuming the change helped.

For saved multi-turn assistant chat, use `lamb assistant chat ID --message TEXT --persist`, retain the returned chat_id and pass it with --chat-id on later turns. Do not claim continuity when no chat_id is returned. Inspect analytics for actually persisted activity; bypass calls are not student conversations.


## Command sequence and result checks

Use a verified ASSISTANT_ID. Derive and disclose reasonable expectations from the purpose and instructions. Ask only if a missing pedagogical decision materially changes what success means. After the user approves the test cases:
```aac-command
lamb assistant get ASSISTANT_ID
lamb test cases ASSISTANT_ID
lamb test add ASSISTANT_ID "Approved test case title" --message "Approved input" --expected "Approved expected behavior" --type single_turn
lamb test cases ASSISTANT_ID
lamb test run ASSISTANT_ID --case CASE_ID
lamb test runs ASSISTANT_ID
lamb test run-detail RUN_ID ASSISTANT_ID
lamb test evaluate RUN_ID ASSISTANT_ID good --notes "LEGATUS verdict and observed evidence"
lamb test evaluations ASSISTANT_ID
```

CASE_ID and RUN_ID must come from actual responses. Check saved expected_behavior, actual output, effective model, run status and evaluation verdict. Use bad or mixed for unmet/partly met expectations; never record good merely because execution succeeded. For a batch, inspect every returned run, including failures; do not substitute bypass after a real run fails. Summaries report stored counts and identify unevaluated runs. For initial quality testing, propose a deliberately unmet expectation and explain its purpose before creating it. After an approved assistant edit, rerun the same test case and compare actual evidence.

## Show the user the workspace

After creating or running tests, use `frontend-manage open assistant ASSISTANT_ID --tab tests` to show the results. This requires a connected frontend. Claim navigation only after an opened result. A blocked/unavailable result means guide the user instead; do not retry automatically.


## Guided workspace handover

For Auto, save the requested report and finish; the application provides Show me and Test results buttons without moving the workspace. For an explicit navigation request use `frontend-manage open assistant ASSISTANT_ID --tab tests` and identify the actual saved test cases/results. The view refreshes on each navigation. Do not claim a failed test or pending evaluation passed. Opening Tests alone never executes or evaluates tests.

At completion, expose the verified destination through lamb plan finish --resource TYPE --id ID --tab TAB, or the saved report. The Show me button navigates only when clicked and respects unsaved edits. Use frontend-manage open only when the user explicitly asks to open a view now; wait for status=opened before claiming it opened. A failed navigation never justifies repeating a successful write.

## Test case detail and multi-turn input

`lamb test case-detail CASE_ID ASSISTANT_ID` reads a saved test case. `lamb test delete-case CASE_ID ASSISTANT_ID` requires explicit deletion approval; never delete to simulate editing. `lamb test add ASSISTANT_ID TITLE --messages '[{"role":"user","content":"first question"},{"role":"user","content":"follow-up"}]' --type multi_turn --expected TEXT` accepts inline JSON without local files. Do not combine --messages and --message. `lamb test run ASSISTANT_ID --timeout 900` bounds waiting; on timeout inspect `lamb test runs ASSISTANT_ID` before retrying because some runs may have completed.


## System prompt filters

Random filters resolve {{RANDOM:minimum-maximum}} in the system prompt once at conversation start. Values remain fixed across turns, reloads and forks. Preview with `lamb assistant preview-filters ASSISTANT_ID`: this is a sample only, with no model call or saved realization. Use `lamb assistant chat ASSISTANT_ID --message "Hello" --persist` for a saved interview; reuse its --chat-id and --persist for follow-ups. Stateless debug and saved tests initialize temporary context and support enabled filters without saved chat IDs. Use create-assistant or improve-assistant to configure filters through normal application approval, or Advanced Mode > Prompt filters in the UI. Configuration edits affect new conversations. Privacy sanitization is not implemented.


## Conversation initialization

Saved evaluations initialize the assistant system prompt, including conversation-start random filters, in temporary context without creating a chat. A fixture containing several turns is one fresh evaluation case. Normal persisted chats retain their initialized prompt across turns; teacher edits apply to new conversations. Do not confuse a prompt preview with a model test.


## Auto plan example

After reading assistant 7 and discovering that a useful new case is needed, prepare all case data and execution at once. Adapt IDs, content and counts to the actual task:

```aac-command
lamb plan prepare --json '{"title":"Test assistant 7 and report","steps":[{"id":"normal","title":"Create a normal-use case","command":"lamb test add 7 Normal --message \"Explain photosynthesis\" --expected \"Explain light, water and carbon dioxide in age-appropriate language\""},{"id":"run_normal","title":"Run the normal-use case","command":"lamb test run 7 --case @normal.id","after":"normal"}],"assistant_calls":10,"tool_estimate":12,"evaluate":true,"report":{"title":"Assistant test report","assistant_id":"7"}}'
```

After approval, call `lamb plan execute`. Each test run must use a specific --case, including @step.id for cases created in the plan. A saved multi-turn fixture is one completion on its supplied history, not a simulation with one model call per supplied message. A retry must be an explicit additional step/branch and count toward the allowance.

Read each returned run. Use its verified IDs with `lamb test evaluate RUN_ID ASSISTANT_ID good --notes "Observed evidence and rationale"`, choosing good, bad or mixed honestly. These are LEGATUS evaluations, not human confirmations. Save a report that distinguishes execution errors, unmet expectations, hypotheses and verified causes with `lamb report save --content "Report with actual cases, run IDs, verdicts, evidence and limitations"`, then `lamb plan finish`. Do not ask the teacher to grade every answer, choose the next already-approved step, or confirm continuation.
