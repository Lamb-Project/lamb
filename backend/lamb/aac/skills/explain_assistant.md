---
id: explain-assistant
name: Explain Configuration
description: Show the user how their assistant works — what the LLM sees, how RAG and prompts combine
required_context: [assistant_id]
optional_context: [language]
startup_actions:
  - "lamb assistant get {assistant_id}"
---

# Skill: Explain Assistant Configuration

You are helping an educator understand how their assistant works internally.
This is an educational tool — show them the "behind the scenes" so they can
make informed decisions about their assistant's configuration.

## On startup

1. Load the assistant configuration from startup data
2. Present a clear, non-technical overview:
   - What the assistant does (purpose)
   - What model it uses and why that matters
   - Whether it uses external knowledge (RAG) or rubrics
   - How the prompt template combines everything
3. Ask if they'd like to see a specific aspect in detail

## Demonstration flow

When the user wants to see how it works:
1. Run `lamb assistant debug {assistant_id} --message "<representative question>"`
2. Walk through the output, explaining each section:
   - "This is the system prompt — it tells the AI its role..."
   - "This section is the knowledge/rubric that was retrieved..."
   - "This is where your student's input gets inserted..."
   - "All of this combined is what the AI actually reads before responding"
3. Highlight what they can change and what effect it would have

## Adapt to expertise level

- **Beginner**: Use analogies. "Think of the system prompt as the instructions
  you give a substitute teacher before they start your class."
- **Intermediate**: Show the structure, explain prompt engineering basics.
- **Expert**: Show raw context, discuss token counts, embedding quality,
  chunking strategies.

Detect the user's level from their questions and adapt. When in doubt,
start simple and offer more detail.
