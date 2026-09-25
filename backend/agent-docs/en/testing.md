<a id="overview"></a>

For verified 0.7 UI steps and screenshots, read `lamb docs read ui-testing`. Prefer that guide for button locations and user-operated actions.


<a id="direct-chat"></a>
## Direct Chat

Click the "Chat with [name]" tab on the assistant detail page. Type messages and see responses. Quick way to check behavior.

<a id="debug-mode-bypass"></a>
## Debug Mode (Bypass)

Shows exactly what the AI model would receive — full system prompt, retrieved KB content, assembled prompt — without calling the model. No completion-model call; retrieval may still involve other services.

Use bypass to verify:
- Is `{context}` populated with relevant content? If empty, report the observation and investigate retrieval, filters and prompt assembly; the cause is not yet established.
- Is the prompt template correctly assembled?
- Are the right KB documents being retrieved?

**Use bypass when inspecting prompt/context assembly** to avoid wasting tokens on a broken pipeline.

<a id="test-scenarios"></a>
## Test Cases

The Tests tab lets you create structured test cases and run them systematically.

### Creating test cases

Click + Add test case:
- **Title** — descriptive name (e.g., "Basic question about topic X")
- **Type** — Normal, Multi-turn, or Adversarial
- **Message** — the test question
- **Expected behavior** — what a good response should include

### Running Tests

| Action | What it does | Cost |
|--------|-------------|------|
| **Run** (single) | Run one test case with real LLM | Tokens |
| **Debug** (single) | Run one test case in bypass | Free |
| **Run All** | Run all test cases with real LLM | Tokens |
| **Debug All (bypass)** | Run all test cases in bypass | Free |
| **Test & Evaluate with Agent** | AI agent generates, runs, evaluates tests | Tokens |

### Evaluating Results

Each test run shows: model used, date, token count, response time.
Click a run to see the full response. Click Evaluate to record:
- **Good** (thumbs up) — response meets expectations
- **Bad** (thumbs down) — response is wrong or inadequate
- **Mixed** — partially good

### Recommended Workflow

1. Create 3-5 test cases (normal + edge + adversarial)
2. Run Debug All (bypass) — verify the pipeline
3. Fix any issues (missing context, wrong KB, bad template)
4. Run All with real LLM
5. Evaluate each result
6. Iterate: adjust system prompt or KB, re-test
