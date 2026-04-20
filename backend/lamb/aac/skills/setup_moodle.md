---
id: setup-moodle
name: Set up Moodle integration
description: Conversationally connect LAMB to the user's Moodle — URL, token, verification.
required_context: []
optional_context: [language]
startup_actions:
  - "lamb integration list"
---

# Skill: Set up Moodle integration

Help the user connect their Moodle server to LAMB so the AAC agent can use `moodle ...` commands on their behalf. Stay brief. One step at a time.

## What is being set up

The user's Moodle credentials will be stored **encrypted** in LAMB. They're used only when the agent runs `moodle ...` commands in this user's sessions — they are never logged, never returned through any API, and never shared with other users.

Three pieces are needed:
1. **URL** — the Moodle base URL, e.g. `https://moodle.example.edu`. No trailing slash.
2. **Token** — a Moodle Web Services token for the *moodle_mobile_app* service.
3. (Optional) **Service shortname** — defaults to `moodle_mobile_app`; only override if the admin configured a custom service.

## On startup

`integration list` will have been run. Look at the result:

- **If the user already has a `moodle` entry with `healthy: true`** → say so plainly (e.g. "You already have Moodle set up and it verified successfully on {last_verified_at}."). Ask whether they want to replace it, test it again, or leave it. Do not run anything destructive without confirmation.
- **If there's a `moodle` entry but `healthy` is false or null** → tell them the credentials exist but haven't verified. Offer to re-verify (`integration test moodle`) or replace them.
- **Otherwise** → start fresh. Walk them through the 3 steps below.

## Walkthrough (fresh setup)

**Step 1 — URL.** Ask: "What's your Moodle site URL?" Accept anything that looks like `https://...`. Strip trailing `/`. If it looks wrong (no `http`, typo), say so and ask again.

**Step 2 — Token.** Ask the user to get a Web Services token from their Moodle. Give them this exact guidance, tailored to their role:

> In Moodle, go to **User menu → Preferences → User account → Security keys**.
> Copy the token for the service **"Moodle mobile web service"** (or whatever the admin named the `moodle_mobile_app` service).
> If it's not listed, the admin needs to enable web services and create the token for your account. Tell them to visit *Site administration → Plugins → Web services → Manage tokens*.

Warn them: **do not share this token in any chat other than this one**. Paste it here and it will be encrypted.

**Step 3 — Service (optional).** Only ask about this if the default (`moodle_mobile_app`) fails verification in step 4. Most Moodle installs use the default.

**Step 4 — Save and verify.** Run these two commands in order:

1. `integration save moodle --url <URL> --token <TOKEN>` (add `--service <name>` only if needed). This requires the user's approval — the authorization policy is `ask` because credentials are sensitive. Present the URL but NEVER echo the token in plain text when confirming; say "token (N chars)" instead.
2. `integration test moodle` — this calls `core_webservice_get_site_info` against their Moodle. Expect a reply like `{"healthy": true, "site": "...", "username": "...", "release": "..."}`.

If the test fails:
- **401 / token error** → the token is wrong or expired. Ask them to regenerate it. Do not keep retrying — that can lock the account.
- **connection error** → the URL might be unreachable from LAMB's container, or the Moodle site is down. Ask them to verify the URL from a browser first.
- **"missing capability" / function disabled** → the web service is enabled but `core_webservice_get_site_info` isn't exposed to this user's role. Tell them to ask their admin.

## After success

- Summarise: "Moodle connected: {site} as {username}. You can now ask me things like *list my courses* or *who's enrolled in course X*, and I'll use `moodle ...` on your behalf."
- Rename the session with `lamb session rename "Setup: Moodle ({site})"` so it's findable later.
- Offer one concrete next step, e.g. `moodle course list` or suggest loading a skill that uses Moodle.

## What NOT to do

- Do **not** echo the token back to the user. Once it's saved, it's encrypted — if they ask "what token did I save?", say you can't recall it, they'd need to regenerate one from Moodle.
- Do **not** try to infer credentials from conversation. Only use what the user explicitly provides.
- Do **not** run `moodle ...` commands until `integration test moodle` has returned healthy.
- Do **not** attempt to "auto-detect" a token from login cookies or similar — there is no such path. Web Services tokens are the only supported auth.

## Troubleshooting quick reference

| Symptom | Likely cause | Action |
|---|---|---|
| `integration test` returns `exception` | token wrong / function not permitted | ask user to regenerate token, or ask admin to expose `core_webservice_get_site_info` |
| `integration test` raises connection error | URL unreachable from LAMB container | verify URL in a browser; check LAN/firewall |
| `moodle <cmd>` returns `No token for profile 'default'` | env-var short-circuit didn't fire — integration not saved | run `integration list` to confirm, `integration save` again |
