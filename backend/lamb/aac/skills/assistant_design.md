# Skill: Assistant Design & Improvement

When helping an educator design or improve an assistant, follow this workflow.

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

## 3. Create or modify the assistant
Use `lamb assistant create` or `lamb assistant update` with appropriate settings:
- Choose a model that fits the task (gpt-4o-mini for simple, gpt-4o for complex)
- Write a clear system prompt focused on the pedagogical goal
- Select RAG processor if knowledge bases are needed
- Select prompt processor (usually simple_augment)

## 4. Debug the pipeline
Use `lamb assistant debug <id> --message "sample question"` to see exactly
what the LLM receives — the fully constructed context including:
- The system prompt
- RAG-retrieved content (knowledge base chunks, rubric criteria)
- The processed prompt template with user input inserted

This is crucial for diagnosing issues. Common things to look for:
- Is the RAG context relevant to the question? If not, the knowledge base
  may need better content, different chunk sizes, or a different embedding model.
- Is the prompt template inserting the user input and context correctly?
- Is the system prompt clear enough for the LLM to follow?
- How large is the total context? Large contexts may need a more capable model.

## 5. Offer improvement suggestions

When reviewing an assistant, check for these common issues and suggest
improvements at the right level for the user:

**Always mention (brief, actionable):**
- System prompt clarity and pedagogical focus
- Whether the model matches the task complexity
- Whether RAG is being used effectively (or should be added/removed)

**Offer if the user is interested (don't overwhelm):**
- Knowledge base quality: are the right documents there? Is content chunked well?
- RAG strategy: simple_rag vs context_aware_rag vs hierarchical_rag
- Prompt template structure: how context and user input are combined
- Rubric configuration for evaluation assistants

**Only on request or if user signals expertise:**
- Embedding model selection and chunk size tuning
- Token consumption analysis and cost optimization
- Comparing responses across different LLM models
- Detailed RAG retrieval analysis (what chunks are returned for specific queries)

## 6. Verify changes
After any modification, read back the assistant state:
- `lamb assistant get <id>` — confirm all settings are correct
- Run a debug check with a representative query to verify the pipeline

## 7. Suggest testing
Propose test queries that exercise:
- The core use case (happy path)
- Edge cases (off-topic, ambiguous, adversarial)
- Rubric coverage (if using rubric-based evaluation)

Use `lamb assistant debug <id> --message "..."` for quick pipeline checks
without consuming tokens.
