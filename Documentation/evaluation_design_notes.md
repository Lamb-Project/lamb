# Evaluation Design Notes

Notes for anyone building or reviewing assistant test scenarios in LAMB. Related to [#327](https://github.com/Lamb-Project/lamb/issues/327) and [#172](https://github.com/Lamb-Project/lamb/issues/172).


---

## Purpose

Educators change system prompts, knowledge bases, and models often. Without saved test scenarios and recorded runs, it is hard to see whether a change helped or made things worse.

LAMB runs tests through the same completion pipeline as production (RAG, prompt processors, LLM). Each run stores the input, response, and an assistant configuration snapshot for later comparison.

---

## Scenario types (evaluation intent)

When writing scenarios in the Assistant Control Centre, match the scenario to what you want to learn.

| Intent | What you are testing | Example student question (fictional) |
|--------|----------------------|--------------------------------------|
| **Grounded answer** | Reply stays faithful to course materials | "What is a food chain?" |
| **KB miss** | Safe behaviour when retrieval is weak or empty | "Does quantum physics affect photosynthesis in this course?" |
| **Partial context** | No over-claiming when only fragments are retrieved | "Summarise the whole ecology unit in one paragraph." |
| **Tone / register** | Voice matches the pedagogical role in the system prompt | "lol idk what mitosis is" |

The platform also labels scenario **type**: Normal (`single_turn`), Multi-turn (`multi_turn`), and Adversarial (`adversarial`). Use adversarial scenarios for off-topic or misleading prompts where refusal or redirection is the expected behaviour.

---

## Next steps (planned)

- Verdict labels for teachers (good / bad / mixed and grounding vocabulary)
- Symmetric evaluation when comparing two assistant configurations
- Fictional worked examples