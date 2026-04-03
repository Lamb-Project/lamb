---
topic: testing
covers: [chat, bypass, debug, test-scenarios, run, evaluate, tokens, pipeline-verification]
answers:
  - "how do I test my assistant"
  - "what is bypass mode"
  - "what is debug mode"
  - "how do I create test scenarios"
  - "how do I run tests"
  - "how do I evaluate test results"
  - "how do I verify RAG is working"
  - "how much do tests cost"
---

## Direct Chat

Click the "Chat with [name]" tab on the assistant detail page. Type messages and see responses. Quick way to check behavior.

## Debug Mode (Bypass)

Shows exactly what the AI model would receive — full system prompt, retrieved KB content, assembled prompt — without calling the model. **Zero token cost.**

Use bypass to verify:
- Is `{context}` populated with relevant content? If empty, RAG is broken.
- Is the prompt template correctly assembled?
- Are the right KB documents being retrieved?

**Always run bypass before real tests** to avoid wasting tokens on a broken pipeline.

## Test Scenarios

The Tests tab lets you create structured test cases and run them systematically.

### Creating Scenarios

Click + Add Scenario:
- **Title** — descriptive name (e.g., "Basic question about topic X")
- **Type** — Normal, Edge case, or Adversarial
- **Message** — the test question
- **Expected behavior** — what a good response should include

### Running Tests

| Action | What it does | Cost |
|--------|-------------|------|
| **Run** (single) | Run one scenario with real LLM | Tokens |
| **Debug** (single) | Run one scenario in bypass | Free |
| **Run All** | Run all scenarios with real LLM | Tokens |
| **Debug All (bypass)** | Run all scenarios in bypass | Free |
| **Test & Evaluate with Agent** | AI agent generates, runs, evaluates tests | Tokens |

### Evaluating Results

Each test run shows: model used, date, token count, response time.
Click a run to see the full response. Click Evaluate to record:
- **Good** (thumbs up) — response meets expectations
- **Bad** (thumbs down) — response is wrong or inadequate
- **Mixed** — partially good

### Recommended Workflow

1. Create 3-5 test scenarios (normal + edge + adversarial)
2. Run Debug All (bypass) — verify the pipeline
3. Fix any issues (missing context, wrong KB, bad template)
4. Run All with real LLM
5. Evaluate each result
6. Iterate: adjust system prompt or KB, re-test
