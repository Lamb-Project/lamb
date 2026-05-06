---
topic: publishing
covers: [publish, unpublish, lti, moodle, consumer-key, tool-url, unified-lti, instructor-dashboard, students]
answers:
  - "how do I publish an assistant"
  - "how do I connect to Moodle"
  - "what is LTI"
  - "how do students access my assistant"
  - "how do I unpublish"
  - "what is unified LTI"
  - "where do I find the consumer key"
---

## Publishing an Assistant

On the assistant Properties page, click **Publish**. This:
1. Registers the assistant as available to students
2. Generates LTI integration credentials
3. Creates a Tool URL for LMS integration

After publishing, the Properties page shows **LTI Publish Details**:
- **Assistant Name** — the published name
- **Model ID** — internal identifier
- **Tool URL** — URL to configure in your LMS
- **Consumer Key** — LTI OAuth key
- **Secret** — ask your LAMB administrator

## Connecting to Moodle

1. In LAMB: Publish the assistant, note Tool URL and Consumer Key
2. In Moodle: Course > Turn editing on > Add activity > External Tool
3. Configure:
   - Tool URL: paste from LAMB
   - Consumer Key: paste from LAMB
   - Shared Secret: get from your LAMB admin
4. Save

Students clicking the activity link in Moodle get redirected to chat with your assistant.

## Unified LTI (Recommended)

A single LTI tool for the entire LAMB instance. Benefits:
- One configuration in Moodle, multiple assistants per activity
- Instructors choose which published assistants to include
- Instructor Dashboard with usage stats, student tracking, anonymized transcripts
- Students see all selected assistants in one view

First-time setup: click LTI link as instructor > select assistants > save. Students see a "not set up yet" page until an instructor configures it.

## Unpublishing

Click **Unpublish** to remove student access. Existing chat history is preserved. Students can no longer start new conversations.
