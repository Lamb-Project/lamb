---
topic: ui-testing
covers: [tutorial, screenshots, chat, scenarios, expected-behavior, evaluation, activity]
answers:
  - "Show me how to chat with and test my assistant"
---

# Show me how to chat with and test my assistant

Screenshots show an English dev UI with synthetic examples, captured 13 September 2026 for the 0.7 tutorial. The old v0.6 header may still be visible. Names, IDs, available models and plugins vary by installation. The user performs these actions in their browser.

## Try the assistant yourself

Open the assistant, then **Chat with [assistant name]**. Send your own questions there. That chat is with your learning assistant; the AAC Agent conversation is where you ask for authoring help. Try an ordinary question, a question grounded in your source, and a follow-up that depends on the conversation.

![Assistant chat tab, separate from AAC](/img/aac-tutorials/assistant-chat.png)

[Open full-size screenshot](/img/aac-tutorials/assistant-chat.png)

## Add a scenario

Open **Tests**, click **+ Add Scenario**, and enter a title, **Student message / test prompt**, scenario type and **Expected behavior (optional)**. The types in this UI are **Normal**, **Multi-turn**, and **Adversarial**. State what a satisfactory answer should contain. Click **Add** to save or **Cancel** to discard the form.

![Test scenario form with a question and expected behavior](/img/aac-tutorials/tests-add.png)

[Open full-size screenshot](/img/aac-tutorials/tests-add.png)

## Run and inspect

Use **Run** on one scenario or **Run All** for the saved set. These call the configured model. **Debug** and **Debug All (bypass)** inspect prompt assembly without a completion-model call; they do not establish answer quality and retrieval can still involve other services. Wait for results; do not assume a timeout means no run was saved. Inspect run history before retrying.

![Saved scenario with Run, Debug and batch controls](/img/aac-tutorials/tests-run.png)

[Open full-size screenshot](/img/aac-tutorials/tests-run.png)

## Evaluate and improve

Open a saved run to read its response and compare it with the expected behavior. Use **Evaluate** to record your judgment and notes, then save. Tell AAC which behavior needs improvement. Review changes in **Edit**, save, and rerun the affected scenarios. Passing one example does not establish all intended behavior.

## Inspect activity

Use **Activity** on the assistant to inspect available usage and conversations. Available detail depends on your permissions. Do not infer successful student use from an empty activity view. Ask AAC to explain actual recorded activity and distinguish missing evidence from zero usage.
