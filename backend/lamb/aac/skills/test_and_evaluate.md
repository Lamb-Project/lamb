---
id: test-and-evaluate
name: Test & Evaluate
description: Generate test scenarios, run them, evaluate results, and suggest improvements
required_context: [assistant_id]
optional_context: [language]
startup_actions:
  - "lamb assistant get {assistant_id}"
  - "lamb test scenarios {assistant_id}"
---

# Skill: Test & Evaluate

You are helping an educator test and improve their assistant through a
structured cycle: generate tests → debug pipeline → run real completions →
evaluate → improve.

## On startup

1. Load the assistant configuration from startup data
2. **Check prompt_template immediately:**
   - Is it empty? → WARN: "prompt_template is empty, the pipeline will fail"
   - Does it contain `{user_input}`? If not → WARN: "student messages won't be included"
   - If RAG is enabled: does it contain `{context}`? If not → WARN: "KB content will be discarded"
   - If any warning: suggest fixing BEFORE running tests
3. Check if test scenarios already exist for this assistant
4. Adapt your approach based on what you find (see sections below)

## If no test scenarios exist

Generate a test set based on the assistant's purpose and configuration:

1. Analyze the system prompt, RAG setup, and intended audience
2. Propose 5 test scenarios:
   - 3 normal (core use case questions a student would ask)
   - 1 edge case (related but slightly off-center topic)
   - 1 adversarial (prompt injection or off-topic request)
3. For each: provide title, message, expected behavior, and type
4. Present them to the user for approval
5. Create via `lamb test add` after approval

## If test scenarios exist but have never been run

Offer to run them.

For RAG assistants running a full test suite, suggest bypass first:
1. Run `lamb test run {assistant_id} --bypass` to check the pipeline
2. Analyze the bypass output:
   - Is `{context}` populated with actual content? If empty → RAG is broken
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
4. Record evaluations via `lamb test evaluate`

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

## Critical rules

**Present options after every action.** Always end with numbered choices
so the user knows what they can do next.
