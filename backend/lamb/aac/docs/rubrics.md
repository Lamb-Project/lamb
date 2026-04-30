---
topic: rubrics
covers: [rubric, evaluaitor, criteria, scoring, evaluation, rubric-rag, performance-levels]
answers:
  - "how do I create a rubric"
  - "what is EvaluAItor"
  - "how do I use a rubric with an assistant"
  - "how does rubric evaluation work"
---

## What is EvaluAItor?

EvaluAItor is LAMB's rubric-based evaluation system. You define criteria with performance levels, and the AI assistant evaluates student submissions against them. Useful for:
- Evaluating written assignments
- Assessing project presentations
- Providing structured, consistent feedback

## Creating a Rubric

Go to Sources of Knowledge > Rubrics > Create Rubric. Define:
- **Name** and **Description**
- **Subject** (academic discipline)
- **Scoring Type** (points or qualitative levels)
- **Maximum Score**
- **Criteria** — each with:
  - Name and weight (percentage of total)
  - Performance levels (e.g., Excellent, Good, Adequate, Insufficient) with descriptions and point values

## Using a Rubric with an Assistant

1. Create or edit an assistant
2. Set RAG Processor to **Rubric Rag**
3. Select the rubric in the configuration
4. Write a system prompt instructing the assistant to evaluate using the rubric
5. Prompt template must include `{context}` (rubric content) and `{user_input}` (student submission)

When a student submits work, the assistant retrieves the rubric criteria and provides structured evaluation feedback.

## Managing Rubrics

- View, edit, export (JSON or markdown), duplicate, delete from the Rubrics page
- Share rubrics publicly within your organization via the Share button
- Templates tab shows public rubrics shared by others
