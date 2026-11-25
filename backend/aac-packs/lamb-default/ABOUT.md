---
summary: The next knowledge pack, being written. Guides are advice only: LEGATUS explores the tools your LAMB offers when no guide fits a request, says what it could not establish, and tells enrolled Moodle courses from active ones.
---

## What this version is for

This is the pack being prepared to follow the one that ships with LAMB 0.9. It is the first written entirely as guidance: it tells LEGATUS how to do a task well and never decides what LEGATUS may do. What a person may do in LAMB is decided by LAMB itself, from their role, their ownership of each resource and the approvals they give.

It changes without notice while it is a beta. Use it in an organization where you try things out.

## What changed

Compared with pack 1.13.6:

- **Working without a guide.** LEGATUS is told what to do when a request was not anticipated: read the list of tools, plan the reads that answer the question, propose any change for your approval, and say that it worked without a guide.
- **Real limits are named.** When something cannot be done, LEGATUS says which it is: a tool LAMB does not have, a permission you lack, an integration that is not connected, or information the source does not hold. A missing guide is never the reason.
- **Enrolled is not active.** Asked for your active Moodle courses, LEGATUS says which criterion it applies and what evidence supports it, and says so when Moodle gives no dates or activity to decide with.
- **Plans as fields.** To prepare several steps for one approval, LEGATUS fills in a form (operation, values, options) and LAMB writes the commands. It no longer has to quote text inside text, which is what made it fail on a plan with a long instruction. When a plan is refused it corrects the named field and keeps your wording.
- **Nothing is built on a partial import.** If some course documents did not finish ingesting, the assistant that depends on them is not created, and LEGATUS says which documents are missing.
- **No roles in the pack.** The pack no longer assigns tools to roles. That list was empty in 1.13.6; the possibility is now removed.

## Guides in this version

| Guide | What it helps with | For | Needs |
|---|---|---|---|
| `about-lamb` | Help educators choose a grounded learning design using documented methodology and installed capabilities | Every creator |  |
| `chat-with-assistant` | Run real assistant conversations, preserve chat history and verify behavior | Every creator |  |
| `configure-agent` | Explain current model availability and who can change the agent configuration | Every creator |  |
| `create-assistant` | Guide through creating a new assistant | Every creator |  |
| `explain-assistant` | Show how the assistant works internally | Every creator |  |
| `improve-assistant` | Review and suggest improvements | Every creator |  |
| `inspect-activity` | Investigate teaching activity, learning difficulties and assistant performance; propose dimensions or a full audit and save dated evidence-based reports | Every creator |  |
| `manage-knowledge-base` | Create and inspect knowledge bases, check files and ingestion status, and verify retrieval | Every creator |  |
| `manage-learning-scenarios` | Create, edit, duplicate and remove personal learning scenarios; choose a default or inspect conversation context | Every creator |  |
| `manage-rubric` | Create, explain and edit rubrics and bind them to assistants | Every creator |  |
| `manage-templates` | Create, inspect, edit, duplicate, share and export prompt templates | Every creator |  |
| `moodle-assessment-draft` | Review a submission and draft feedback, a proposed grade and an evidence-based rationale | Every creator | Moodle connected |
| `moodle-course-documents` | Read course files, Pages and Books without importing them, or import them into owned grounding; review size, provenance and replacements | Every creator | Moodle connected |
| `moodle-forums` | Check forum news across courses, inspect evidence, read a thread and draft or post a reply | Every creator | Moodle connected |
| `moodle-triage` | Identify unresolved forum questions, submitted work, deadlines and access signals | Every creator | Moodle connected |
| `publish-assistant` | Publish or unpublish an owned assistant in LAMB, verify status, then guide external LMS setup | Every creator |  |
| `test-and-evaluate` | Generate test cases, run them, evaluate results, and suggest improvements | Every creator |  |
| `test-lti-tools` | Help an admin configure and test LAMB as an LTI tool via the LTI 1.1 Test Platform simulator | System administrators |  |

## Languages

LEGATUS answers in English, Spanish, Catalan or Basque, with a vocabulary checked against the words of the LAMB interface in each language.

## Needs

LAMB 0.9.0 or later, the first version in which a guide is advice. The Moodle guides appear only to a creator who has connected Moodle.
