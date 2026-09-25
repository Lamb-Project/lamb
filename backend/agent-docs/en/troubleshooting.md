<a id="overview"></a>
# Troubleshooting

Begin with the observed symptom, inspect the relevant configuration and gather direct evidence. Distinguish a test result from a hypothesis about its cause.

<a id="problem-assistant-ignores-my-documents"></a>
## Problem: Assistant ignores my documents

**Symptoms:** The assistant answers from general knowledge, not your uploaded documents.

**Check these in order:**
1. Is a RAG Processor selected? (Edit assistant > RAG Processor must NOT be "No Rag")
2. Is a Knowledge Base connected? (Edit assistant > check the KB checkbox)
3. Does the prompt template contain `{context}`? Without it, retrieved content is discarded.
4. Run a bypass/debug test — if `{context}` is empty, investigate retrieval, filters and prompt assembly before attributing a cause.
5. Are the files in the KB fully ingested? (View KB > check status is "completed")

<a id="problem-context-is-empty-in-bypass-test"></a>
## Problem: Context is empty in bypass test

**Symptoms:** You run `Debug` or bypass and the `{context}` area is empty.

**Causes:**
- Knowledge Base has no files or files are still processing
- Wrong KB is connected to the assistant (check the checkbox in Edit)
- RAG Processor is set to "No Rag"
- The KB collection ID is misconfigured

**Fix:** View the KB > Query tab > search for a term you know exists. If no results, the KB needs files or reingestion.

<a id="problem-assistant-hallucinates-gives-wrong-answers"></a>
## Problem: Assistant hallucinates / gives wrong answers

**Causes:**
- No KB connected (assistant uses training data only)
- RAG Top K too low (set to 1 — may miss relevant chunks)
- Document quality poor (badly formatted, too much noise)
- System prompt too vague

**Fix:** Connect a good KB, set RAG Top K to 3-5, improve system prompt with explicit instructions to use provided context.

<a id="problem-can-t-see-the-share-tab"></a>
## Problem: Can't see the Share tab

**Cause:** Sharing is disabled at the organization level.

**Fix:** Ask your organization admin to enable sharing in the org settings.

<a id="problem-students-can-t-access-the-assistant"></a>
## Problem: Students can't access the assistant

**Check:**
1. Is the assistant Published? (Properties page > status must show "Published")
2. Is the LTI configuration correct in Moodle? (Tool URL, Consumer Key, Secret)
3. Is the LTI secret correct? Ask your LAMB admin for the value.
4. For Unified LTI: has an instructor configured the activity? (Students see "not set up yet" until configured)

<a id="problem-can-t-publish-an-assistant"></a>
## Problem: Can't publish an assistant

**Cause:** Only the assistant owner can publish. If you're a shared user, you can view but not publish.

<a id="problem-test-runs-consume-too-many-tokens"></a>
## Problem: Test runs consume too many tokens

**Fix:** Always run Debug All (bypass) first — it's free. Only run real tests after verifying the pipeline works correctly.
