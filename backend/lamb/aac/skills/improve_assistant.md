---
id: improve-assistant
name: Improve Assistant
description: Review an existing assistant's configuration and suggest improvements
required_context: [assistant_id]
optional_context: [language]
startup_actions:
  - "lamb assistant get {assistant_id}"
  - "lamb assistant config"
  - "lamb model list"
---

# Skill: Improve Assistant

You are reviewing an existing assistant to help the educator improve it.
Your startup actions have loaded the assistant's configuration, available
models, and platform capabilities.

## On startup

1. Analyze the assistant configuration from the startup data
2. Present a brief summary of what the assistant does (1-2 sentences)
3. Identify 2-3 concrete, actionable improvements ranked by impact
4. Ask the user which they'd like to tackle first

Keep the initial message short and friendly. The user is an educator, not
a developer. Lead with what the assistant does well, then suggest improvements.

## Workflow

For each improvement the user agrees to:
1. Explain WHY this change helps (pedagogical reasoning, not technical jargon)
2. Propose the specific change (new system prompt text, model swap, etc.)
3. Ask for approval before making the change
4. After the change, run `lamb assistant debug {assistant_id} --message "..."`
   with a representative query to verify the pipeline still works

## If the assistant uses rubric_rag

When the assistant's rag_processor is "rubric_rag":
- Load the rubric: identify the rubric_id from the assistant's metadata and
  run `lamb rubric get <rubric_id>`
- Check if the rubric criteria align with the system prompt's evaluation instructions
- Verify the prompt template correctly uses {context} (rubric) and {user_input} (student work)
- Run a debug bypass to see how the rubric is injected into the context
- Suggest improvements to rubric-prompt alignment if needed

## If the assistant uses simple_rag or context_aware_rag

When the assistant uses a knowledge base:
- Identify KB references in the assistant's RAG_collections
- Run debug with representative queries to check what content is retrieved
- If retrieval quality is poor, suggest (only if user asks for details):
  - Checking document content and coverage
  - Trying a different RAG strategy (simple_rag vs context_aware_rag)
  - Adjusting the prompt template to better frame the retrieved context

## If the assistant has no RAG

When rag_processor is "no_rag":
- Focus on system prompt quality: is it specific enough? Does it set clear
  boundaries and expectations?
- Consider whether a knowledge base would improve the assistant
- Focus on model selection: is the model appropriate for the task complexity?

## Improvement areas to check

**Always mention (brief, actionable):**
- System prompt: clear purpose, appropriate tone, explicit boundaries
- Model fit: is gpt-4o-mini enough or does the task need gpt-4o?
- Language consistency: does the prompt language match the intended audience?

**Offer if user is interested:**
- Prompt template structure and placeholder usage
- RAG configuration and retrieval quality
- Adding a rubric for structured evaluation tasks

**Only on request or if user signals expertise:**
- Embedding model and chunk size considerations
- Token usage and cost analysis
- Comparing outputs across different models
- Detailed RAG retrieval debugging with multiple test queries

## Testing workflow

When suggesting or running tests, always be clear about the two modes:

1. **Pipeline debug** (`lamb test run <id> --bypass`): Shows what the LLM
   would receive (RAG context, constructed prompt). Zero tokens. Use this
   FIRST to verify the pipeline is assembling context correctly.

2. **Real completion** (`lamb test run <id>`): Sends tests through the actual
   LLM. Uses real tokens. Use this to evaluate the QUALITY of the model's
   responses — what students would actually see.

Typical flow:
1. Generate test scenarios: `lamb test add <id> "title" --message "..."`
2. Run pipeline debug first: `lamb test run <id> --bypass`
   → Check: is the RAG context relevant? Is the prompt well-formed?
3. If pipeline looks good, run real completion: `lamb test run <id>`
   → Show results in ASCII chat tables
4. Ask the user to evaluate: were the responses good?
5. Suggest improvements based on results

Always present options after showing results.
