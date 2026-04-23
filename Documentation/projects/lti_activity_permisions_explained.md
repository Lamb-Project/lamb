# LTI Activity Permissions Explained

**Audience:** administrators, support staff, and non-developers  
**Scope:** how permissions work when LAMB is used through an LMS LTI activity

---

## What This Document Explains

When a course in Moodle launches a LAMB LTI activity, several different permission systems work together:

- LMS roles such as teacher or student
- LAMB Creator permissions for building and sharing assistants
- Activity-level permissions for one specific LTI activity
- Open WebUI access rules for actually chatting with assistants

This document explains who can do what, and why.

---

## The Short Version

- A **teacher** can open the activity dashboard.
- The **first teacher who configures the activity** chooses which assistants are available in that activity.
- Only the **activity owner** can later change that assistant selection.
- Other teachers can use the activity and open the dashboard, but they do not automatically get permission to reconfigure it.
- Students can use only the assistants selected for that specific activity.
- Access inside chat is controlled through **one activity group** in Open WebUI that is connected to all assistants selected for that activity.

---

## The Main Idea

An LTI activity is treated as its own isolated space.

That means:

- one Moodle activity instance
- one LAMB activity record
- one Open WebUI group for that activity
- many users may enter it
- many assistants may be available inside it

So permissions are **per activity**, not global.

If the same course has two different LTI activities, they are treated separately:

- they can expose different assistants
- they can have different privacy settings
- the same Moodle user is treated as a separate activity user in each one

---

## Who Can Do What

## 1. First teacher configuring the activity

When an activity is launched for the first time, it has not been configured yet.

The first teacher who is recognized as a valid LAMB Creator user can:

- choose the organization, if more than one applies
- see assistants they own or assistants shared with them
- choose which assistants will be available in the activity
- choose whether anonymized chat transcript visibility is enabled

After saving:

- the activity becomes configured
- that teacher becomes the **owner** of the activity
- the selected assistants become the assistants for that activity only

Important:

- This does **not** change permissions for the whole course.
- This does **not** make all assistants globally available.
- It only defines what is available inside that one LTI activity.

---

## 2. Other teachers entering later

Other teachers who launch the same configured activity can:

- open the dashboard
- view activity statistics
- review the student access log
- review anonymized chat transcripts if transcript visibility is enabled
- open chat as a participant

But they do **not** automatically get permission to:

- change the assistant list
- change privacy/chat visibility settings

Those management actions are reserved for the **activity owner**.

In plain language:

- many teachers may use an activity
- only the owner may manage its configuration

---

## 3. Students

Students cannot configure the activity.

Students can:

- launch the configured activity
- accept the consent notice when required
- enter chat
- use only the assistants selected for that activity

If anonymized transcript visibility is enabled:

- students are shown a consent step before entering chat

If transcript visibility is not enabled:

- students go directly into chat without that consent step

---

## How Assistant Access Actually Works

This is the most important part for administrators.

LAMB does **not** create one Open WebUI group per assistant.

Instead, it creates:

- **one Open WebUI group per LTI activity**

Then LAMB gives that one activity group access to:

- all assistants selected for that activity

So the structure is:

1. Activity is configured
2. LAMB creates one activity group in Open WebUI
3. Every selected assistant is linked to that activity group
4. When a user enters chat, that user is added to the activity group
5. Open WebUI shows the assistants available to that group

This means:

- one activity can expose several assistants
- users do not need a separate group for each assistant
- assistant availability is controlled centrally by the activity group

---

## Why This Matters

This design makes administration simpler:

- one place controls access for the whole activity
- reconfiguring the activity means changing which assistants are linked to the group
- users keep activity-specific access instead of receiving broad permanent permissions

It also improves separation:

- a user in Activity A does not automatically get access to assistants from Activity B
- assistants can be reused across activities without merging permissions between them

---

## What Happens When Someone Clicks "Open Chat"

There are two different kinds of access involved:

## Dashboard access

The LAMB dashboard uses a LAMB session token.

This allows the user to:

- open the dashboard
- view stats
- manage the activity if they are the owner

## Chat access

Open WebUI uses its own authentication.

When the user clicks `Open Chat`:

- LAMB creates or retrieves that activity-specific chat user
- LAMB adds that user to the activity's Open WebUI group
- Open WebUI issues its own token
- the user is redirected into chat

So:

- dashboard access and chat access are related
- but they are not the same token and not the same permission system

---

## Activity Owner vs. Regular Teacher

The **activity owner** is the teacher whose Creator identity was used when the activity was first configured.

The owner can:

- manage assistant selection
- change transcript visibility settings
- open the same dashboard as everyone else

A regular teacher can:

- use the dashboard
- open chat
- review activity data allowed by the activity settings

But a regular teacher cannot:

- reconfigure the activity

This is intentional, so one teacher does not accidentally change another teacher's configured activity.

---

## Privacy and Transcript Visibility

An activity may optionally allow teachers to review anonymized transcripts.

If enabled:

- students are warned before entering chat
- consent is required
- transcript review is anonymized

If disabled:

- there is no transcript review for teachers
- students are not asked for that transcript-related consent step

Important:

- enabling transcript visibility does **not** reveal student names
- transcript review is designed to remain anonymized

---

## Common Admin Questions

## Does every teacher need to be a Creator user?

No.

Only the teacher who configures the activity, or a teacher who needs owner-level management rights, needs the relevant Creator identity.

Regular teachers can still use the configured activity as instructors.

## Does every activity get its own assistant copies?

No.

The assistants remain the same assistants. What changes is which activity group is allowed to use them.

## If one activity has three assistants and another has two, do they interfere?

No.

Each activity has its own Open WebUI group and its own selected assistant list.

## If a student uses the same course in two different activities, is that the same chat identity?

No.

The user is activity-specific. Each activity is isolated.

## Can another teacher see the dashboard without being able to reconfigure it?

Yes.

That is the normal expected behavior.

---

## Recommended Admin Mental Model

Think of an LTI activity as:

- a private room inside the course
- with its own selected assistants
- its own privacy setting
- its own participant list
- and its own Open WebUI access group

Then think of the owner as:

- the teacher allowed to arrange that room

And all other teachers as:

- teachers allowed to enter and use the room
- but not rearrange it

---

## Summary

The permission model for LAMB LTI activities is based on **activity isolation**.

- The first valid teacher configures the activity.
- That teacher becomes the owner.
- Other teachers can use the activity but not reconfigure it.
- Students can only access the assistants selected for that activity.
- Open WebUI access is controlled through **one group per activity**, linked to all assistants selected for that activity.

This keeps assistant access organized, limited to the correct activity, and easier to manage for administrators.
