<a id="overview"></a>

# Show me how to upload and ingest a file in the UI

Screenshots show an English dev UI with synthetic examples, captured 13 September 2026 for the 0.7 tutorial. The old v0.6 header may still be visible. Names, IDs, available models and plugins vary by installation. The user performs these actions in their browser.

<a id="create-or-open-a-knowledge-base"></a>
## Create or open a knowledge base

1. Open **Sources of Knowledge**, then **Knowledge Bases**.
2. For an existing KB, click **View** on its entry. Otherwise click **Create Knowledge Base**, enter a name and description, then submit the form with **Create Knowledge Base**.
3. Wait for creation to finish. Use your KB's name; the example name/ID in the screenshot is not a target to copy.

![Create Knowledge Base dialog with a name and description](/agent-docs/img/en/kb-create.png)

[Open full-size screenshot](/agent-docs/img/en/kb-create.png)

<a id="select-your-local-file"></a>
## Select your local file

1. In the KB detail page, open **Ingest Content**. The **Files** tab lists files and their status; it is not the upload form.
2. Under **Select File**, click **Choose File** (the native button label can vary by browser).
3. Your computer opens its file picker. Select the intended document and confirm the selection. AAC cannot select a file on your computer. Canceling the picker does not ingest anything.
4. Check that the correct filename appears. Choose another file if it is wrong.

![Ingest Content tab with the file chooser highlighted](/agent-docs/img/en/kb-select-file.png)

[Open full-size screenshot](/agent-docs/img/en/kb-select-file.png)

<a id="start-ingestion"></a>
## Start ingestion

1. Choose the appropriate **Ingestion Plugin** from those actually available. For plain text or Markdown use `simple_ingest`; for PDF/Office documents, `markitdown_ingest` converts the file when that plugin is available. Do not promise unsupported formats or plugins.
2. Keep the default parameters unless there is a reason to change them. **Advanced** reveals more options.
3. With the intended filename displayed, click **Upload File**. This starts upload and ingestion. **Run Ingestion** is the label used for non-file ingestion modes.
4. Wait for the upload response. Do not click repeatedly or retry an uncertain timeout before inspecting saved status.

![Selected course-notes.md and the Upload File button highlighted](/agent-docs/img/en/kb-ingest.png)

[Open full-size screenshot](/agent-docs/img/en/kb-ingest.png)

<a id="check-processing"></a>
## Check processing

Open **Files** and use **Refresh Status**. A row marked **processing** means the file is not yet ready; wait and refresh. The screenshot illustrates this intermediate state, not successful completion. If processing reports failure, inspect the error before retrying. A selected filename or successful upload alone does not prove completed ingestion.

![Files tab with processing status and Refresh Status control](/agent-docs/img/en/kb-files.png)

[Open full-size screenshot](/agent-docs/img/en/kb-files.png)

<a id="verify-retrieval"></a>
## Verify retrieval

1. Open **Query**. Enter a question about a distinctive fact in your document.
2. Click **Submit Query**.
3. Inspect **Query Results**, source identity and returned content. The sample source says CORAL-19 and Tuesday; your query should use a fact in your own document.
4. Empty results or errors are not success. Check ingestion status and the selected KB. Tell AAC what you see; it may inspect the KB with read tools when it knows which one you used.

![Query results containing the actual sample source fact CORAL-19](/agent-docs/img/en/kb-query.png)

[Open full-size screenshot](/agent-docs/img/en/kb-query.png)
