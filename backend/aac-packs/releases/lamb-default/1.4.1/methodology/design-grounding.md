<a id="choose-grounding"></a>
# Choosing grounding

Begin with the material and the learning task. If students need general practice and no
specific source governs the answers, a design without external grounding may suffice.
For one short, stable document that comfortably fits the model context, single-file
grounding is often simpler to inspect and maintain than a searchable collection.
The educator must select and upload the file through the UI in frontend liteshell.
For multiple documents, changing materials or content too large to include whole,
consider a knowledge base. Retrieval can omit relevant passages; design questions that
test coverage and inspect assembled context before trusting answers.
Context-aware retrieval is worth considering when follow-up questions depend on earlier
turns. It adds a query-rewriting step, latency and another possible failure. Compare the
same follow-up scenarios with simpler retrieval before choosing it. More top-k is an
experiment, not a guaranteed fix. These are design alternatives only when reported by
the installation capability map. Ask about material size, stability and follow-up needs;
do not create a KB merely because a user mentions a document.
