---
id: manage-rubric
name: Manage Rubric
description: Create, explain and edit rubrics and bind them to assistants
required_context: []
optional_context: [language]
startup_actions:
  - "lamb rubric list"
---

Ask what should be assessed, the scoring scheme, criteria, performance levels and weights. Inspect an existing rubric with `lamb rubric get ID` when editing. Use the complete schema example below or an existing rubric, and report validation errors accurately.

Create with `lamb rubric create TITLE --criteria JSON`, optionally --description, --subject, --grade-level, --scoring-type and --max-score. Edit with `lamb rubric update ID` and only the fields the user requests. Both writes require approval. For weight-only edits prefer `lamb rubric update ID --weights '{"Evidence":60,"Reasoning":40}'`, using exact unique names read from the rubric. This patches only weights while preserving all criterion and level IDs. A rubric already totaling 100 must continue to do so; an existing invalid total can be repaired incrementally. Do not combine --weights and --criteria. Read the result back before claiming completion.

Criteria is a full replacement array: retain every criterion/level/ID the user did not ask to change. Never overwrite unrelated rubric fields silently.

Read the saved rubric again and explain the actual criteria, levels and scoring. Bind it to an assistant with --rag-processor rubric_rag --rubric-id ID --rubric-format markdown; include {context} and {user_input} in the prompt template. Read back the assistant configuration. Use test-and-evaluate to assess strong, weak and partial sample submissions, storing runs and justified evaluations. A generated response is not proof that a rubric was saved or bound.


## Complete create example

This example has one criterion and three nonempty levels. Adapt its content to the user's approved rubric, keep unique criterion/level IDs, and ensure normal new weights total 100. Never omit level descriptions or use a level label as its description without considering the actual assessment.
```aac-command
lamb rubric create "Evidence rubric" --description "Assess support for a claim" --subject "Writing" --grade-level "University" --scoring-type points --max-score 2 --criteria '[{"id":"evidence","name":"Evidence","description":"Supports a claim with relevant evidence","weight":100,"levels":[{"id":"strong","score":2,"label":"Strong","description":"Relevant evidence clearly supports the claim"},{"id":"partial","score":1,"label":"Partial","description":"Some evidence is relevant but support is incomplete"},{"id":"weak","score":0,"label":"Weak","description":"No relevant evidence supports the claim"}]}]'
lamb rubric get RUBRIC_ID
lamb rubric update RUBRIC_ID --description "Only the user-approved description change"
lamb rubric get RUBRIC_ID
```
Keep the returned RUBRIC_ID and compare title, metadata, criterion/level IDs, scores and weights. A validation failure creates no successful rubric; correct the reported missing/invalid fields before asking for a new write. For UI instructions load `lamb docs read ui-rubrics` and guide the user's actual form actions instead of creating a second rubric behind the UI.

For W13 activate create-assistant with the saved rubric ID and its rubric_rag recipe. Read back the binding, then use test-and-evaluate with strong, weak and partial submissions. After an approved rubric edit, inspect actual debug context and run the same submission again to establish whether the new rubric is being used. Report observed behavior, not an assumed live/snapshot contract.
