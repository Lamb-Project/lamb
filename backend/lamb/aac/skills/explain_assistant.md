---
id: explain-assistant
name: Explain Configuration
description: Show how the assistant works internally
required_context: [assistant_id]
optional_context: [language]
startup_actions:
  - "lamb assistant get {assistant_id}"
---

# Skill: Explain Assistant

Show the educator how their assistant works. Be brief.

## On startup

Summarize in 3-4 short lines:
- Purpose (one sentence)
- Model + RAG setup (one line)
- How the prompt assembles (one line)

Then offer options. Do NOT explain everything unprompted.

## If user asks for detail

Only then go deeper. Use `lamb assistant debug` to show real context.
Keep explanations short. Use bullet points, not paragraphs.

Adapt depth to the user: start minimal, add detail only when asked.
