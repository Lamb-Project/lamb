# LAMB Platform -- Stakeholder Summary

**Version:** 1.0
**Date:** February 15, 2026
**Audience:** Teachers, Institution Administrators, System Administrators

---

## Table of Contents

1. [What is LAMB?](#1-what-is-lamb)
2. [The Philosophy: Safe AI in Education](#2-the-philosophy-safe-ai-in-education)
3. [Who is LAMB For?](#3-who-is-lamb-for)
4. [Key Capabilities](#4-key-capabilities)
5. [How It Works -- For Teachers](#5-how-it-works--for-teachers)
6. [How It Works -- LTI Integration with Moodle](#6-how-it-works--lti-integration-with-moodle)
7. [How It Works -- For Institution Administrators](#7-how-it-works--for-institution-administrators)
8. [How It Works -- For System Administrators](#8-how-it-works--for-system-administrators)
9. [AI-Assisted Evaluation: Evaluaitor & LAMBA](#9-ai-assisted-evaluation-evaluaitor--lamba)
10. [Architecture at a Glance](#10-architecture-at-a-glance)
11. [Privacy and Data Sovereignty](#11-privacy-and-data-sovereignty)
12. [Glossary](#12-glossary)

---

## 1. What is LAMB?

**LAMB** (Learning Assistants Manager and Builder) is an open-source platform that empowers educators to create, manage, and deploy AI-powered learning assistants directly into Learning Management Systems (like Moodle) -- **without writing any code**.

Think of LAMB as a **"teaching chatbot builder"**: it lets educators combine large language models (GPT-4, Mistral, locally-hosted models, etc.) with their own course materials to create specialized AI tutors that students can access right from within Moodle.

### The One-Sentence Pitch

> **LAMB gives educators total control to build a "specialized ChatGPT" for their subject, connect it to Moodle, and keep students' data completely secure.**

### Core Value Proposition

| For... | LAMB provides... |
|--------|------------------|
| **Teachers** | A no-code builder to create AI tutors grounded in course materials |
| **Institutions** | AI deployment while maintaining data sovereignty and privacy |
| **Students** | Context-aware, subject-specific AI assistance within their familiar LMS |

### Academic Foundation

LAMB is not a commercial startup product. It is developed by university researchers and has been peer-reviewed:

> *"LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems"*
> Marc Alier, Juanan Pereira, Francisco Jose Garcia-Penalvo, Maria Jose Casan, Jose Cabre
> *Computer Standards & Interfaces*, Volume 92, March 2025

The project is led by **Marc Alier** (Universitat Politecnica de Catalunya, Barcelona) and **Juanan Pereira** (Universidad del Pais Vasco / Euskal Herriko Unibertsitatea, Basque Country), with collaboration from Universidad de Salamanca (Grial Research Group) and Tknika (Basque VET Applied Research Centre).

---

## 2. The Philosophy: Safe AI in Education

LAMB is built on the principles of the **Safe AI in Education Manifesto** (https://manifesto.safeaieducation.org), a framework signed by 87+ academics worldwide, including Dr. Charles Severance (University of Michigan, creator of Coursera).

The manifesto's core belief: **"AI should always be at the service of people, enhancing human capabilities rather than replacing them."**

### The Seven Principles

| # | Principle | What It Means for Education | How LAMB Implements It |
|---|-----------|----------------------------|----------------------|
| 1 | **Human Oversight** | All decisions remain under human supervision. AI cannot be responsible for educating students. | Educators create, control, and manage all assistants. Every assistant's behavior is defined by the educator. |
| 2 | **Privacy Protection** | Student data must be safeguarded. Students retain full control over personal data. | Self-hosted infrastructure. No student data leaves the institution. No PII sent to external LLM providers without explicit institutional configuration. |
| 3 | **Educational Alignment** | AI must support institutional educational strategies, not undermine them. | Assistants are grounded in specific course materials and learning objectives. They only answer within the educator's defined scope. |
| 4 | **Didactic Integration** | AI must fit seamlessly into existing teaching workflows. | LTI integration embeds assistants directly into Moodle courses. No separate logins or platforms for students. |
| 5 | **Accuracy & Explainability** | AI responses must be accurate and traceable. | RAG (Retrieval-Augmented Generation) provides automatic source citations. Debug mode lets educators inspect exactly what the AI "sees." |
| 6 | **Transparent Interfaces** | Interfaces must clearly communicate AI limitations. | Clear communication that responses are AI-generated. Source documents are cited when referenced. |
| 7 | **Ethical Training** | AI models must be ethically trained with transparency about data sources. | Open-source platform. Educators choose their LLM provider. Full transparency about what models are used. |

### Why Not Just Use ChatGPT or Google Gemini?

The manifesto and LAMB address a real concern: when educators use commercial AI platforms directly, they:

- **Surrender their knowledge** -- prompts and materials become training data for the provider
- **Expose student data** -- student identities, questions, and behavior are processed by third parties
- **Have no transparency** -- how the model behaves, what data it retains, and how it evolves are opaque
- **Cannot customize behavior** -- no way to restrict answers to course materials or enforce pedagogical approaches
- **Risk vendor lock-in** -- switching providers means rebuilding everything

LAMB solves all of these by giving the institution full control over the entire stack.

---

## 3. Who is LAMB For?

### Teachers (Creator Users)

Teachers are the primary users of LAMB. They use the **Creator Interface** -- a web-based, no-code environment -- to:

- Create AI assistants specialized for their courses
- Build knowledge bases from multiple sources: file uploads (PDF, Word, PowerPoint, spreadsheets, Markdown), web URLs and crawled websites, and YouTube video transcripts
- Configure how the AI behaves (system prompts, model selection, RAG settings)
- Create structured assessment rubrics and attach them to assistants for AI-assisted evaluation (Evaluaitor)
- Set up grading activities where students submit work, the AI proposes an evaluation based on a rubric, and the teacher reviews and decides the final grade (LAMBA)
- Test assistants before publishing them to students
- Publish assistants as LTI activities in Moodle
- View analytics on how students use their assistants

**No programming skills required.** The AI never grades autonomously -- it assists the teacher by proposing evaluations, but the teacher always reviews, edits, and confirms the final grade. A teacher can create and publish their first assistant in about 15 minutes.

### Institution Administrators (Organization Admins)

Organization admins manage their department or institution within LAMB:

- Manage users within their organization (create, enable/disable)
- Configure AI providers (API keys, available models)
- Set signup policies (open registration vs. invitation-only)
- Enable/disable features like assistant sharing
- Manage LTI Creator access for their organization

### System Administrators (Sys Admins)

System administrators manage the LAMB deployment itself:

- Deploy and maintain the LAMB infrastructure
- Create and manage organizations (multi-tenancy)
- Configure global LLM providers and API keys
- Manage system-wide users and roles
- Configure LTI credentials
- Monitor system health and performance

---

## 4. Key Capabilities

### For Teaching

| Capability | Description |
|-----------|-------------|
| **Unlimited Assistants** | Create as many AI assistants as needed, each with unique behavior |
| **Specialized Subject Tutors** | Assistants that only answer within the educator's defined course context |
| **Knowledge Base (RAG)** | Ingest content from files (PDF, Word, PowerPoint, spreadsheets), web URLs, website crawling, and YouTube video transcripts -- the AI uses these as its "textbook" |
| **Automatic Citations** | When the AI references uploaded materials, it cites the source |
| **Multiple AI Models** | Switch between GPT-4o, Mistral, Llama, and other models with one click |
| **Debug Mode** | See the complete prompt sent to the AI, enabling fine-tuning |
| **LTI Publishing** | Publish assistants as Moodle activities with a few clicks |
| **Assistant Sharing** | Share assistants with colleagues in the same organization |
| **Rubric-Based Evaluators** | Create structured assessment rubrics (manually or AI-generated) and attach them to assistants for consistent AI-assisted evaluation |
| **AI-Assisted Evaluation (LAMBA)** | Students submit assignments via LTI; the AI proposes an evaluation against rubrics; the teacher reviews, edits, and decides the final grade; scores sync to Moodle |
| **Chat Analytics** | View how students interact with your assistants |
| **Multilingual** | Interface available in English, Spanish, Catalan, and Basque |

### For Administration

| Capability | Description |
|-----------|-------------|
| **Multi-Tenancy** | Isolated organizations with independent configuration |
| **User Management** | Create, enable/disable, and manage user accounts |
| **Role-Based Access** | System admin, org admin, creator, end user roles |
| **LLM Provider Flexibility** | Configure OpenAI, Anthropic, Ollama, or other providers per organization |
| **Signup Keys** | Organization-specific registration with secret keys |
| **LTI Creator Access** | Educators can access LAMB directly from Moodle via LTI |

### For Infrastructure

| Capability | Description |
|-----------|-------------|
| **Self-Hosted** | Deploy on your own servers -- full data sovereignty |
| **Docker Deployment** | Single-command deployment with Docker Compose |
| **OpenAI-Compatible API** | Standard `/v1/chat/completions` endpoint for integration |
| **Plugin Architecture** | Extensible connectors for new LLM providers |
| **SQLite Database** | Simple, file-based database (no separate DB server needed) |

---

## 5. How It Works -- For Teachers

### The Teacher Workflow (15 Minutes to First Assistant)

#### Step 1: Sign In
Log in to the LAMB Creator Interface with your institutional credentials (or via LTI from Moodle).

#### Step 2: Create an Assistant
Give your assistant a name and description. Choose an AI model (e.g., GPT-4o-mini for fast responses, GPT-4o for complex reasoning).

#### Step 3: Define Behavior
Write a **system prompt** that tells the AI how to behave. For example:

> *"You are a tutor for Introduction to Computer Science. Answer only questions related to algorithms, data structures, and programming fundamentals. When students ask about topics outside the course, politely redirect them. Always encourage students to think through problems before giving direct answers."*

#### Step 4: Build a Knowledge Base (Optional but Recommended)
Add your course materials from multiple sources:
- **Upload files** -- lecture notes, textbook chapters, problem sets (PDF, Word, PowerPoint, spreadsheets, Markdown, and more)
- **Ingest from URLs** -- point to a webpage or let the crawler follow links across a site
- **Import YouTube videos** -- automatically extract and index video transcripts

LAMB processes and indexes all content so the AI can reference it when answering questions.

#### Step 5: Configure RAG
Connect your knowledge base to the assistant. Configure how many chunks of context to retrieve (Top K). The AI will now ground its answers in your actual course materials and cite sources.

#### Step 6: Test
Use the built-in chat interface to test your assistant. Ask it questions your students might ask. Use **debug mode** to see exactly what prompt and context the AI receives.

#### Step 7: Publish to Moodle
Click "Publish." LAMB generates LTI credentials (Tool URL, Consumer Key, Secret). Add these to Moodle as an External Tool activity. Students can now access the assistant directly from their course page.

### Two Ways to Access LAMB as a Teacher

1. **Direct Login** -- Navigate to the LAMB URL and log in with email/password
2. **LTI Creator Launch** -- Click an LTI link in Moodle and land directly in the Creator Interface (no separate password needed). This is configured by your organization admin.

---

## 6. How It Works -- LTI Integration with Moodle

LTI (Learning Tools Interoperability) is the standard protocol that connects LAMB to Moodle. LAMB supports three LTI integration modes:

### 6.1 Unified LTI (Recommended for New Deployments)

The **Unified LTI** approach uses a single LTI tool for the entire LAMB instance. It is the most flexible and feature-rich option.

**How it works:**

1. The system admin configures **one set of global LTI credentials** for the entire LAMB instance
2. A Moodle admin adds LAMB as an External Tool using these global credentials
3. Teachers add LAMB activities to their courses in Moodle
4. **First-time setup:** When a teacher clicks the activity for the first time, they see a setup page where they select which published assistants to make available
5. **After setup:** Students who click the activity see the selected assistants and can start chatting
6. **Instructor dashboard:** Teachers get a dashboard showing usage statistics, student access logs, and (if enabled) anonymized chat transcript review

**Key features:**
- Multiple assistants per activity (students can choose)
- Instructor dashboard with usage stats
- Optional chat visibility (anonymized transcripts for pedagogical review)
- Student consent flow when chat visibility is enabled
- One set of LTI credentials for the whole instance

**Student experience:**
1. Click the activity link in Moodle
2. (If chat visibility is enabled and first access) Accept a consent notice
3. See the available assistants and start chatting
4. Everything happens within Moodle -- no separate login needed

### 6.2 Legacy LTI (Single Assistant per Activity)

The older approach where each published assistant has its own LTI credentials. Still supported but less flexible.

**How it works:**
1. Teacher publishes an assistant in LAMB
2. LAMB generates unique LTI consumer key and secret for that assistant
3. Teacher adds these as an External Tool in Moodle
4. Students click the link and go directly to that one assistant

### 6.3 LTI Creator (Teacher Access to LAMB from Moodle)

This mode lets teachers access the LAMB Creator Interface itself through Moodle, eliminating the need for separate LAMB login credentials.

**How it works:**
1. Organization admin configures LTI Creator credentials
2. Moodle admin adds LAMB Creator as an External Tool
3. When a teacher clicks the link, they land directly in the LAMB Creator Interface
4. Their identity is linked to their LMS account -- no separate password needed
5. They can create and manage assistants as usual

---

## 7. How It Works -- For Institution Administrators

### Organization Management

LAMB uses a **multi-tenant** model where each institution, department, or team is an **organization**. Organizations provide complete isolation:

- Each organization has its own users, assistants, and knowledge bases
- Each organization configures its own AI providers and API keys
- Users in one organization cannot see resources from another

### Key Responsibilities

#### User Management
- Create accounts for teachers (creator users) and end users
- Enable/disable user accounts
- Set user roles within the organization (admin, member)
- Manage LTI Creator users who access via Moodle

#### AI Provider Configuration
- Configure which AI providers are available (OpenAI, Anthropic, Ollama, etc.)
- Set API keys for each provider
- Define default models
- Control which models teachers can use

#### Access Policies
- Enable/disable open signup for the organization
- Set a signup key for self-registration
- Enable/disable assistant sharing between teachers
- Configure LTI Creator access credentials

#### User Types

| User Type | Access | Purpose |
|-----------|--------|---------|
| **Creator** | Creator Interface (assistant builder) | Teachers who create and manage assistants |
| **End User** | Chat interface only (Open WebUI) | Users who only need to interact with published assistants |
| **LTI Creator** | Creator Interface (via Moodle LTI) | Teachers who access LAMB through their LMS |

---

## 8. How It Works -- For System Administrators

### Deployment

LAMB is designed for **self-hosted deployment** using Docker Compose. The stack includes:

| Service | Port | Purpose |
|---------|------|---------|
| **Backend** (FastAPI) | 9099 | Core API, authentication, completions pipeline |
| **Frontend** (Svelte) | 5173 (dev) | Creator Interface web application |
| **Open WebUI** | 8080 | Chat interface for students and end users |
| **KB Server** | 9090 | Knowledge base document processing and vector search |

### Quick Start
```bash
git clone https://github.com/Lamb-Project/lamb.git
cd lamb
./scripts/setup.sh
docker-compose up -d
```

### Key Configuration

| Variable | Purpose |
|----------|---------|
| `LAMB_DB_PATH` | Path to LAMB database directory |
| `OWI_DATA_PATH` | Path to Open WebUI data directory |
| `LAMB_BEARER_TOKEN` | API key for completions endpoint (**change from default!**) |
| `LAMB_JWT_SECRET` | Secret for signing JWT tokens (**set to a secure value!**) |
| `OPENAI_API_KEY` | Default OpenAI API key (can be overridden per org) |
| `LTI_GLOBAL_CONSUMER_KEY` | Global LTI consumer key for Unified LTI |
| `LTI_GLOBAL_SECRET` | Global LTI shared secret |
| `OWI_BASE_URL` | Internal URL for Open WebUI |
| `OWI_PUBLIC_BASE_URL` | Public-facing URL for Open WebUI |

### System Administration Tasks

- **Create organizations** -- Set up isolated tenants for departments or institutions
- **Manage global users** -- Create system admin accounts, manage all users
- **Configure LTI** -- Set up global LTI credentials for Unified LTI
- **Monitor health** -- `GET /status` endpoint for health checks
- **Database backups** -- Back up SQLite database files regularly
- **SSL/TLS** -- Configure HTTPS via Caddy or reverse proxy
- **LLM provider management** -- Configure system-level defaults, monitor API usage

### Production Checklist

- [ ] Change `LAMB_BEARER_TOKEN` from default value
- [ ] Set `LAMB_JWT_SECRET` to a secure random value
- [ ] Configure SSL/TLS (Caddy recommended)
- [ ] Set up regular database backups
- [ ] Configure organization-specific LLM API keys
- [ ] Set logging level (`GLOBAL_LOG_LEVEL=WARNING` for production)
- [ ] Set up system monitoring
- [ ] Test LTI integration end-to-end

### Multi-Tenancy Architecture

```
System Organization (always exists, cannot be deleted)
    |
    +-- Department A (slug: "engineering")
    |   +-- Users (with roles: owner, admin, member)
    |   +-- Assistants
    |   +-- Knowledge Bases
    |   +-- Independent LLM provider config
    |
    +-- Department B (slug: "physics")
    |   +-- Users
    |   +-- Assistants
    |   +-- Knowledge Bases
    |   +-- Independent LLM provider config
    |
    +-- Partner Institution (slug: "partner-univ")
        +-- ...
```

---

## 9. AI-Assisted Evaluation: Evaluaitor & LAMBA

LAMB includes a built-in **Evaluaitor** system for rubric-based assessment, and the **LAMBA** (Learning Activities & Machine-Based Assessment) application is being merged into the platform to provide a complete AI-assisted evaluation pipeline. Critically, **the AI never grades autonomously** -- it proposes evaluations that the teacher must review, edit if needed, and explicitly approve before any grade reaches the student. This is a direct application of Manifesto Principle 1 (Human Oversight).

### 9.1 Evaluaitor: Rubric-Based Assessment

The Evaluaitor is LAMB's rubric management system. It lets teachers create structured assessment rubrics and attach them to assistants, turning any assistant into a consistent AI evaluator.

#### Creating Rubrics

Teachers can create rubrics in three ways:

1. **Manual creation** -- Define criteria, performance levels, weights, and scoring from scratch
2. **AI generation** -- Describe what you want to assess in natural language and the AI generates a complete rubric (supports English, Spanish, Catalan, and Basque)
3. **From templates** -- Duplicate a public rubric shared by colleagues or promoted by admins as a showcase template

#### Rubric Structure

Each rubric contains:
- **Title and description** -- What is being assessed
- **Criteria** -- The dimensions of assessment (e.g., "Content Quality", "Critical Thinking"), each with a weight
- **Performance levels** -- Descriptions for each quality tier (e.g., Exemplary / Proficient / Developing / Beginning) with scores
- **Scoring type** -- Points, percentage, holistic, single-point, or checklist
- **Metadata** -- Subject area, grade level

#### Using Rubrics with Assistants

When a rubric is attached to an assistant, LAMB's completion pipeline automatically injects the rubric into the AI's context with evaluation-optimized formatting -- including scoring instructions, weight calculations, and expected output format. This means the AI produces consistent proposed evaluations against the rubric's specific criteria, which the teacher then reviews and finalizes.

#### Sharing and Templates

- Rubrics can be **private** (only the creator sees them) or **public** (visible to all members of the organization)
- Admins can promote rubrics as **showcase templates** available across the platform
- Rubrics can be **exported/imported** as JSON for sharing between institutions

### 9.2 LAMBA: The Grading Pipeline (Being Merged)

LAMBA started as a separate LTI application and is now being integrated directly into LAMB. It provides the full evaluation lifecycle through Moodle:

#### The Evaluation Workflow

1. **Teachers create evaluation activities** in Moodle via LTI and assign a rubric-based evaluator assistant
2. **Students upload documents** (PDF, Word, TXT, source code) through the Moodle interface
3. **AI proposes evaluations** -- the assistant analyzes each submission against the rubric and produces a suggested score and written feedback
4. **Teachers review the AI's proposals** -- they can accept, edit, or completely override the suggested score and feedback for each student
5. **Teachers confirm the final grade** -- only the teacher-approved grade is the real grade
6. **Final grades sync back to Moodle's gradebook** via LTI

#### Key Features

| Feature | Description |
|---------|-------------|
| **Rubric-Driven Proposals** | AI proposes evaluations against structured rubrics, giving the teacher a consistent starting point |
| **Teacher Has Final Say** | The AI's suggestion and the actual grade are separate fields -- the teacher must explicitly move the proposed evaluation to the final grade, editing it as needed |
| **Group Submissions** | Supports group assignments with shared submission codes |
| **Moodle Grade Sync** | Only teacher-confirmed final grades are pushed to the Moodle gradebook |
| **Batch Processing** | Request AI proposals for all submissions at once with real-time progress tracking |
| **Human Oversight** | The AI assists; the teacher decides -- consistent with Manifesto Principle 1 |

#### Goal

Reduce teacher evaluation workload by **50%** on routine assessments, delivering proposed feedback in minutes instead of days. The AI provides a consistent, rubric-based starting point, but **the teacher always retains full authority over the final grade**.

---

## 10. Architecture at a Glance

```
+------------------------------------------------------------------+
|                         LAMB Platform                            |
|                                                                  |
|   +----------------+    +----------------+    +----------------+ |
|   |   Creator      |    |   Backend      |    |   Open WebUI   | |
|   |   Interface    |<-->|   (FastAPI)     |<-->|   (Chat UI)    | |
|   |   (Svelte)     |    |   Port 9099    |    |   Port 8080    | |
|   +----------------+    +-------+--------+    +----------------+ |
|          |                      |                      |         |
|    Teachers use           Core logic            Students use     |
|    this to build          & API                 this to chat     |
|    assistants                   |                                |
|                          +------+-------+                        |
|                          |  KB Server   |                        |
|                          |  Port 9090   |                        |
|                          +--------------+                        |
|                                 |                                |
|                          +------+-------+                        |
|                          | LLM Provider |                        |
|                          | OpenAI/Ollama|                        |
|                          +--------------+                        |
+------------------------------------------------------------------+
         |                                           |
    LTI Creator                                 LTI Student
    (Teachers access                            (Students access
     LAMB from Moodle)                           assistants from Moodle)
         |                                           |
+------------------------------------------------------------------+
|                     Moodle (LMS)                                 |
+------------------------------------------------------------------+
```

### How a Student's Question Gets Answered

1. Student types a question in the chat interface (Open WebUI, launched via LTI)
2. The question goes to LAMB's completions API
3. LAMB loads the assistant's configuration (system prompt, model, RAG settings)
4. **RAG Processor** queries the knowledge base for relevant content from uploaded documents
5. **Prompt Processor** combines the system prompt, retrieved context, and student's question
6. **Connector** sends everything to the configured LLM (e.g., OpenAI GPT-4o)
7. The LLM response streams back to the student with source citations

---

## 11. Privacy and Data Sovereignty

### Where Data Lives

| Data | Location | Who Controls It |
|------|----------|----------------|
| User accounts | LAMB database (institution's server) | Institution |
| Assistant configurations | LAMB database | Educator + institution |
| Course materials (KBs) | ChromaDB on institution's server | Educator + institution |
| Chat history | Open WebUI database on institution's server | Institution |
| Student interactions | Institution's server | Institution |

### What Does NOT Leave the Institution

- Student identities and personal data
- Chat conversations and interaction history
- Uploaded course materials and knowledge bases
- Usage analytics and evaluation data

### What Goes to External Services (Configurable)

- **Only the text of questions and context** is sent to the configured LLM provider (OpenAI, etc.)
- This can be **eliminated entirely** by using locally-hosted models (Ollama with Llama, Mistral, etc.)
- The institution chooses which LLM provider to use and can change at any time

### GDPR and FERPA Alignment

- Self-hosted: full compliance with data residency requirements
- No mandatory third-party registrations for students
- Students access assistants through their existing LMS -- no new accounts needed
- Clear data retention under institutional control
- Optional chat visibility requires explicit student consent

---

## 12. Glossary

| Term | Definition |
|------|-----------|
| **Assistant** | An AI-powered chatbot configured by a teacher with specific behavior, knowledge, and model settings |
| **Creator Interface** | The web-based UI where teachers build and manage assistants |
| **Knowledge Base (KB)** | A collection of uploaded documents that the AI can reference when answering questions |
| **RAG** | Retrieval-Augmented Generation -- the technique of retrieving relevant document chunks to include in AI prompts |
| **LTI** | Learning Tools Interoperability -- the standard protocol for connecting external tools to an LMS |
| **LMS** | Learning Management System (e.g., Moodle, Canvas) |
| **Organization** | An isolated tenant in LAMB (department, institution, or team) with its own users and configuration |
| **Open WebUI (OWI)** | The chat interface component where students interact with published assistants |
| **System Prompt** | Instructions that define how an AI assistant behaves (persona, rules, limitations) |
| **Connector** | A plugin that connects LAMB to a specific LLM provider (OpenAI, Ollama, Anthropic) |
| **Unified LTI** | The recommended LTI mode where one tool serves multiple assistants per activity |
| **LTI Creator** | An LTI mode that lets teachers access the Creator Interface from within Moodle |
| **Evaluaitor** | LAMB's built-in rubric management system for creating structured assessment criteria |
| **Rubric** | A structured set of criteria with performance levels and weights used to evaluate student work consistently |
| **LAMBA** | Learning Activities & Machine-Based Assessment -- the AI-assisted evaluation pipeline (being merged into LAMB). The AI proposes evaluations; the teacher decides the final grade. |
| **Manifesto** | The Safe AI in Education Manifesto -- the ethical framework guiding LAMB's design |

---

## Key Links

| Resource | URL |
|----------|-----|
| LAMB GitHub Repository | https://github.com/Lamb-Project/lamb |
| LAMB Project Website | https://lamb-project.org |
| LAMBA (Grading Extension) | https://github.com/Lamb-Project/LAMBA |
| Safe AI in Education Manifesto | https://manifesto.safeaieducation.org |
| Manifesto Checklist | https://manifesto.safeaieducation.org/checklist |
| Research Paper (DOI) | https://doi.org/10.1016/j.csi.2024.103940 |

---

*This document was prepared as stakeholder training material for the LAMB project.*
*Last updated: February 15, 2026*
