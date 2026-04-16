# LAMB LTI Integration Notes

This note summarizes how LTI currently works between Moodle and LAMB, based on the current backend routers and the architecture docs.

## High-level flow

At a high level, the integration works like this:

1. Moodle launches an external tool using LTI 1.1 and sends a signed POST request to LAMB.
2. LAMB validates the OAuth 1.0 signature and extracts the Moodle user and launch context.
3. LAMB provisions or reuses the corresponding user record.
4. LAMB creates or reuses the session needed for the destination application.
5. LAMB redirects the browser to the final UI.

In practice, the main modern Moodle path is:

- `/lamb/v1/lti/launch` for the unified activity-based LTI flow.

There are also two more specialized LTI paths:

- `/lamb/v1/lti_users/lti` for the simpler student or end-user launch into chat.
- `/lamb/v1/lti_creator/launch` for educator launch into the creator interface.

So if Moodle is configured for the current activity workflow, `/lamb/v1/lti/launch` is the endpoint that matters most.

## Unified LTI flow

The unified flow is implemented in `backend/lamb/lti_router.py`.

Moodle sends a POST request to `/lamb/v1/lti/launch` with the usual LTI launch parameters, especially:

- `oauth_consumer_key`
- `oauth_signature`
- `resource_link_id`
- `user_id`
- `roles`
- optionally `lis_person_contact_email_primary`
- optionally `lis_person_name_full`
- optionally `ext_user_username`
- optionally `context_id`
- optionally `context_title`

LAMB then does the following:

1. Validates the configured consumer key.
2. Reconstructs the request URL and validates the OAuth signature.
3. Extracts the Moodle launch context, especially `resource_link_id`, roles, user identity, and course context.
4. Looks up whether that `resource_link_id` is already configured as a LAMB LTI activity.

From there the flow branches.

### If the activity already exists

- If the user is an instructor, LAMB sends them to the LTI dashboard for that activity.
- If the user is a student, LAMB checks whether consent is required.
- If consent is required, the user is sent to a consent page first.
- If consent is not required, LAMB launches the user directly into Open WebUI chat.

The student launch eventually goes through the activity manager, which provisions or reuses the user, ensures the user belongs to the activity group, gets an OWI token, and redirects into chat.

### If the activity does not exist yet

- If the user is not an instructor, LAMB shows a waiting page.
- If the user is an instructor, LAMB tries to identify which LAMB Creator account matches that LMS identity.
- If the instructor is identified, LAMB redirects them to an activity setup page.
- On that setup page, the instructor chooses the organization and assistants that will be bound to that Moodle activity.

After configuration, that Moodle `resource_link_id` becomes a persisted LTI activity in LAMB, and future launches use the configured path.

### What makes the unified route special

This route is different from the simpler student and creator routes because it is activity-based.

- The main key is `resource_link_id`, not just a consumer key.
- One global LTI tool can serve many Moodle activities.
- Instructors can configure which assistants belong to each activity on first launch.
- The route also includes instructor-only dashboard and analytics pages for a configured activity.

In other words, `/lamb/v1/lti/launch` is the modern multi-step Moodle integration flow.

## Student LTI flow

The student flow is implemented in `backend/lamb/lti_users_router.py`.

Moodle sends a POST request to `/lamb/v1/lti_users/lti` with standard LTI parameters such as:

- `oauth_consumer_key`
- `oauth_signature`
- `oauth_timestamp`
- `oauth_nonce`
- `user_id`
- optionally `ext_user_username`

LAMB then does the following:

1. Reads the submitted form data.
2. Loads the shared secret from `LTI_SECRET`.
3. Reconstructs the launch URL from the request headers and path.
4. Recomputes the OAuth signature using HMAC-SHA1.
5. Rejects the launch if the computed signature does not match the received one.

If the signature is valid, LAMB identifies the user and assistant context:

- It takes `ext_user_username` if present, otherwise falls back to `user_id`.
- It uses `oauth_consumer_key` as the assistant publishing key for lookup.
- It generates a synthetic email in the form `{username}-{oauth_consumer_key}@lamb-project.org`.

That synthetic email is important because LAMB avoids relying on the LMS-provided email address directly.

After that, LAMB checks whether the LTI user already exists in its own database:

- If the user already exists, LAMB gets an Open WebUI auth token for that user.
- If the user does not exist, LAMB looks up the published assistant associated with the consumer key.

For a first-time launch, LAMB then provisions the user:

1. Creates an `LTIUser` record in the LAMB database.
2. Creates the matching Open WebUI user if needed.
3. Adds the user to the Open WebUI group associated with the published assistant.
4. Requests an Open WebUI auth token.

Finally, LAMB redirects the browser into Open WebUI using a completion URL of the form:

`{OWI_PUBLIC_BASE_URL}/api/v1/auths/complete?token=...`

That is what gives the student a seamless auto-login into the assistant chat UI.

This route is simpler than the unified activity flow. It is still useful context, but it is not the main activity-based Moodle flow when the platform is configured around `/lamb/v1/lti/launch`.

## Creator LTI flow

The creator flow is implemented in `backend/lamb/lti_creator_router.py`.

This flow is for educators who should land in the LAMB creator interface rather than in Open WebUI chat.

Moodle sends a POST request to `/lamb/v1/lti_creator/launch`.

LAMB then does the following:

1. Reads the submitted form data.
2. Extracts `oauth_consumer_key`.
3. Resolves the organization associated with that key.
4. Rejects the request if the organization does not exist or is the system organization.
5. Reads the org-specific LTI creator secret from the organization config.
6. Rebuilds the launch URL and validates the OAuth signature.

If the request is valid, LAMB identifies the creator user:

- `user_id` is the stable LMS identity.
- `lis_person_name_full` or `ext_user_username` is used as the display name fallback.
- LAMB generates a synthetic creator email in the form `lti_creator_{org_slug}_{user_id}@lamb-lti.local`.

LAMB then provisions or reuses a creator user in its own database:

1. Looks up the creator by organization id and LTI user id.
2. Creates the creator if it does not exist yet.
3. Checks that the creator account is enabled.
4. Generates a LAMB JWT for the creator interface.

Finally, LAMB redirects the browser to the creator UI:

`{LAMB_PUBLIC_BASE_URL}/assistants?token=...`

The frontend can then store that token and use it for Creator Interface API calls.

This route is focused on authenticating educators into the Creator Interface itself. It is separate from the unified activity workflow.

## Main difference between the flows

The core difference is the destination and the unit of configuration.

- Unified LTI is activity-based. It binds a Moodle `resource_link_id` to one or more assistants and can route instructors to setup or dashboard pages.
- Student LTI is a simpler assistant-chat launch flow.
- Creator LTI is an educator login flow into the LAMB creator UI.

- Student LTI creates or reuses an end-user style account, gets an Open WebUI token, and redirects to chat.
- Creator LTI creates or reuses a creator account, gets a LAMB JWT, and redirects to the LAMB assistants UI.

There is also a configuration difference:

- Unified LTI uses a global consumer key and secret for the whole LAMB instance.
- Student LTI uses a shared LTI secret from environment configuration.
- Creator LTI uses an organization-specific consumer key and secret.

## Practical Moodle to LAMB picture

From Moodle's point of view, the integration is straightforward:

1. Moodle is configured with the launch URL and consumer credentials.
2. A teacher or student clicks the external tool link in Moodle.
3. Moodle sends the signed launch request to LAMB.
4. LAMB validates the request and resolves the right path for that activity and user role.
5. LAMB redirects the browser to the right destination without asking the user to log in again.

So the essential role of LTI in LAMB is not just authentication. It is also automatic user provisioning, context mapping, and redirection into the correct application surface.

## Multi-worker fix for unified LTI

The unified route at `/lamb/v1/lti/launch` is a multi-step flow.

After the initial LTI POST, LAMB may redirect the browser to internal follow-up pages such as:

- `/lamb/v1/lti/setup`
- `/lamb/v1/lti/consent`
- `/lamb/v1/lti/dashboard`

Originally, the router stored temporary setup, consent, and dashboard tokens in process memory inside `backend/lamb/lti_router.py`.

That worked with a single worker, but it broke intermittently with multiple Uvicorn workers:

1. One worker handled the initial launch request.
2. That worker created the temporary token in its own memory.
3. The browser followed the redirect.
4. A different worker received the next request.
5. That second worker could not see the in-memory token.
6. LAMB returned a "Session expired" page.

To make the unified LTI flow work correctly with multiple workers, the temporary token mechanism was changed.

Instead of storing those tokens in memory, LAMB now creates short-lived signed stateless tokens using the regular LAMB JWT utility in `backend/lamb/auth.py`.

The lifetimes remain the same as before:

- setup tokens: 10 minutes,
- consent tokens: 10 minutes,
- dashboard tokens: 30 minutes.

Those values come from SETUP_TOKEN_TTL = 600, CONSENT_TOKEN_TTL = 600, and DASHBOARD_TOKEN_TTL = 1800 in `backend/lamb/lti_router.py`

That means:

- any worker can validate the token,
- redirects can hop across workers safely,
- the unified LTI setup, consent, and dashboard flow is no longer tied to one Python process.

### Subtle consequence

There is one important tradeoff.

Before the change, a temporary token could be consumed server-side by deleting it from the in-memory store.

After the change, the token is stateless, so there is no shared server-side record to delete. In practice, this means:

- the token is no longer truly one-time-use,
- validity is controlled by signature verification and expiration time,
- ordinary token use does not renew or extend its lifetime,
- `_consume_token()` in the unified router is effectively a no-op.

The only time a lifetime is refreshed is when LAMB explicitly issues a brand new token, for example when the account-linking flow reissues a setup token after updating the available creator identity data.

So the fix improves correctness under multiple workers, but it changes token behavior from server-consumed to expiry-based.