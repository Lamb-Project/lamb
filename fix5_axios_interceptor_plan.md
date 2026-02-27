# Fix 5: Axios Global Interceptor Plan

## The Problem

5 services still make API calls without automatic disabled-account detection:
- `assistantService.js` — uses `axios` + `fetch`
- `knowledgeBaseService.js` — uses `axios`
- `templateService.js` — uses `axios`
- `analyticsService.js` — uses `axios`
- `authService.js` — uses `fetch`

Unlike `adminService.js` (which already uses `authenticatedFetch`), these services handle auth manually via `localStorage.getItem('userToken')` on every call.

---

## The Solution: Two-track approach

### Track 1: Axios interceptor (covers services using axios)

We add a **global axios interceptor** in `apiClient.js`. This runs automatically on **every axios call** across the whole app — no need to change each service.

> **Important:** We register it on the **global `axios` instance** (not a custom instance), so every `import axios from 'axios'` in every service benefits immediately with zero changes to the service files themselves.

```
Request flow with interceptor:
  axios.get(url)
       ↓
  [REQUEST interceptor] → auto-adds Authorization header
       ↓
  HTTP call
       ↓
  [RESPONSE interceptor] → on error: calls handleApiResponse(error.response)
       ↓                              → if 401/403 → forceLogout
  Service .catch() handler
```

### Track 2: `authenticatedFetch` (keeps covering services using fetch)

`authenticatedFetch` already exists in `apiClient.js` and handles `fetch`-based calls (`adminService.js`, `authService.js` endpoints after `/me`). It stays as is — no changes needed here.

---

## Changes Required

### [MODIFY] `frontend/svelte-app/src/lib/utils/apiClient.js`

Add at the **bottom of the file**:

```js
import axios from 'axios';

// ────────────────────────────────────────────────────
// Global Axios interceptors: auto-auth + session guard
// ────────────────────────────────────────────────────

// REQUEST: inject Authorization header automatically
axios.interceptors.request.use(config => {
    const token = getAuthToken();
    if (token) {
        config.headers = config.headers ?? {};
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// RESPONSE: detect disabled/deleted/expired account on every axios error
axios.interceptors.response.use(
    response => response,   // 2xx — pass through unchanged
    async error => {
        if (error.response) {
            // Adapt axios response to be compatible with handleApiResponse
            const adapted = {
                status: error.response.status,
                headers: {
                    get: (name) => error.response.headers[name.toLowerCase()] ?? null
                }
            };
            await handleApiResponse(adapted);
        }
        return Promise.reject(error);   // still propagate to service .catch()
    }
);
```

**Why wrap the headers?**
`handleApiResponse` uses `response.headers.get('X-Account-Status')` — the native fetch API.
Axios headers are a plain object, so we adapt it with a small `get()` wrapper.
No changes needed to `handleApiResponse`.

---

## What changes in the service files?

**Nothing structural.** Each service can keep:
- Its `axios.get/post/put/delete` calls
- Its `if (axios.isAxiosError(error))` error handling
- Its `.data` access pattern

The only optional cleanup (not required):
```js
// BEFORE (manual token on every call)
const token = localStorage.getItem('userToken');
const response = await axios.get(url, {
    headers: { Authorization: `Bearer ${token}` }
});

// AFTER (token injected by interceptor automatically)
const response = await axios.get(url);
// No headers needed — interceptor adds it
```
This cleanup is optional but recommended since the token logic is now centralized.

---

## What about `authService.js` login/signup?

The `/login` and `/signup` endpoints don't require a token and should NOT add the Authorization header. The interceptor handles this gracefully:

```js
axios.interceptors.request.use(config => {
    const token = getAuthToken();
    if (token) {  // ← if no token (not logged in), nothing is added
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});
```

So unauthenticated calls (login/signup) work normally. ✅

---

## Summary

| Service | Uses | Change needed |
|---------|------|---------------|
| `adminService.js` | `authenticatedFetch` | ✅ Already done |
| `assistantService.js` | `axios` + `fetch` | Interceptor covers `axios` calls |
| `knowledgeBaseService.js` | `axios` | Interceptor covers all |
| `templateService.js` | `axios` | Interceptor covers all |
| `analyticsService.js` | `axios` | Interceptor covers all |
| `authService.js` | `fetch` | Login/signup don't need it; `/me` already uses `authenticatedFetch` |

One file change (`apiClient.js`) → automatic coverage across all services. ✅
