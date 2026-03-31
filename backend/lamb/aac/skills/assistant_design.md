# Skill: Assistant Design

When helping an educator design a new assistant, follow this workflow:

## 1. Understand the goal
Ask what the assistant should do:
- What subject/topic?
- Who is the audience (grade level, expertise)?
- What interaction pattern? (tutor, evaluator, Q&A, open-ended)
- What language should the assistant use?

## 2. Check available resources
Before configuring, inspect what's available:
- `lamb model list` — what LLMs are available?
- `lamb kb list` — any relevant knowledge bases?
- `lamb rubric list` — any rubrics for evaluation assistants?
- `lamb template list` — any reusable prompt templates?
- `lamb assistant config` — what connectors and processors exist?

## 3. Create the assistant
Use `lamb assistant create` with appropriate settings:
- Choose a model that fits the task (gpt-4o-mini for simple, gpt-4o for complex)
- Write a clear system prompt focused on the pedagogical goal
- Select RAG processor if knowledge bases are needed
- Select prompt processor (usually simple_augment)

## 4. Verify the configuration
After creating, read it back:
- `lamb assistant get <id>` — confirm all settings are correct
- Explain to the educator what each setting does

## 5. Suggest testing
Propose test queries that exercise:
- The core use case (happy path)
- Edge cases (off-topic, ambiguous, adversarial)
- Rubric coverage (if using rubric-based evaluation)
