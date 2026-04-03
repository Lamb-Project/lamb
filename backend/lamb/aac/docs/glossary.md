---
topic: glossary
covers: [terms, definitions, vocabulary]
answers:
  - "what does RAG mean"
  - "what is a connector"
  - "what is LTI"
  - "what is bypass mode"
  - "what is a prompt processor"
---

## Glossary

| Term | Definition |
|------|-----------|
| **Assistant** | An AI-powered learning tool with a defined personality, knowledge source, and behavior |
| **System Prompt** | Instructions that define how the assistant behaves and responds |
| **Prompt Template** | Template that assembles the system prompt, retrieved context, and student question into the final prompt sent to the AI model. Must contain `{context}` and `{user_input}` placeholders when using RAG. |
| **Knowledge Base (KB)** | A collection of documents the assistant searches for relevant context |
| **RAG** | Retrieval-Augmented Generation — retrieves relevant document chunks to ground AI responses in your content |
| **RAG Processor** | Algorithm that handles document retrieval: Simple Rag (basic), Context Aware Rag (advanced), Rubric Rag (evaluation) |
| **RAG Top K** | Number of document chunks retrieved per query (1-10, default 3) |
| **Connector** | AI provider: OpenAI, Ollama, or Bypass (debug) |
| **LLM** | Large Language Model — the AI model generating responses (e.g., GPT-4o, GPT-4o-mini) |
| **Bypass / Debug Mode** | Shows what the model would receive without calling it. Zero cost. Essential for verifying RAG pipelines. |
| **LTI** | Learning Tools Interoperability — standard for integrating LAMB with LMS platforms (Moodle, Canvas) |
| **Publishing** | Making an assistant available to students via the LMS |
| **Rubric** | Structured evaluation framework with criteria and performance levels, used by EvaluAItor |
| **EvaluAItor** | LAMB's rubric-based evaluation system |
| **Organization** | Tenant boundary isolating users, assistants, KBs, and LLM configuration |
| **Prompt Processor** | Plugin that transforms messages before they reach the LLM (e.g., simple_augment) |
