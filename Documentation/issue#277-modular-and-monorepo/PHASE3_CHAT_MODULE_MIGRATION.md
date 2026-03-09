# Phase 3: LTI Chat Module Migration to SvelteKit SPA

> **Status**: ✅ Completed
> **Date**: 2026-03-08
> **Issue**: #277 — Architecture: Activity Module System

---

## 1. Executive Summary & Objective

To complete Phase 3, we have successfully decoupled the Chat Learning Tools Interoperability (LTI) module from the traditional Jinja2 template rendering system in the FastAPI backend. 

The entire application flow is now served by a new modern SvelteKit Single Page Application (SPA). This new SPA (`module-chat`) lives inside our frontend monorepo (`frontend/packages/module-chat`), sharing the `@lamb/ui` library for UI consistency, authentication, and internationalization. The FastAPI backend has been converted to serve pure JSON data APIs for these specific routes.

---

## 2. Architecture Plan (Old vs. New Flow)

**Old Flow (Jinja2):**
1. Moodle sends an LTI Launch to Backend `/lamb/v1/lti/launch`.
2. Backend generates a JWT token and renders a full HTML page using Jinja2 (e.g., `templates/lti_dashboard.html`).
3. JavaScript snippets inside the HTML make `fetch()` calls back to the server to load dynamic parts (like chat logs).

**New Flow (SvelteKit SPA):**
1. Moodle sends an LTI Launch.
2. Backend generates a JWT token and returns an HTTP 303 Redirect to `/m/chat/dashboard?token=...`.
3. The browser hits the Catch-All route in FastAPI, which transparently serves SvelteKit's compiled `index.html` for the `/m/chat/` path.
4. SvelteKit boots up, reads the `?token` from the URL, and executes a `fetch()` to `/lamb/v1/lti/dashboard/info` and other JSON APIs to get the initial data.
5. SvelteKit renders the reactive UI using `@lamb/ui` components.

---

## 3. Execution Log (Steps Completed)

### 3.1 — SvelteKit Scaffolding (`module-chat`)
- **App Creation:** Created the initial SvelteKit application structure in `frontend/packages/module-chat/`.
- **Base Path Configuration:** Modified `svelte.config.js` to use `paths.base = '/m/chat'`, ensuring the app handles routing correctly when mounted under that URL.
- **Workspace Dependencies:** Added `@lamb/ui` to `package.json` to reuse Nav, Footer, Modals, and Spinner components. Ported Tailwind CSS configuration.

### 3.2 — SvelteKit Routing & Interfaces Refactoring
- **Setup Route (`m/chat/setup`):** Translated the legacy `lti_activity_setup.html`. It now fetches organization/assistant data via `GET` in JSON format. Form submissions use a `POST` fetch with JSON payload instead of native HTML submission.
- **Consent Route (`m/chat/consent`):** Migrated `lti_consent.html`. It displays activity information and collects student consent via an API request.
- **Dashboard Route (`m/chat/dashboard`):** Translated `lti_dashboard.html`. Reactively loads statistics, student logs, and collapsible chat transcripts via individual JSON endpoints (`/stats`, `/students`, `/chats`), implementing asynchronous spinners for a better UX.

### 3.3 — Backend FastAPI Adaptation (`lamb/lti_router.py`)
- **LTI Launch Redirects:** Functions previously returning `templates.TemplateResponse()` now return `RedirectResponse(url='/m/chat/...')` with the necessary JWT tokens embedded as URL parameters.
- **JSON APIs:** Changed original routes (`GET /setup`, `GET /consent`, `GET /dashboard`) to (`GET /setup/info`, `GET /consent/info`, `GET /dashboard/info`), explicitly designed to return JSON.
- **JSON Payload Handling:** Modified `POST` methods (`/configure`, `/consent`) to parse request bodies as `await request.json()` instead of `request.form()`.

### 3.4 — Catch-All Routing & Monorepo Builds
- **Docker Compose:** Updated `docker-compose-example.yaml` and `docker-compose-workers.yaml` to build both packages concurrently using `pnpm --filter creator-app --filter module-chat build`.
- **FastAPI Catch-All:** Modified the `main.py` Catch-All routing rule to transparently serve `module_chat_assets` (`/m/chat/app`) and return the correct `index.html` when `/m/chat` is requested, isolating it from the main `creator-app`.

---

## 4. How to Test (Full LTI Flow)

1. **Build and Start:**
   Spin up the application from scratch using Docker Compose. Wait for the frontend build step to compile both `creator-app` and `module-chat`.
   ```bash
   docker-compose -f docker-compose-example.yaml up --build
   ```

2. **Instructor LTI Launch (Setup):**
   Execute an LTI Launch from Canvas LMS (or using a simulated POST request with valid OAuth1 signatures) as an Instructor, using a brand new activity ID not in the DB.
   - **Expected Result:** Redirection to the new Svelte SPA (`/m/chat/setup?token=...`). Review the UI and `@lamb/ui` components, select an assistant, and click Save. You should be seamlessly navigated to the Dashboard.

3. **Student LTI Launch (Consent):**
   Execute another LTI Launch using the same LTI key, but with a Student role.
   - **Expected Result:** You should first see the consent screen (`/m/chat/consent?token=...`). Clicking 'Agree' should redirect you directly to the internal OWI chat interface.

4. **Instructor Dashboard (Returning):**
   Launch again as an Instructor on the previously configured activity.
   - **Expected Result:** Direct redirection to `/m/chat/dashboard?resource_link_id=...&token=...`. Verify tabs, the student list, and chat transcript details load correctly.

---

## 5. Potential Bugs & Troubleshooting 🐛

While refactoring aimed for high backward compatibility via the API, the following risks and troubleshooting steps are critical:

### 🔴 1. The 404 Catch-All Loop (FastAPI vs Svelte Base Path)
**Symptom:** Visiting `/m/chat/dashboard` results in a white screen, a 404, or an infinite refresh loop.
**Cause:** SvelteKit's `paths.base` config might physically clash with FastAPI's `StaticFiles` mounting or `main.py` Catch-all logic.
**Check:** Ensure static resources (Vendor JS, images, CSS) deployed at `frontend/build/m/chat/...` load intact and do not collide with `creator-app` routes.

### 🔴 2. SvelteKit Fetching from the Wrong Port (CORS / Proxy)
**Symptom:** Svelte app loads but shows "Failed to load data" in development mode.
**Cause:** `module-chat` (running on `localhost:5174`) tries to `fetch('/lamb/...')` and hits its own Vite server instead of FastAPI (`localhost:9099`).
**Check:** Ensure `module-chat/vite.config.js` has a `server.proxy` block identical to `creator-app`'s.

### 🔴 3. Token Loss on Page Refresh (`window.location` vs Local Storage)
**Symptom:** Hitting F5 on the dashboard results in a "Session Expired (403)" error.
**Cause:** LTI JWTs arrive via URL params (`?token=`). If SvelteKit's internal router strips or loses the query parameter during navigation or form submission, the session dies.
**Check:** Ensure the `token` is intercepted and temporarily stored or correctly appended in all subsequent `fetch` requests during the SPA session.

### 🔴 4. Missing `@lamb/ui` Styles
**Symptom:** Buttons appear but lack Tailwind styling (looking like plain HTML).
**Cause:** Tailwind in `module-chat` is not configured to scan the `@lamb/ui` package.
**Check:** Verify `module-chat/tailwind.config.js` includes `../../packages/ui/src/**/*.{html,js,svelte,ts}` in its `content` array.

### 🔴 5. JSON Payload Migration Issues
**Symptom:** Submitting the Setup form crashes the backend.
**Cause:** Backend now reads payloads via `await request.json()`. If SvelteKit sends a raw boolean `false` for a checkbox, and the backend expects a "1" string or vice-versa, validation might fail.
**Check:** Verify all payload fields cast correctly (e.g., explicitly casting to `bool()` in Python).

### 🔴 6. Docker Build Output Misplacement
**Symptom:** Works locally with `pnpm dev` but fails in Docker.
**Cause:** Both apps might overwrite each other's `index.html` inside `build/`.
**Check:** Confirm `module-chat/svelte.config.js` properly configures `adapter-static` to output to `../../build/m/chat`.

### 🔴 7. pnpm ERR_PNPM_OUTDATED_LOCKFILE en Docker (CI)
**Symptom:** Al hacer `docker-compose up --build`, el contenedor `frontend-build` falla con código 1 y el error `ERR_PNPM_OUTDATED_LOCKFILE`.
**Cause:** Los entornos que detectan variables CI (como `CI=true` dentro de Docker) aplican implícitamente la directiva `--frozen-lockfile`. Si se añade una nueva dependencia cruzada (`@lamb/ui: "workspace:*"`) en un `package.json` pero el desarrollador no actualizó su `pnpm-lock.yaml` local previamente, fallará catastróficamente al rechazar cambiar el map en frío.
**Check:** Se resolvió de manera definitiva especificando `pnpm install --no-frozen-lockfile` directamente en los scripts YAML (`docker-compose-example.yaml` y `docker-compose-workers.yaml`).

---

## 6. Next Steps (Phase 4 and beyond)

The Chat Module served as an excellent proof-of-concept for the monorepo architecture. Future Phase 4 iterations will focus on standardizing this LTI module schema:
- **State Management:** Convert JWT injection from URL params into a robust Svelte Context (`$context`) or store.
- **API Typed Contracts:** Move Backend endpoints to formal Pydantic schemas (`response_model=...`), enabling OpenAPI/Redoc documentation instead of generic `JSONResponse` objects.
