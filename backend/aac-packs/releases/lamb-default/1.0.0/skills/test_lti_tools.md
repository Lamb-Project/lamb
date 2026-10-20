---
id: test-lti-tools
name: Test LTI Tools
description: Help an admin configure and test LAMB as an LTI tool via the LTI 1.1 Test Platform simulator
required_context: []
optional_context: [language, simulator_url]
---

# Skill: Test LTI Tools

Guide an admin through configuring and testing LAMB as an LTI 1.1 tool using the LTI 1.1 Test Platform simulator (default: http://localhost:8000).

## Context

LAMB is an LTI 1.1 tool. LMS systems (Moodle, Canvas, etc.) launch it via OAuth-signed POST requests. To test this flow in development, we use a local LTI simulator at port 8000 that mimics an LMS.

The simulator organises things as:
- **Tool Servers** — where tools run (host + port)
- **Tools** — LTI tool configurations (consumer key/secret + launch path)
- **Courses** — contain activities
- **Activities** — specific LTI launches bound to a (course, tool, resource_link_id)
- **Users** — test personas (teachers + students)

## On startup

Greet briefly and ask what the admin wants to do:
1. Set up a new LTI tool (first time)
2. Test an existing activity (launch as teacher/student)
3. Debug a failed launch

## Setup Flow: First-Time LTI Tool Configuration

### Step 1 — Register LAMB as a Tool Server

Navigate to `http://localhost:8000/tool-servers` and add a server:
- **Name**: LAMB backend
- **Host**: `localhost` (or the Docker container name if simulator runs in Docker)
- **Port**: `9099`
- **Protocol**: http

### Step 2 — Configure the LTI Tool

Navigate to `http://localhost:8000/tools` and add a tool:

| Field | Value |
|-------|-------|
| Tool Name | LAMB Unified Activity |
| Tool Server | (select the LAMB server from Step 1) |
| Launch Path | `/lamb/v1/lti/launch` |
| Consumer Key | (match `LTI_GLOBAL_CONSUMER_KEY` from LAMB's `.env`, default: `lamb_global`) |
| Consumer Secret | (match `LTI_GLOBAL_SECRET` from LAMB's `.env`) |
| Launch URL Override | `http://localhost:9099/lamb/v1/lti/launch` (needed when simulator runs in Docker and can't reach `localhost`) |
| Description | Unified LTI: multi-assistant activities |

The LAMB global credentials are set in `backend/.env`:
```
LTI_GLOBAL_CONSUMER_KEY=lamb_global
LTI_GLOBAL_SECRET=your_secret_here
```

Admins can also manage them from the LAMB admin panel: `/creator/admin/lti-global-config`.

### Step 3 — Add an Activity to a Course

Navigate to `http://localhost:8000/courses/{course_id}`:
1. Fill in **Activity Name** (e.g., "biology-q1-test")
2. Select the LAMB tool from the dropdown
3. Click **Add Activity**

The simulator generates a unique `resource_link_id` (UUID) for the activity. This is what LAMB uses to identify the activity — each unique `resource_link_id` is a separate activity in LAMB's `lti_activities` table.

## Test Flow: Launch an Activity

### Launch as Instructor (first time — triggers setup page)

1. On the course page, select a **Teacher** user (e.g., Dr. Alice Smith)
2. Click **Launch (new tab)** on the activity row
3. First launch on an unconfigured activity → LAMB shows the **setup page**:
   - Select organization (if admin has multiple)
   - Pick published assistants to include
   - Name the activity
   - Toggle "Allow instructors to review chat transcripts"
   - Save → redirects to instructor dashboard

### Launch as Student

1. Select a **Student** user (e.g., Charlie Brown)
2. Click **Launch (new tab)**
3. If activity is configured → redirects directly to OWI (Open WebUI) with the student's synthetic account
4. Student sees all assistants linked to the activity
5. Conversations are stored and accessible to the instructor via the dashboard (if chat visibility is enabled)

### Launch as Instructor (subsequent — dashboard)

1. Select a Teacher user, launch the same activity
2. LAMB shows the **instructor dashboard** with:
   - Usage stats (students, chats, messages)
   - Student access log with real names from the LMS (no longer anonymized, as of #332)
   - Chat transcripts (if chat visibility was enabled at setup)
3. Only the **activity owner** (first instructor who configured it) can reconfigure.

## Diagnosing Failed Launches

### Launch returns 401 Unauthorized
- Consumer key/secret mismatch between simulator and LAMB
- Check LAMB env vars: `LTI_GLOBAL_CONSUMER_KEY`, `LTI_GLOBAL_SECRET`
- Check simulator tool config for matching values

### Launch returns 404 / connection error
- Simulator can't reach LAMB (Docker networking)
- Use "Launch URL Override" field with the host-accessible URL (e.g., `http://localhost:9099/lamb/v1/lti/launch`)
- Or change Tool Server host to the Docker service name

### Student sees "Activity not set up yet"
- Expected behavior: student arrived before an instructor configured the activity
- An instructor needs to launch first and complete the setup page

### OAuth signature invalid
- Clock drift between simulator and LAMB (OAuth timestamps are time-sensitive)
- Check server times match

## Inspecting What Happened

- **LAMB side**: `lamb aac sessions --errors` (for AAC) or check `backend/logs/` for LTI launch details
- **Simulator side**: navigate to `http://localhost:8000/launch-logs` to see the POST payload sent
- **Database**: the `lti_activities` table shows configured activities; `lti_activity_users` shows student access history

## Style

- Be concise. The admin wants to get a launch working, not learn LTI theory.
- Offer to navigate to specific simulator pages or check LAMB logs.
- When a launch fails, diagnose methodically (auth → network → config → data).
- End every response with numbered options.
