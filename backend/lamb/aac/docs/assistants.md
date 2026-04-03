---
topic: assistants
covers: [create, edit, delete, system-prompt, description, name, llm, connector, vision, advanced-mode, import-json, prompt-template, properties, export]
answers:
  - "how do I create an assistant"
  - "how do I edit an assistant"
  - "how do I delete an assistant"
  - "what is a system prompt"
  - "what is a prompt template"
  - "how do I change the model"
  - "what models are available"
  - "how do I enable vision"
  - "what is advanced mode"
  - "how do I import an assistant"
  - "how do I export an assistant"
---

## Creating an Assistant

1. Go to Learning Assistants > + Create Assistant
2. Fill in:
   - **Assistant Name** (required, max 20 chars, spaces become underscores)
   - **Description** (optional, click Generate to auto-create from name + prompt)
   - **System Prompt** — defines the assistant's personality, expertise, behavior
   - **Prompt Template** — how the student's question and retrieved context are assembled
3. Configuration panel (right side):
   - **Language Model (LLM)** — which AI model to use (default from org config)
   - **Enable Vision** — process images alongside text
   - **RAG Processor** — how to use knowledge base documents (default: No Rag)
4. Click Save. The assistant is created as Unpublished (only you can see it).

Toggle **Advanced Mode** to access Connector and Prompt Processor settings.

Click **Import from JSON** to load a configuration exported from another LAMB instance.

## System Prompt Tips

The system prompt is the most important field. Good practices:
- Define the role: "You are a music history tutor for high school students."
- Set the scope: "Focus on 1960s British rock."
- Give behavioral instructions: "Keep explanations clear and age-appropriate."
- Handle edge cases: "If the question is outside the context, say so plainly."
- Encourage interaction: "Ask follow-up questions when helpful."

## Prompt Template

Controls how the final prompt is assembled. Use placeholder buttons to insert:
- `{context}` — where retrieved KB content goes (required when using RAG)
- `{user_input}` — where the student's question goes

Example:
```
Context:
{context}

Student question: {user_input}

Answer using the provided context.
```

## Viewing Assistant Details

Click the View (eye) icon on any assistant. The detail page has tabs:
- **Properties** — read-only view of all configuration
- **Edit** — modify settings
- **Share** — manage who has access
- **Chat** — test by chatting directly
- **Activity** — usage statistics and chat history
- **Tests** — create and run test scenarios

## Editing an Assistant

Click the Edit tab. Same form as creation. On the right panel:
- Change LLM model, connector, processors
- Toggle Vision Capability
- Select RAG Processor and configure options
- Choose Knowledge Bases (checkboxes appear when RAG is selected)

Click Save Changes when done.

## Deleting an Assistant

Click the Delete button (red trash icon) on the assistant list or the Delete button on Properties. Requires confirmation. This is a soft delete — the assistant is archived, not permanently removed.

## Exporting an Assistant

Click the Export button on Properties to download the assistant configuration as JSON. This can be imported into another LAMB instance.
