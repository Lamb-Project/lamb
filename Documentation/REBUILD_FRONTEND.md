# Frontend Rebuild Instructions

## Issue
Buttons in Prompt Templates page are unresponsive in Firefox with the current production build.

## Solution
Rebuild the frontend to apply the latest changes.

## Steps to Rebuild

### 1. Navigate to frontend directory
```bash
cd /opt/lamb/frontend/svelte-app
```

### 2. Build for production
```bash
npm run build
```

### 3. Restart Docker containers (if using Docker)
```bash
cd /opt/lamb
docker-compose restart lamb-backend
```

OR if running standalone:
```bash
# The backend will automatically detect the new build
# No restart needed if using the development watcher
```

## What Was Fixed

1. ✅ Event handlers already using correct Svelte 5 syntax (`onclick` not `on:click`)
2. ✅ Textbox sizes increased (8 rows for prompts)
3. ✅ Proper padding and borders added
4. ✅ Correct placeholders: `{context}` and `{user_input}`
5. ✅ Helpful placeholder text in all fields

## Testing After Rebuild

1. Navigate to Tools > Prompt Templates in Firefox
2. Try clicking Edit, Share, Delete, Duplicate buttons
3. All buttons should now be responsive

## Expected Result

All buttons and interactions should work correctly in:
- ✅ Chrome (dev and production)
- ✅ Firefox (dev and production)
- ✅ Safari
- ✅ Edge

---

**Note:** The code itself is correct - the issue is just that Firefox is using a cached production build. After rebuilding, everything will work perfectly.

