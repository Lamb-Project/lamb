<a id="overview"></a>

# Show me how to chat with and test my assistant

Screenshots show an English dev UI with synthetic examples. The test-case form and controls were recaptured on 18 September 2026; the assistant chat image is from 13 September 2026. The old v0.6 header may still be visible. Names, IDs, available models and plugins vary by installation. The user performs these actions in their browser.

<a id="try-the-assistant-yourself"></a>
## Try the assistant yourself

Open the assistant, then **Chat with [assistant name]**. Send your own questions there. That chat is with your learning assistant; the AAC Agent conversation is where you ask for authoring help. Try an ordinary question, a question grounded in your source, and a follow-up that depends on the conversation.

![Assistant chat tab, separate from AAC](/agent-docs/img/en/assistant-chat.png)

[Open full-size screenshot](/agent-docs/img/en/assistant-chat.png)

<a id="add-a-scenario"></a>
## Add a test case

Open **Tests**, click **+ Add Test Case**, and enter a title, **Student message / test prompt**, test case type and **Expected behavior (optional)**. The types in this UI are **Normal**, **Multi-turn**, and **Adversarial**. State what a satisfactory answer should contain. Click **Add** to save or **Cancel** to discard the form.

![Test case form with a question and expected behavior](/agent-docs/img/en/tests-add.png)

[Open full-size screenshot](/agent-docs/img/en/tests-add.png)

<a id="run-and-inspect"></a>
## Run and inspect

Use **Run** on one test case or **Run All** for the saved set. These call the configured model. **Debug** and **Debug All (bypass)** inspect prompt assembly without a completion-model call; they do not establish answer quality and retrieval can still involve other services. Wait for results; do not assume a timeout means no run was saved. Inspect run history before retrying.

![Saved test case with Run, Debug and batch controls](/agent-docs/img/en/tests-run.png)

[Open full-size screenshot](/agent-docs/img/en/tests-run.png)

<a id="evaluate-and-improve"></a>
## Evaluate and improve

Open a saved run to read its response and compare it with the expected behavior. Use **Evaluate** to record your judgment and notes, then save. Tell AAC which behavior needs improvement. Review changes in **Edit**, save, and rerun the affected test cases. Passing one example does not establish all intended behavior.

<a id="inspect-activity"></a>
## Inspect activity

Use **Activity** on the assistant to inspect available usage and conversations. Available detail depends on your permissions. Do not infer successful student use from an empty activity view. Ask AAC to explain actual recorded activity and distinguish missing evidence from zero usage.
