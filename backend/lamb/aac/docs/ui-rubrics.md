---
topic: ui-rubrics
covers: [tutorial, screenshots, rubric, criteria, weights, scoring, assistant-binding]
answers:
  - "Show me how to create and edit a rubric"
---

# Show me how to create and edit a rubric

Screenshots show an English dev UI with synthetic examples, captured 13 September 2026 for the 0.7 tutorial. The old v0.6 header may still be visible. Names, IDs, available models and plugins vary by installation. The user performs these actions in their browser.

## Create a rubric

Open **Sources of Knowledge** and the rubric area (**Evaluaitor**), then **Create Rubric**. Enter **Title**, **Subject**, **Grade Level**, **Scoring Type** and **Maximum Score** where applicable. In **Assessment Criteria**, edit each criterion's name, weight, description and performance levels. Use **Add Criterion** and **Add Level** as needed. For percentage weights, check that they total 100. Review the content before pressing the form's **Create Rubric** button. **Generate with AI** is a separate optional action, not required for manual creation.

![Rubric editor showing metadata, criterion weights and performance levels](/img/aac-tutorials/rubric-create.png)

[Open full-size screenshot](/img/aac-tutorials/rubric-create.png)

## View and edit

Return to **My Rubrics**, open the saved rubric and use its edit controls. Verify the saved criteria, levels, weights and scoring. Change only what you intend; for weight-only changes preserve the existing criterion and level identities. If the rubric page shows a fetch or save error, resolve it before claiming the rubric exists.

## Use the rubric in an assistant

Create or edit an assistant. Choose **Rubric Rag** under **RAG Processor**, then select your saved rubric. Write a system prompt explaining how the assistant should assess submissions. Include `{context}` and `{user_input}` in the prompt template. Save, inspect the binding, and test strong, weak and partial example submissions. Review whether the actual feedback follows the criteria and weights; a saved binding alone is not a grading-quality test.
