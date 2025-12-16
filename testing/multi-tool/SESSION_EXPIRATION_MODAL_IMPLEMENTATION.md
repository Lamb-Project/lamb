# Session Expiration Modal Implementation

## Overview
Implemented a user-friendly session expiration modal that automatically appears when authentication tokens expire or become invalid, and redirects users to the login page.

## Implementation Details

### Components Created

#### 1. SessionExpiredModal Component
**Location:** `frontend/svelte-app/src/lib/components/modals/SessionExpiredModal.svelte`

- Modal dialog that appears when session expires
- Shows clear message: "Your session has expired or the token is invalid. Please sign in again to continue."
- "Go to Login" button that:
  - Logs out the user (clears token from localStorage)
  - Closes the modal
  - Redirects to home/login page (`/`)
- Keyboard support: ESC or Enter to proceed
- Accessible with ARIA labels

#### 2. Session Store
**Location:** `frontend/svelte-app/src/lib/stores/sessionStore.js`

- Svelte store to manage session expiration state
- Functions: `showSessionExpired()`, `hideSessionExpired()`
- Used to trigger the modal from anywhere in the app

#### 3. HTTP Client Utility
**Location:** `frontend/svelte-app/src/lib/utils/httpClient.js`

- `authenticatedFetch()` wrapper around native `fetch()`
- Automatically detects 401 Unauthorized responses
- Checks error messages for authentication-related keywords
- Shows session expired modal when detected
- Maintains backward compatibility with existing fetch calls

#### 4. Axios Interceptor
**Location:** `frontend/svelte-app/src/lib/utils/axiosInterceptor.js`

- Global axios interceptor setup
- Response interceptor catches 401 errors
- Request interceptor adds auth token automatically
- Shows session expired modal for authentication errors
- Used by services that use axios (e.g., `knowledgeBaseService.js`)

### Integration Points

#### Layout Integration
**Location:** `frontend/svelte-app/src/routes/+layout.svelte`

- Added `SessionExpiredModal` component
- Subscribes to `sessionExpired` store
- Sets up axios interceptor on mount
- Modal appears globally across all pages

#### Service Updates
**Location:** `frontend/svelte-app/src/lib/services/assistantService.js`

- Replaced all `fetch()` calls with `authenticatedFetch()`
- Ensures 401 errors are caught and modal is shown
- No breaking changes to API

## How It Works

### Flow Diagram
```
User makes API request
    ↓
Service calls authenticatedFetch() or axios
    ↓
Backend returns 401 Unauthorized
    ↓
HTTP client/interceptor detects 401
    ↓
Checks error message for auth keywords
    ↓
Sets sessionExpired store to true
    ↓
Modal appears with message
    ↓
User clicks "Go to Login"
    ↓
User logged out, token cleared
    ↓
Redirected to home/login page
```

### Error Detection
The system detects session expiration when:
1. HTTP status code is 401
2. Error message contains keywords:
   - "authentication"
   - "session"
   - "token"
   - "expired"
   - "invalid"

## Usage

### For Services Using Fetch
```javascript
import { authenticatedFetch } from '$lib/utils/httpClient';

const response = await authenticatedFetch(url, {
    headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
    }
});
```

### For Services Using Axios
Axios interceptor is automatically set up in the layout. No changes needed - just use axios normally:
```javascript
import axios from 'axios';

const response = await axios.get(url, {
    headers: {
        Authorization: `Bearer ${token}`
    }
});
```

### Manual Trigger
If you need to manually show the modal:
```javascript
import { showSessionExpired } from '$lib/stores/sessionStore';

showSessionExpired();
```

## Testing

### Test Cases

1. **Expired Token**
   - Login to the app
   - Wait for token to expire (or manually expire it)
   - Make any API request
   - Modal should appear automatically

2. **Invalid Token**
   - Login to the app
   - Manually corrupt token in localStorage
   - Make any API request
   - Modal should appear

3. **Modal Interaction**
   - When modal appears, click "Go to Login"
   - Should redirect to `/`
   - Token should be cleared from localStorage
   - User should be logged out

4. **Keyboard Navigation**
   - When modal appears, press ESC or Enter
   - Should trigger same behavior as clicking button

## Benefits

1. **Better UX:** Users get clear feedback instead of cryptic error messages
2. **Automatic Handling:** No need to handle 401 errors in every component
3. **Consistent Behavior:** Same modal appears regardless of which API call fails
4. **Easy Recovery:** One click to get back to login
5. **Accessible:** ARIA labels and keyboard support

## Future Enhancements

1. **Token Refresh:** Implement automatic token refresh before showing modal
2. **Retry Logic:** Option to retry request after re-login
3. **Custom Messages:** Allow services to provide custom error messages
4. **Analytics:** Track session expiration frequency
5. **Auto-redirect:** Option to auto-redirect without showing modal (for background requests)

## Files Modified

- `frontend/svelte-app/src/routes/+layout.svelte` - Added modal and interceptor setup
- `frontend/svelte-app/src/lib/services/assistantService.js` - Updated to use authenticatedFetch

## Files Created

- `frontend/svelte-app/src/lib/components/modals/SessionExpiredModal.svelte`
- `frontend/svelte-app/src/lib/stores/sessionStore.js`
- `frontend/svelte-app/src/lib/utils/httpClient.js`
- `frontend/svelte-app/src/lib/utils/axiosInterceptor.js`
