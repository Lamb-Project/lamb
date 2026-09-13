---
topic: ui-assistants
covers: [tutorial, screenshots, assistant, create, edit, properties, no-rag, single-file, context-aware]
answers:
  - "Show me how to configure an assistant and its documents"
---

# Show me how to configure an assistant and its documents

Screenshots show an English dev UI with synthetic examples, captured 13 September 2026 for the 0.7 tutorial. The old v0.6 header may still be visible. Names, IDs, available models and plugins vary by installation. The user performs these actions in their browser.

## Create or edit

Open **Learning Assistants** and **Create Assistant**, or open an existing assistant and its **Edit** tab. Enter **Assistant Name**, **Description** and **System Prompt**. Choose from the **Language Model (LLM)** options provided by your organization. Review **Prompt Template** as well: it determines how the question and document context reach the model. Scroll to **Save** to persist changes, then reopen **Properties** to check them.

![Assistant creation form with prompts and configuration controls](/img/aac-tutorials/assistant-create.png)

[Open full-size screenshot](/img/aac-tutorials/assistant-create.png)

## Without documents

Choose **No Rag** in **RAG Processor**. A straightforward prompt template is `{user_input}`. Save, then test the behavior in the assistant's chat.

## Use an existing knowledge base

Choose **Simple Rag** or **Context Aware Rag** in **RAG Processor**. Select the intended knowledge base in the revealed selector and review **RAG Top K**. First verify that KB's ingestion and query results. Use a prompt template containing both `{context}` and `{user_input}`, for example:

```
Context: {context}
Question: {user_input}
```

Save and verify the selected source in **Properties**. If the selection does not appear, report the actual interface state rather than guessing a KB ID.

![Assistant form with Simple Rag and knowledge-base configuration](/img/aac-tutorials/assistant-kb.png)

[Open full-size screenshot](/img/aac-tutorials/assistant-kb.png)

![Context Aware Rag with knowledge-base selection](/img/aac-tutorials/assistant-context.png)

[Open full-size screenshot](/img/aac-tutorials/assistant-context.png)

## Use a single local file

Choose **Single File Rag**. In **Upload New File**, click **Choose File**, select your own file and wait for upload to finish. Review the selected file in the selector before saving. Alternatively choose an existing file you can access. Keep `{context}` and `{user_input}` in the prompt template. Use UTF-8 text/Markdown/JSON for this documented path; the chooser advertising other extensions does not prove those files work as whole-text context. For PDF material, use KB ingestion and KB-backed RAG instead.

![Single File Rag configuration with Upload New File and file selection](/img/aac-tutorials/assistant-file.png)

[Open full-size screenshot](/img/aac-tutorials/assistant-file.png)

## View and explain saved properties

Open the assistant's **Properties** tab. Review its description, model, prompts and connected knowledge. Ask AAC to explain those saved settings; it should distinguish actual settings from suggestions.

![Saved assistant Properties tab](/img/aac-tutorials/assistant-properties.png)

[Open full-size screenshot](/img/aac-tutorials/assistant-properties.png)
