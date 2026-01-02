# MarkItDown Plus - User Guide

## What is this plugin?

**MarkItDown Plus** is a tool that converts your documents (PDFs, Word files, PowerPoints, etc.) into a format that can be searched and queried by AI assistants. It breaks your documents into smaller pieces called "chunks" and stores them in a knowledge base.

Think of it like creating an index for a book: instead of reading the entire book to find information, the AI can quickly look up relevant sections.

---

## Privacy & Security

### 🔒 Your documents stay private by default

**Important:** This tool processes your documents **on our servers** (locally) by default. Your content is NOT sent to external services like OpenAI unless you specifically choose to do so.

| Setting | What happens to your data |
|---------|--------------------------|
| Image descriptions: **None** (default) | ✅ Everything stays local. No external services used. |
| Image descriptions: **Basic** | ✅ Everything stays local. Images are extracted and saved. |
| Image descriptions: **AI-powered** | ⚠️ Images are sent to OpenAI for description. |

**Recommendation:** For confidential documents, employee records, financial data, or any sensitive information, always use "None" or "Basic" mode.

---

## Understanding the Options

### 1. Image Handling

When your document contains images (charts, diagrams, photos), you can choose how to handle them:

#### Option: None (Recommended for sensitive documents)
- **What it does:** Keeps any existing image references but doesn't extract or process images
- **Best for:** Confidential documents, fastest processing
- **Privacy:** ✅ Completely local

#### Option: Basic
- **What it does:** Extracts images from your document and saves them with simple descriptions based on filenames
- **Best for:** Documents where you want images accessible but don't need detailed descriptions
- **Privacy:** ✅ Completely local

#### Option: AI-powered (LLM)
- **What it does:** Sends images to OpenAI's AI to generate detailed, intelligent descriptions
- **Best for:** Educational materials, public documents where image context matters
- **Privacy:** ⚠️ **Images are sent to OpenAI** - Do NOT use for confidential documents

---

### 2. How to Split Your Document (Chunking Mode)

Your document needs to be divided into smaller pieces for the AI to search effectively. There are three ways to do this:

#### Option: Standard (Default)
- **What it does:** Splits your document into pieces of roughly equal size (measured in characters)
- **Best for:** General documents, emails, articles, unstructured text
- **How it works:** Like cutting a long ribbon into equal pieces

**Additional settings for Standard mode:**
- **Chunk size:** How big each piece should be (default: 1000 characters, roughly 150-200 words)
- **Overlap:** How much text is repeated between pieces to maintain context (default: 200 characters)

*Tip: Smaller chunks (500-800) work better for Q&A. Larger chunks (1500-2500) work better for summaries.*

#### Option: By Page
- **What it does:** Keeps each page as a separate piece
- **Best for:** PDFs, presentations, documents where page breaks are meaningful
- **Works with:** PDF, Word (.docx), PowerPoint (.pptx) only

**Additional settings for Page mode:**
- **Pages per chunk:** How many pages to group together (default: 1)

*Example: A 10-page PDF with "Pages per chunk: 2" creates 5 chunks, each containing 2 pages.*

#### Option: By Section
- **What it does:** Uses your document's headings (titles, subtitles) to create natural divisions
- **Best for:** Reports, manuals, structured documents with clear sections
- **How it works:** Respects your document's organization

**Additional settings for Section mode:**
- **Split on heading level:** Which heading level defines a chunk
  - Level 1 = Main titles (# Heading)
  - Level 2 = Subtitles (## Heading) - *recommended*
  - Level 3 = Sub-subtitles (### Heading)
- **Sections per chunk:** How many sections to group together (default: 1)

*Example: A report with chapters and sections, using "Level 2" and "1 section per chunk" creates one chunk per section, with chapter titles preserved for context.*

---

## Practical Examples

### Example 1: Company Policy Document (Confidential)

**Scenario:** You're uploading an employee handbook with sensitive HR policies.

**Recommended settings:**
- Image handling: **None**
- Chunking mode: **By Section**
- Split on heading: **2** (to capture each policy section)
- Sections per chunk: **1**

**Why:** Keeps everything private, respects the document structure, makes it easy to find specific policies.

---

### Example 2: Product Catalog with Photos

**Scenario:** You're uploading a product catalog with many images that need descriptions.

**Recommended settings:**
- Image handling: **Basic** (or AI-powered if descriptions are crucial and content isn't sensitive)
- Chunking mode: **By Page**
- Pages per chunk: **1**

**Why:** Each product page stays together, images are accessible.

---

### Example 3: Research Paper

**Scenario:** You're uploading an academic paper for research purposes.

**Recommended settings:**
- Image handling: **Basic** (to extract figures and charts)
- Chunking mode: **By Section**
- Split on heading: **2**
- Sections per chunk: **1**

**Why:** Respects the paper's structure (Abstract, Introduction, Methods, etc.), keeps figures accessible.

---

### Example 4: Large Text Document

**Scenario:** You're uploading a long document without clear structure (like a transcript or novel).

**Recommended settings:**
- Image handling: **None**
- Chunking mode: **Standard**
- Chunk size: **1000**
- Overlap: **200**

**Why:** Standard mode works best for unstructured text, overlap ensures context isn't lost between pieces.

---

## Frequently Asked Questions

### Q: What happens if I choose "By Section" but my document has no headings?

The system automatically falls back to "Standard" mode. You'll get evenly-sized chunks instead.

### Q: How do I know which chunk size to use?

- **For question-answering:** Smaller chunks (500-1000) work better because they're more focused
- **For summarization:** Larger chunks (1500-2500) provide more context
- **When in doubt:** The default (1000) works well for most cases

### Q: What file types are supported?

PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx, .xls), HTML, audio files (.mp3, .wav), CSV, JSON, XML, ZIP archives, and EPUB e-books.

### Q: Will my original file be preserved?

Yes! The original file is saved, and a Markdown version is also created for easier viewing.

### Q: How long does processing take?

It depends on the file size and options chosen:
- Small documents (< 10 pages): A few seconds
- Large documents with AI image descriptions: Several minutes

---

## Getting Help

If you have questions or encounter issues:
1. Check that your file is in a supported format
2. Try with default settings first
3. Contact your system administrator for assistance

---

*Last updated: January 2026*

