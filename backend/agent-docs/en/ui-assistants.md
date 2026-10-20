<a id="overview"></a>

# Show me how to configure an assistant and its documents

Screenshots show an English dev UI with synthetic examples, captured 13 September 2026 for the 0.7 tutorial. The old v0.6 header may still be visible. Names, IDs, available models and plugins vary by installation. The user performs these actions in their browser.

<a id="create-or-edit"></a>
## Create or edit

Open **Learning Assistants** and **Create Assistant**, or open an existing assistant and its **Edit** tab. Enter **Assistant Name**, **Description** and **System Prompt**. Choose from the **Language Model (LLM)** options provided by your organization. Review **Prompt Template** as well: it determines how the question and document context reach the model. Scroll to **Save** to persist changes, then reopen **Properties** to check them.

![Assistant creation form with prompts and configuration controls](/agent-docs/img/en/assistant-create.png)

[Open full-size screenshot](/agent-docs/img/en/assistant-create.png)

<a id="without-documents"></a>
## Without documents

Choose **No Rag** in **RAG Processor**. A straightforward prompt template is `{user_input}`. Save, then test the behavior in the assistant's chat.

<a id="use-an-existing-knowledge-base"></a>
## Use an existing knowledge base

Choose **Simple Rag** or **Context Aware Rag** in **RAG Processor**. Select the intended knowledge base in the revealed selector and review **RAG Top K**. First verify that KB's ingestion and query results. Use a prompt template containing both `{context}` and `{user_input}`, for example:

```
Context: {context}
Question: {user_input}
```

Save and verify the selected source in **Properties**. If the selection does not appear, report the actual interface state rather than guessing a KB ID.

![Assistant form with Simple Rag and knowledge-base configuration](/agent-docs/img/en/assistant-kb.png)

[Open full-size screenshot](/agent-docs/img/en/assistant-kb.png)

![Context Aware Rag with knowledge-base selection](/agent-docs/img/en/assistant-context.png)

[Open full-size screenshot](/agent-docs/img/en/assistant-context.png)

<a id="use-a-single-local-file"></a>
## Use a single local file

Choose **Single File Rag**. In **Upload New File**, click **Choose File**, select your own file and wait for upload to finish. Review the selected file in the selector before saving. Alternatively choose an existing file you can access. Keep `{context}` and `{user_input}` in the prompt template. Use UTF-8 text/Markdown/JSON for this documented path; the chooser advertising other extensions does not prove those files work as whole-text context. For PDF material, use KB ingestion and KB-backed RAG instead.

![Single File Rag configuration with Upload New File and file selection](/agent-docs/img/en/assistant-file.png)

[Open full-size screenshot](/agent-docs/img/en/assistant-file.png)

<a id="view-and-explain-saved-properties"></a>
## View and explain saved properties

Open the assistant's **Properties** tab. Review its description, model, prompts and connected knowledge. Ask AAC to explain those saved settings; it should distinguish actual settings from suggestions.

![Saved assistant Properties tab](/agent-docs/img/en/assistant-properties.png)

[Open full-size screenshot](/agent-docs/img/en/assistant-properties.png)
