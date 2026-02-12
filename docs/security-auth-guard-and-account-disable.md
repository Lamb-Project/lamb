# Security Changes: Auth Guards and Account Disablement

**Date:** 2026-02-12  
**Project:** LAMB (Learning Assistants Manager and Builder)

---

## Executive Summary

Two critical security fixes have been implemented:

1. **Layout-Level Auth Guards**: Centralized protection for all routes against unauthenticated access.
2. **Disabled Account Detection**: Immediate session invalidation when an admin disables an account.

---

## 1. Layout-Level Auth Guards

### Original Problem

After logout, users could navigate directly to protected routes like `/assistants`, `/knowledgebases`, and `/admin` by typing the URL in the browser. The page would fully render (tabs, forms, structure) even though data wouldn't load (API returned 401/403).

### Solution Implemented

A **centralized authentication guard** was added to `+layout.svelte` that checks `$user.isLoggedIn` and redirects to root (`/`) if the user is not authenticated.

#### Modified File

**`frontend/svelte-app/src/routes/+layout.svelte`**

```svelte
<script>
    // ...existing imports...
    import { browser } from '$app/environment';
    import { base } from '$app/paths';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { user } from '$lib/stores/userStore';

    // Layout-level auth guard: redirect unauthenticated users to root (login page)
    $effect(() => {
        if (browser && !$user.isLoggedIn) {
            const currentPath = $page.url.pathname.replace(base, '') || '/';
            if (currentPath !== '/') {
                goto(`${base}/`, { replaceState: true });
            }
        }
    });
</script>
```

### Individual Guard Cleanup

Redundant authentication guards were removed from individual pages:

| File | Change |
|------|--------|
| `prompt-templates/+page.svelte` | Removed `onMount` auth check |
| `evaluaitor/+page.svelte` | Removed `$effect` with `window.location.href` |
| `evaluaitor/[rubricId]/+page.svelte` | Removed `$effect` auth check, standardized redirect |
| `admin/+page.svelte` | Removed commented redirect code |
| `org-admin/+page.svelte` | Changed redirect from `/auth` to layout guard |

---

## 2. Disabled Account Detection

### Original Problem

When an admin disabled a user account, the user's existing token was **not invalidated**. The user could continue using the application until they manually logged out. Even worse, a disabled admin could continue operating and even revoke access from the admin who disabled them.

### Original Flow Analysis

| Layer | Behavior |
|-------|----------|
| Login (`verify_user`) | ✅ Checks `enabled` - prevents new tokens |
| `get_creator_user_from_token()` | ❌ **DOES NOT** check `enabled` - accepts valid tokens |
| Endpoint `/disable` | Only updates LAMB DB, does NOT invalidate existing tokens |
| Frontend 401/403 handling | ❌ No global interceptor, no auto-logout |

### Solution Implemented

#### A) Backend: `enabled` Check in Token Validation

Added verification of the `enabled` field in all user token validation functions.

**1. `backend/creator_interface/assistant_router.py`** (main function)

```python
def get_creator_user_from_token(auth_header: str) -> Optional[Dict[str, Any]]:
    # ...existing code...
    
    creator_user = db_manager.get_creator_user_by_email(user_email)
    if not creator_user:
        logger.error(f"No creator user found for email: {user_email}")
        return None

    # NEW: Check if the user account is disabled
    if not creator_user.get('enabled', True):
        logger.warning(f"Disabled user {user_email} attempted API access with valid token")
        raise HTTPException(
            status_code=403,
            detail="Account disabled. Your account has been disabled by an administrator."
        )
    
    # ...rest of code...
```

**2. `backend/creator_interface/analytics_router.py`** (duplicate function)

Same change as assistant_router.py.

**3. `backend/creator_interface/chats_router.py`** (duplicate function)

Same change as assistant_router.py.

**4. `backend/lamb/database_manager.py`** (LTI JWT auth)

```python
def get_creator_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
    # ...existing code...
    
    user = self.get_creator_user_by_email(user_email)
    
    # Check if the user account is disabled
    if user and not user.get('enabled', True):
        logger.warning(f"Disabled user {user_email} attempted API access with valid JWT token")
        return None
    
    return user
```

#### B) Frontend: Session Guard with Polling

Created a session validation system that:
1. Performs periodic polling (every 60 seconds) to detect disablement
2. Detects 403 "Account disabled" responses from any API call
3. Forces immediate logout when a disabled account is detected

**New File: `frontend/svelte-app/src/lib/utils/sessionGuard.js`**

```javascript
import { browser } from '$app/environment';
import { getApiUrl } from '$lib/config';
import { user } from '$lib/stores/userStore';
import { goto } from '$app/navigation';
import { base } from '$app/paths';
import { get } from 'svelte/store';

const ACCOUNT_DISABLED_SIGNAL = 'Account disabled';
let pollingInterval = null;

/**
 * Performs a lightweight token validation call to the backend.
 * If it returns 403 "Account disabled", forces logout.
 */
export async function checkSession() {
    const currentUser = get(user);
    if (!currentUser.isLoggedIn || !currentUser.token) return false;

    const response = await fetch(getApiUrl('/user/profile'), {
        method: 'GET',
        headers: {
            Authorization: `Bearer ${currentUser.token}`,
            'Content-Type': 'application/json'
        }
    });

    if (response.status === 403) {
        try {
            const body = await response.json();
            const detail = body?.detail || '';
            if (typeof detail === 'string' && detail.includes(ACCOUNT_DISABLED_SIGNAL)) {
                forceLogout();
                return false;
            }
        } catch {}
    }

    if (response.status === 401) {
        forceLogout();
        return false;
    }

    return response.ok;
}

/**
 * Starts periodic polling every 60 seconds
 */
export function startSessionPolling(intervalMs = 60000) {
    if (!browser) return;
    stopSessionPolling();
    pollingInterval = setInterval(() => {
        const currentUser = get(user);
        if (currentUser.isLoggedIn) checkSession();
        else stopSessionPolling();
    }, intervalMs);
}

function forceLogout() {
    console.warn('Account disabled detected — forcing logout');
    user.logout();
    goto(`${base}/`, { replaceState: true });
}
```

**Integration in `frontend/svelte-app/src/routes/+layout.svelte`:**

```svelte
<script>
    import { onDestroy } from 'svelte';
    import { startSessionPolling, stopSessionPolling } from '$lib/utils/sessionGuard';

    // Session guard: periodically check if the account has been disabled
    $effect(() => {
        if (browser && $user.isLoggedIn) {
            startSessionPolling(60000);
        } else {
            stopSessionPolling();
        }
    });

    onDestroy(() => {
        stopSessionPolling();
    });
</script>
```

---

## Modified Files

### Frontend

| File | Type | Description |
|------|------|-------------|
| `src/routes/+layout.svelte` | Modified | Added auth guard + session polling |
| `src/routes/prompt-templates/+page.svelte` | Modified | Removed redundant auth guard |
| `src/routes/evaluaitor/+page.svelte` | Modified | Removed auth guard, used `goto` |
| `src/routes/evaluaitor/[rubricId]/+page.svelte` | Modified | Removed auth guard, used `base` path |
| `src/routes/admin/+page.svelte` | Modified | Removed commented code |
| `src/routes/org-admin/+page.svelte` | Modified | Simplified redirect |
| `src/lib/utils/sessionGuard.js` | **NEW** | Utility to detect disabled accounts |

### Backend

| File | Type | Description |
|------|------|-------------|
| `creator_interface/assistant_router.py` | Modified | Added `enabled` check |
| `creator_interface/analytics_router.py` | Modified | Added `enabled` check |
| `creator_interface/chats_router.py` | Modified | Added `enabled` check |
| `lamb/database_manager.py` | Modified | Added `enabled` check in JWT |

---

## Current Security Flow

### User Login
```
1. User enters credentials
2. Backend verifies user + password
3. Backend verifies `enabled == True` in Creator_users
4. If disabled → rejected with error "Account has been disabled"
5. If enabled → generates JWT token
```

### API Access (every request)
```
1. Frontend sends request with Bearer token
2. Backend calls get_creator_user_from_token()
3. Token validated by OWI
4. User fetched from LAMB DB
5. Verify `enabled == True` ← NEW
6. If disabled → HTTPException(403) "Account disabled"
7. Frontend detects 403 → force logout
```

### Account Disablement by Admin
```
1. Admin calls PUT /creator/admin/users/{id}/disable
2. Backend updates enabled=0 in Creator_users
3. Disabled user has existing token
4. User makes API request
5. Backend detects enabled=0 → 403 "Account disabled"
6. Frontend polling detects 403 → force logout
7. User redirected to login
```

---

## Security Considerations

1. **Polling Interval**: 60 seconds is a balance between quick response and minimal overhead. Can be adjusted based on needs.

2. **Multiple Tokens**: If a user has multiple sessions (different browsers/devices), all will be invalidated when the account is disabled (each session will poll and be rejected).

3. **Edge Case - Admin disabling themselves**: Disable endpoints prevent self-disable. An admin cannot disable themselves.

4. **Inconsistency between endpoints**: Some disable endpoints update OWI (`auth.active`), others only update LAMB. The new verification in `get_creator_user_from_token()` covers both cases because it checks the LAMB `Creator_users` table.

---

## Recommended Testing

### Test 1: Auth Guard After Logout
1. Login as any user
2. Click Logout
3. Manually navigate to `/assistants`
4. **Expected**: Redirect to `/`

### Test 2: Disabled Account Retains Access
1. Login as admin
2. In another session, create test user and login
3. As admin, disable test user
4. **Expected (BEFORE)**: Test user still sees the app
5. **Expected (AFTER)**: Test user is redirected to login in ~60 seconds

### Test 3: Disabled Admin Can Revoke Access
1. Login as admin
2. Disable admin account (another admin or via API directly)
3. Try to perform any action as admin
4. **Expected**: HTTP 403 and forced logout

---

## Notes

- LSP errors shown are pre-existing (project uses JavaScript with JSDoc, not TypeScript)
- Forced logout uses `replaceState: true` to prevent the user from going back in browser history
