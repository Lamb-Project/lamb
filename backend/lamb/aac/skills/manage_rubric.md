---
id: manage-rubric
name: Manage Rubric
description: Create, explain and edit rubrics and bind them to assistants
required_context: []
optional_context: [language]
startup_actions:
  - "lamb rubric list"
---

Ask what should be assessed, the scoring scheme, criteria, performance levels and weights. Inspect an existing rubric with `lamb rubric get ID` when editing. Do not invent the schema: use an existing rubric or documentation, and report validation errors accurately.

Create with `lamb rubric create TITLE --criteria JSON`, optionally --description, --subject, --grade-level, --scoring-type and --max-score. Edit with `lamb rubric update ID` and only the fields the user requests. Both writes require approval. Criteria is a full replacement array: retain every criterion/level/ID the user did not ask to change. Never overwrite unrelated rubric fields silently.

Read the saved rubric again and explain the actual criteria, levels and scoring. Bind it to an assistant with --rag-processor rubric_rag --rubric-id ID --rubric-format markdown; include {context} and {user_input} in the prompt template. Read back the assistant configuration. Use test-and-evaluate to assess strong, weak and partial sample submissions, storing runs and justified evaluations. A generated response is not proof that a rubric was saved or bound.
