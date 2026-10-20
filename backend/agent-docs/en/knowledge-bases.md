<a id="overview"></a>

For verified 0.7 UI steps and screenshots, read `lamb docs read ui-knowledge-bases`. Prefer that guide for button locations and user-operated actions.


<a id="what-is-rag"></a>
## What is RAG?

Retrieval-Augmented Generation (RAG) makes your assistant answer using your own documents instead of just its training data. When a student asks a question:
1. The system searches your documents for relevant passages
2. Those passages are inserted into the prompt as context
3. The AI model generates an answer grounded in your content

Without RAG: the assistant answers from general training data (may be outdated or inaccurate for your course).
With RAG: answers are grounded in your specific materials.

<a id="creating-a-knowledge-base"></a>
## Creating a Knowledge Base

Go to Sources of Knowledge > Knowledge Bases > Create Knowledge Base. Give it a descriptive name.

<a id="adding-documents"></a>
## Adding Documents

Click View on a KB. The detail page has three tabs:

### Files Tab
The Files tab lists uploaded files and their processing status. Upload files from **Ingest Content**, using the file chooser and a suitable available plugin. Common source formats include:
- PDF (textbooks, articles, handouts)
- Markdown / plain text (lecture notes, study guides)
- Word documents (course materials)

Each file is split into chunks and embedded as vectors for semantic search. Processing status shows as "completed" when ready.

### Ingest Content Tab
Import from external sources:
- **Web pages** — paste a URL to scrape and ingest
- **YouTube videos** — paste a URL to ingest the transcript

### Query Tab
Test retrieval by entering a search query. Shows the most relevant chunks with similarity scores. Use this to verify your documents are properly indexed before connecting to an assistant.

<a id="connecting-a-kb-to-an-assistant"></a>
## Connecting a KB to an Assistant

1. Edit your assistant
2. Set RAG Processor to one of:
   - **Simple Rag** — basic retrieval, good for most cases
   - **Context Aware Rag** — more sophisticated context handling
   - **Rubric Rag** — specialized for rubric-based evaluation
3. Set **RAG Top K** (1-10, default 3) — how many document chunks to retrieve
4. Check the Knowledge Bases to connect (checkboxes appear when RAG is selected)
5. Ensure your Prompt Template includes `{context}` and `{user_input}` placeholders

**Critical:** If your prompt template does not contain `{context}`, the retrieved content has nowhere to go and the assistant will ignore your documents.

<a id="sharing-knowledge-bases"></a>
## Sharing Knowledge Bases

Click the Share button to make a KB available to other educators in your organization. They can connect it to their assistants but cannot modify the content.

<a id="common-issues"></a>
## Common Issues

- **Empty context in bypass test** — KB not ingested, wrong collection ID, or prompt template missing `{context}`
- **Garbage retrieval** — document chunk size too small; re-upload with better formatting
- **"No results"** — KB has no files, or files are still processing (check status)
