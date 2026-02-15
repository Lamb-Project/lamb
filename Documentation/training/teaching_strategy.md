# LAMB Training Course -- Teaching Strategy

**Version:** 1.0
**Date:** February 15, 2026
**Status:** Draft
**Audience:** Course designers, instructors

---

## 1. Course Identity

**Title:** *Building AI Learning Assistants with LAMB -- A Hands-On Course for Educators*

**Format:** Hybrid (asynchronous Moodle course + synchronous AMA sessions)

**Duration:** 3-4 weeks (flexible, drip-fed content)

**Platform:** Moodle with LAMB integrated via LTI

**Target Audience:** University lecturers and professors who want to create AI-powered learning assistants for their courses. No programming skills required.

---

## 2. Pedagogical Philosophy

### 2.1 Learn by Doing, Not by Watching

Every piece of content has a clear, achievable **call to action**. Participants never just watch -- they always do something concrete with LAMB immediately after. The goal is that by the end of the course, every participant has at least one functional, published assistant grounded in their own course materials.

### 2.2 Eat Our Own Dogfood

The course itself is built on LAMB. Participants experience LAMB from the student side (interacting with a course assistant, having their work evaluated by LAMBA) while simultaneously learning to be creators. This dual perspective is intentional -- they feel what their students will feel.

### 2.3 Community-Driven Content

The forum is not a support channel -- it is a **content engine**. Participant questions, frustrations, and ideas become screencasts, FAQ entries, and feature discussions. The course grows richer with every cohort. Participants are explicitly told: your questions make this course better for everyone.

### 2.4 Drip-Feed, Not Firehose

Content is released every 1-2 days in short, focused videos (5-10 minutes max). This creates a rhythm: watch, do, share, discuss. It prevents overwhelm and gives instructors time to respond to the forum before the next release.

### 2.5 Manifesto Alignment

The course embodies the Safe AI in Education Manifesto principles in its own design:
- **Human Oversight** -- The instructor is present, responsive, and drives the conversation
- **Privacy** -- Participants use an institutionally-hosted LAMB instance
- **Didactic Integration** -- The course runs inside Moodle, the same environment participants already use
- **Transparency** -- Participants see how the AI assistant works from the inside (debug mode, prompt inspection)

---

## 3. Learning Objectives

By the end of the course, participants will be able to:

### Week 1: Experience and First "Wow" (Foundational)
1. Experience LAMB assistants as an end user -- feel what students will feel
2. Explain what LAMB is and why it exists (privacy, control, manifesto principles)
3. Log into LAMB from Moodle via LTI Creator and navigate the Creator Interface
4. Create a first assistant with a system prompt and a single attached file (single file RAG) -- instant context with zero setup complexity
5. Test the assistant and see it answer questions from your own course material

### Week 2: Deep Knowledge and Refinement (Intermediate)
6. Build a full knowledge base from multiple sources (files, URLs, YouTube)
7. Connect a knowledge base to an assistant (RAG configuration, Top K)
8. Understand the difference between single file RAG and full knowledge bases
9. Test and debug an assistant using debug mode
10. Iterate on system prompts to improve assistant behavior

### Week 3: Publishing, Assessment, and Beyond (Advanced)
11. Publish an assistant as an LTI activity in a Moodle course
12. Create an assessment rubric using Evaluaitor (manually or AI-generated)
13. Attach a rubric to an assistant for AI-assisted evaluation
14. Understand the LAMBA evaluation workflow (AI proposes, teacher decides)

### Meta-Learning (Throughout)
13. Experience LAMB from the student perspective (interacting with the course assistant)
14. Experience AI-assisted evaluation from the student perspective (LAMBA)
15. Critically evaluate the role of AI in their own teaching context

---

## 4. Course Infrastructure

### 4.1 Moodle Course Structure

```
LAMB Training Course (Moodle)
|
+-- Announcements (teacher messages channel)
|     One-way channel for instructor updates, new video releases,
|     and responses to common questions.
|
+-- Discussion Forum (open to all)
|     The heart of the course. Participants post questions,
|     feature requests, frustrations, ideas, and wins.
|     Instructor responds with text or short screencasts.
|
+-- Demo Assistants (LTI External Tool -- Unified LTI)
|     Pre-built assistants for Week 1 end-user experience.
|     Participants interact as students before becoming creators.
|     Examples: a history tutor, a math helper, a language coach.
|
+-- LAMB Creator Access (LTI External Tool -- LTI Creator)
|     LTI Creator link -- one click lands participants
|     directly in the LAMB Creator Interface.
|     No separate credentials needed.
|
+-- Course AI Assistant (LTI External Tool -- Unified LTI)
|     A LAMB assistant loaded with all video transcriptions
|     and course documentation. Participants can ask it
|     questions and it redirects them to the right video
|     and timestamp.
|
+-- Content Modules (one per video/topic)
|     +-- Video (embedded or linked)
|     +-- Written summary / transcript
|     +-- Call to action (concrete task)
|     +-- Optional: link to relevant documentation
|
+-- Final Deliverable
|     Submit a link/description of their published assistant.
|     Evaluated via LAMBA with a rubric.
|
+-- AMA Sessions (2-3 scheduled videoconferences)
      Calendar events with videoconference links.
```

### 4.2 LAMB Setup

**LTI Creator:** Participants are provisioned as `lti_creator` users in a dedicated training organization. They access LAMB directly from Moodle with no separate login.

**Demo Assistants (Week 1):** 2-3 pre-built assistants published via Unified LTI for the end-user experience in the first days. These should be polished, diverse (different subjects, different tones), and demonstrate what a well-crafted assistant looks and feels like. Participants chat with these before they build their own -- setting the bar for what they're working toward.

**Course Assistant:** A published LAMB assistant whose knowledge base contains:
- All video transcriptions (with timestamps and video identifiers)
- The stakeholder summary document
- FAQ entries generated from forum questions

The assistant's system prompt instructs it to:
- Answer questions about LAMB
- Reference specific videos and timestamps when relevant (e.g., "This is covered in Video 5 at 3:20")
- Redirect to the forum for questions it cannot answer
- Be transparent about being an AI assistant built with LAMB itself

**LAMBA Evaluation:** The final deliverable (a published assistant) is evaluated using a rubric through LAMBA. The AI proposes an evaluation; the instructor reviews and finalizes the grade. Participants experience LAMBA from the learner side.

### 4.3 The Dogfooding Loop

```
Participants ask questions in forum
        |
        v
Best questions become screencast answers
        |
        v
Screencast transcriptions are ingested into the course KB
        |
        v
The course AI assistant can now answer those questions
        |
        v
Participants experience a better assistant
        |
        v
They understand why knowledge bases matter for THEIR assistants
```

This loop is made explicit to participants. They see the course assistant improve in real time as new content is added, demonstrating the value of maintaining and growing a knowledge base.

---

## 5. Content Plan: The Video Series

Each video is **5-10 minutes**, focused, and ends with a concrete call to action.

### Week 1: Experience First, Build Second

The first week is designed to be **enjoyable and immediately rewarding**. Participants start as end users -- experiencing LAMB assistants the way their students will -- before switching to the creator side. When they do create, they use **single file RAG**, which lets them attach one document to an assistant with zero setup complexity. No knowledge base creation, no chunking configuration, no waiting. Upload a file, select it, and the assistant instantly knows your course content.

| # | Video Title | Key Content | Call to Action |
|---|------------|-------------|----------------|
| 1 | **Meet Your AI Tutor** | Start as a student: interact with 2-3 pre-built demo assistants (a history tutor, a math helper, a language coach). Feel the experience. Notice how each has different personality, scope, and knowledge. | Chat with each demo assistant. Post in the forum: which one impressed you most and why? What would you want for YOUR course? |
| 2 | **Why LAMB? Control, Privacy, and the Manifesto** | Now that you've felt it -- why does this exist? Privacy concerns with ChatGPT, manifesto principles, institutional control, the case for purpose-built educational AI vs. general-purpose tools. | Read the manifesto (or skim it). Post in the forum: what concerns do you have about AI in your courses? |
| 3 | **Your First Login and Your First Assistant** | Click the LTI Creator link in Moodle. Land in the Creator Interface. Create an assistant: name, description, choose a model, write a basic system prompt. Keep it simple. | Log into LAMB from Moodle. Create an assistant for your course with a simple system prompt (e.g., "You are a tutor for [your subject]. Be helpful and encouraging."). |
| 4 | **The Magic Trick: Attach a File and Watch** | Introduce single file RAG: select "single_file_rag" as the RAG processor, upload one file (your syllabus, a chapter summary, a set of key concepts -- just a .txt or .md file), select it, save. Now test: ask the assistant about your course content. It knows. | Upload one document from your course and attach it to your assistant. Ask it 5 questions that require knowledge from that file. Post in the forum: what was the "wow" moment? |
| 5 | **The Course Assistant & Eating Our Own Dogfood** | Demonstrate the course's own LAMB assistant. Show how it references specific videos and timestamps. Explain the dogfooding concept: this course runs on LAMB. Everything you're learning to build, you're also experiencing as a learner. | Try the course assistant. Ask it something about what you've learned this week. Compare its answers to the demo assistants from Video 1 -- what's different about an assistant with real content behind it? |

### Week 2: Deep Knowledge and Refinement

Now that participants have a working assistant with a single file, Week 2 introduces the full knowledge base system -- explaining why they might need more than one file, how semantic search works, and how to fine-tune their assistant's behavior.

| # | Video Title | Key Content | Call to Action |
|---|------------|-------------|----------------|
| 6 | **From One File to a Full Knowledge Base** | The limitation of single file RAG (whole file in context, one file only). Introduce Knowledge Bases: create a collection, upload multiple documents. Explain chunking and vector search -- the AI finds the relevant parts instead of reading everything. | Create a knowledge base. Upload at least 2-3 documents from your course. |
| 7 | **Beyond Files: URLs, Crawlers, and YouTube** | Ingest a web page, crawl a course website, import a YouTube lecture transcript. Show how diverse sources become searchable knowledge. | Add a URL or YouTube video to your KB. |
| 8 | **Connecting Your Knowledge Base (RAG)** | Switch your assistant from single file RAG to a full KB. Configure Top K. Test the difference -- now it searches for relevant chunks instead of dumping the whole file. Compare the results. | Connect your KB to your assistant. Ask the same questions from Week 1. Is it better? Post your comparison in the forum. |
| 9 | **Debug Mode: Seeing What the AI Sees** | Enable debug mode. Read the complete prompt: system prompt + retrieved context + user question. Understand what the AI actually receives. Inspect citations. | Enable debug mode. Take a screenshot of the full prompt. Post it in the forum with your observations. |
| 10 | **Prompt Engineering for Educators** | Refining system prompts: setting boundaries, tone, pedagogical strategies (Socratic method, scaffolding, "don't give the answer -- guide the student"). Before/after comparison. | Rewrite your system prompt. Compare the assistant's behavior before and after. Share your best prompt in the forum. |

### Week 3: Publishing, Assessment, and Beyond

| # | Video Title | Key Content | Call to Action |
|---|------------|-------------|----------------|
| 11 | **Publishing to Moodle** | The publish workflow, LTI credentials, adding as External Tool in Moodle, student view | Publish your assistant. Add it to a test Moodle course (or your real course). |
| 12 | **Creating Assessment Rubrics with Evaluaitor** | Manual rubric creation, AI-generated rubrics, criteria/levels/weights, sharing templates | Create a rubric for evaluating your assistant (or a student assignment). Try AI generation. |
| 13 | **AI-Assisted Evaluation with LAMBA** | The evaluation workflow, how the AI proposes (not decides), teacher review, dual-grade model | Experience LAMBA as a student by submitting your final deliverable. Then discuss in the forum: how would you use this? |
| 14 | **Sharing, Analytics, and Next Steps** | Assistant sharing with colleagues, chat analytics, the LAMB ecosystem, what's coming next | Share your assistant with a colleague. Review your analytics. Post your final reflections in the forum. |

### Bonus / Responsive Content

| # | Video Title | When |
|---|------------|------|
| B1-Bn | **Screencast answers to forum questions** | As needed, throughout the course |
| B? | **Advanced: Prompt Templates** | If participants ask about reusable prompts |
| B? | **Advanced: Organization Admin** | If institution admins are in the cohort |
| B? | **Advanced: Multiple Models Compared** | If participants want to compare GPT-4o vs. Mistral vs. local |

---

## 6. The Forum as Content Engine

### 6.1 Forum Culture

The forum is positioned not as "support" but as a **professional learning community**. The instructor sets the tone in Video 1 and the welcome announcement:

> *This forum is where the course really happens. Post anything: questions you can't figure out, features you wish existed, things that frustrated you, things that delighted you, ideas for how you'd use LAMB in your teaching. There are no dumb questions -- and your questions will literally make this course better, because we'll turn the best ones into new content.*

### 6.2 Encouraged Post Types

| Type | Description | Instructor Response |
|------|-------------|-------------------|
| **Questions** | "How do I...?", "Why does...?" | Text answer or screencast if visual |
| **Feature requests** | "It would be great if LAMB could..." | Acknowledge, discuss feasibility, potentially route to GitHub |
| **Clarifications** | "I didn't understand the part about..." | Short screencast addressing the confusion |
| **Wins** | "I got my assistant working and it..." | Celebrate, ask follow-up, share with the group |
| **Frustrations** | "I tried X and it didn't work because..." | Troubleshoot, possibly create a screencast, improve documentation |
| **Ideas** | "What if we used LAMB for...?" | Discuss, connect to other participants' ideas |

### 6.3 Screencast-to-KB Pipeline

When the instructor creates a screencast answer:

1. Record short screencast (2-5 min) addressing the forum question
2. Upload to video hosting (YouTube unlisted or institutional platform)
3. Generate/write a transcript
4. Post the screencast link as a forum reply
5. **Ingest the transcript into the course assistant's knowledge base**
6. The course assistant can now answer that question and point to the screencast

This pipeline is documented and visible to participants -- it demonstrates real-time KB maintenance.

---

## 7. AMA Sessions (Synchronous)

### 7.1 Format

2-3 live videoconference sessions (60-90 minutes each), scheduled at key moments:

| Session | Timing | Focus |
|---------|--------|-------|
| **AMA 1** | End of Week 1 | First impressions, clarifying concepts, troubleshooting first assistants |
| **AMA 2** | End of Week 2 | Knowledge bases, RAG, prompt engineering discussion |
| **AMA 3** | End of Week 3 | Publishing, evaluation, future plans, course wrap-up |

### 7.2 Structure

Each AMA session follows a loose structure:

1. **Warm-up (10 min)** -- Instructor addresses 2-3 curated forum questions (seeded in case participants are shy at first)
2. **Open Q&A (40-60 min)** -- Participants ask anything. Screen sharing encouraged for live troubleshooting.
3. **Show & Tell (10-20 min)** -- Volunteers show their assistants. Group feedback.

### 7.3 Seeded Questions

The instructor selects 2-3 interesting forum threads before each session as conversation starters. This ensures the session has momentum even if participants are initially quiet. As the course progresses and trust builds, seeding becomes less necessary.

### 7.4 Recording

AMA sessions are recorded and posted to the course. Transcripts are ingested into the course assistant's KB.

---

## 8. Assessment Strategy

### 8.1 Philosophy

Assessment in this course serves two purposes:
1. Ensure participants have achieved the core learning objectives
2. **Demonstrate LAMBA in action** -- participants experience AI-assisted evaluation from the learner perspective

### 8.2 Final Deliverable

Each participant submits a **published LAMB assistant** for their own teaching context. The submission includes:

- The assistant's name and a brief description of its purpose
- The system prompt used
- A description of the knowledge base contents (what was ingested and why)
- The Moodle course where it is published (or a plan for publication)
- A short reflection (300-500 words): What worked? What would you change? How might your students benefit?

### 8.3 Evaluation Rubric

The deliverable is evaluated using a rubric created in Evaluaitor and processed through LAMBA:

| Criterion | Weight | What We Look For |
|-----------|--------|------------------|
| **Assistant Design** | 25% | Clear purpose, well-written system prompt, appropriate model choice |
| **Knowledge Base Quality** | 25% | Relevant content ingested, appropriate sources, reasonable scope |
| **Testing & Iteration** | 20% | Evidence of testing, prompt refinement, debug mode usage |
| **Publication & Integration** | 15% | Assistant published and accessible via LTI in a Moodle course |
| **Reflection** | 15% | Thoughtful analysis of the experience, realistic plans for use |

### 8.4 The LAMBA Experience

The evaluation workflow:

1. Participant submits their deliverable through Moodle (LAMBA LTI activity)
2. The AI evaluates the submission against the rubric and proposes a score with written feedback
3. **The instructor reviews every AI proposal**, edits the feedback where needed, adjusts scores if the AI misjudged, and confirms the final grade
4. The participant receives the instructor-confirmed grade and feedback in Moodle

This is made transparent to participants. They are told:

> *The AI read your submission and proposed an evaluation. Your instructor then reviewed that proposal, edited it where needed, and confirmed the final grade. This is exactly how LAMBA works -- the AI assists, the teacher decides. You just experienced it from the student side.*

### 8.5 Forum Participation (Ungraded but Valued)

Forum participation is encouraged but not formally graded. The instructor highlights valuable contributions in announcements and AMA sessions. Participants who share prompts, help peers, or post thoughtful questions are acknowledged publicly.

---

## 9. Content Production Guidelines

### 9.1 Video Production

| Aspect | Guideline |
|--------|-----------|
| **Length** | 5-10 minutes maximum. If longer, split into two. |
| **Format** | Screencast with voiceover. Face cam optional but recommended for intro/outro. |
| **Structure** | Hook (what you'll learn) > Demo (show, don't tell) > Call to action (what to do now) |
| **Tone** | Conversational, encouraging, peer-to-peer. Not lecturing -- showing a colleague how to do something. |
| **Subtitles** | Always. Auto-generated is fine, corrected if possible. |
| **Transcript** | Always produced. Serves dual purpose: accessibility + course assistant KB. |

### 9.2 Screencast Answers

| Aspect | Guideline |
|--------|-----------|
| **Length** | 2-5 minutes. Address one question per screencast. |
| **Context** | Start by reading the forum question aloud. |
| **Format** | Screen recording showing the solution. No editing needed. |
| **Posting** | Reply in the forum thread with the video link. |
| **KB Ingestion** | Transcript added to course assistant's KB within 24 hours. |

### 9.3 Written Content

- The stakeholder summary document serves as the primary reference
- Each video module includes a short written summary (not a full transcript -- a 2-3 paragraph digest)
- FAQ entries are compiled from forum interactions

---

## 10. Timeline and Rhythm

### Weekly Rhythm

```
Monday:      New video released + announcement
Tuesday:     Forum activity, instructor responds to posts
Wednesday:   Second video released (if on 2-day cadence)
Thursday:    Forum activity, screencast answers if needed
Friday:      Third video or rest day + weekly summary announcement
Weekend:     Participants catch up, forum stays active
```

### Course Calendar (3-Week Model)

| Day | Content | Activity |
|-----|---------|----------|
| **D1** | Video 1: Meet Your AI Tutor | Chat with demo assistants, forum intro |
| **D2** | Video 2: Why LAMB? | Read manifesto, discuss AI concerns |
| **D3** | Video 3: First Login & First Assistant | Log in via LTI, create assistant |
| **D4** | Video 4: The Magic Trick (single file RAG) | Upload a file, instant "wow" |
| **D5** | Video 5: Course Assistant & Dogfooding | Try the course assistant |
| **D5-6** | **AMA Session 1** | First impressions, wow moments, Q&A |
| **D7** | Rest / catch-up | |
| **D8** | Video 6: From One File to a Full KB | Create KB, upload multiple docs |
| **D9** | Video 7: URLs, Crawlers & YouTube | Ingest web/video content |
| **D10** | Video 8: Connecting Your KB (RAG) | Switch from single file to full KB |
| **D11** | Video 9: Debug Mode | Inspect prompts and context |
| **D12** | Video 10: Prompt Engineering | Refine system prompts |
| **D12-13** | **AMA Session 2** | RAG comparison, prompt sharing |
| **D14** | Rest / catch-up | |
| **D15** | Video 11: Publishing | Publish to Moodle |
| **D16** | Video 12: Evaluaitor Rubrics | Create rubrics |
| **D17** | Video 13: LAMBA | Experience AI-assisted evaluation |
| **D18** | Video 14: Sharing & Analytics | Wrap-up features |
| **D19** | Final deliverable deadline | Submit via LAMBA |
| **D20-21** | **AMA Session 3** | Show & tell, reflections, wrap-up |

---

## 11. Success Metrics

### For Participants

| Metric | Target |
|--------|--------|
| Completed at least one assistant | 90%+ of participants |
| Published assistant to Moodle | 70%+ of participants |
| Created a knowledge base with real course content | 80%+ of participants |
| Posted at least once in the forum | 95%+ of participants |
| Submitted final deliverable | 80%+ of participants |

### For the Course

| Metric | Target |
|--------|--------|
| Participant satisfaction (post-course survey) | 4.0+ / 5.0 |
| Forum posts per participant (average) | 3+ |
| Screencast answers produced | 5-10 per cohort |
| Course assistant KB growth | Measurable increase from D1 to D21 |
| Participants who continue using LAMB after the course | Track at 3 months |

### For LAMB (Product Feedback)

| Metric | Outcome |
|--------|---------|
| Feature requests collected | Triaged and routed to GitHub issues |
| Bugs reported | Filed and prioritized |
| UX friction points identified | Documented for product improvement |
| Use cases discovered | Added to documentation / website |

---

## 12. Reusability and Scaling

### Cohort Model

This course is designed to be run in cohorts. Each cohort:
- Gets a fresh Moodle course instance (or section)
- Shares the same LAMB training organization
- Inherits the growing content backlog from previous cohorts
- Benefits from an ever-improving course assistant KB

### Content Backlog Growth

```
Cohort 1:  14 core videos + N screencast answers
Cohort 2:  14 core videos + N + M screencast answers (some from Cohort 1 reused)
Cohort 3:  14 core videos (possibly refined) + growing library of screencast answers
   ...
```

The course assistant becomes more capable with each cohort as its KB grows. This is itself a demonstration of LAMB's value proposition.

### Localization

- Core videos can be produced in multiple languages (Spanish, English, Catalan, Basque -- matching LAMB's interface languages)
- The course assistant can be configured per language
- Written materials already exist in multiple languages on the project website

---

## 13. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Low forum participation | Course feels empty, fewer screencasts | Seed the forum with questions from the instructor. Directly invite participants to respond to specific prompts in calls to action. |
| Participants fall behind on videos | Accumulation of unwatched content, disengagement | Keep videos short. Weekly summary announcements. AMA sessions as catch-up points. |
| LAMB instance issues (downtime, bugs) | Frustration, blocked participants | Have a known-good backup instance. Transparent communication about issues. Turn bugs into learning moments ("this is open source -- let's file it"). |
| Participants lack Moodle admin access for publishing | Cannot complete the publishing step | Provide a shared test Moodle course. Partner with institutional Moodle admins. Offer the publishing step as optional if access is not possible. |
| AI-assisted evaluation (LAMBA) feels impersonal | Negative reaction to AI proposing grades | Be extremely transparent about the process. Show the raw AI proposal vs. the instructor's final feedback. Emphasize the teacher-decides model. |
| AMA sessions poorly attended | Missed opportunity for community building | Record and share. Offer two time slots if possible. Keep them optional but valuable (exclusive Q&A, show & tell). |

---

## 14. Summary: The Course in One Page

**What:** A 3-week hybrid course teaching university educators to build AI learning assistants with LAMB.

**How:** Short daily videos with hands-on tasks, an active discussion forum, and live AMA sessions. The course itself runs on LAMB (dogfooding).

**The Loop:**
1. Watch a short video (5-10 min)
2. Do something concrete with LAMB (call to action)
3. Share your experience in the forum
4. Get answers (text or screencast) from the instructor
5. Those answers feed the course assistant's knowledge base
6. The course assistant gets smarter -- proving the value of what you're building

**Assessment:** Submit a published assistant. AI proposes an evaluation via LAMBA. The instructor reviews and confirms. Participants experience the full cycle from both sides.

**Philosophy:** The AI assists; the teacher decides. Always.

---

*This document defines the teaching strategy for the LAMB training course. The next step is to develop detailed video scripts and the Moodle course structure.*
