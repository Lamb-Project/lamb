<a id="design-evidence"></a>
# Testing as design

Write expected behavior before running a test. Include a normal learning question,
a question requiring source grounding, an ambiguous follow-up and an out-of-scope or
misleading request. Expectations should be observable: uses the relevant passage,
asks a useful clarification, or admits missing evidence. Avoid grading fluency alone.
A bypass/debug invocation inspects newly assembled input. It does not evaluate the final
answer, and a raw KB query is a separate probe. Saved test cases make comparisons
repeatable; retain their IDs, expected behavior and actual runs. Run real completions
and evaluate against the expectation. A successful HTTP request is not a passed test.
If a change is proposed, keep the test case fixed, rerun and compare evidence. Include
an intentionally unmet expectation when checking that the evaluation process can report
failure. Model judgments are provisional: the educator reviews unclear or consequential
cases. Do not claim a cause or improvement that the available observations do not show.
