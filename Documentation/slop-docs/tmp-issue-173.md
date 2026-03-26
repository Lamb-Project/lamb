# Issue #173: LAMB Internal Chat Persistence - Implementation Context

> **Status:** Implementation complete, needs testing/debugging  
> **Date:** December 29, 2025  
> **Related Issue:** https://github.com/Lamb-Project/lamb/issues/173

---

## 🎯 What Was Implemented

**Goal:** Add chat persistence to the Creator Interface's "Chat with Assistant" tab, enabling:
- Chat history sidebar (list previous conversations)
- Chat recall (load and continue previous chats)
- Title editing (user-controlled)
- Unified Activity tab (shows both OWI and LAMB internal chats)

**Architecture Decision:** Keep chat logs separate from pipeline analysis (pipeline logging will be a separate issue).

---

## 📁 Files Created

### Backend

| File | Purpose |
|------|---------|
| `backend/lamb/services/lamb_chats_service.py` | Service layer for LAMB chat CRUD operations |
| `backend/creator_interface/chats_router.py` | REST API endpoints for chat management |

### Frontend

No new files - modified existing `ChatInterface.svelte`

---

## 📝 Files Modified

### Backend

| File | Changes |
|------|---------|
| `backend/lamb/database_manager.py` | Added Migration 7: `lamb_chats` table + CRUD methods (~400 lines added at end of file) |
| `backend/creator_interface/main.py` | Added `from .chats_router import router as chats_router` and `router.include_router(chats_router, prefix="/chats")` |
| `backend/creator_interface/learning_assistant_proxy.py` | Added `wrap_streaming_response_with_chat_save()` function, modified `proxy_assistant_chat()` to save messages |
| `backend/lamb/services/chat_analytics_service.py` | Added `_get_lamb_internal_chats()` method, modified `get_chats_for_assistant()` and `get_assistant_stats()` to include LAMB chats |

### Frontend

| File | Changes |
|------|---------|
| `frontend/svelte-app/src/lib/components/ChatInterface.svelte` | Complete rewrite - added sidebar, chat list, title editing, persistence |

---

## 🗄️ Database Schema

**New Table: `lamb_chats`** (created by Migration 7 in `run_migrations()`)

```sql
CREATE TABLE lamb_chats (
    id TEXT PRIMARY KEY,                    -- UUID
    user_id INTEGER NOT NULL,               -- FK to Creator_users.id
    assistant_id INTEGER NOT NULL,          -- FK to assistants.id
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at INTEGER NOT NULL,            -- Unix timestamp
    updated_at INTEGER NOT NULL,            -- Unix timestamp
    chat JSON NOT NULL,                     -- {history: {messages: {...}}} (OWI-compatible)
    archived INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES Creator_users(id) ON DELETE CASCADE,
    FOREIGN KEY (assistant_id) REFERENCES assistants(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_lamb_chats_user ON lamb_chats(user_id);
CREATE INDEX idx_lamb_chats_assistant ON lamb_chats(assistant_id);
CREATE INDEX idx_lamb_chats_user_assistant ON lamb_chats(user_id, assistant_id);
CREATE INDEX idx_lamb_chats_updated ON lamb_chats(updated_at);
CREATE INDEX idx_lamb_chats_archived ON lamb_chats(archived);
```

---

## 🔌 New API Endpoints

**Base path:** `/creator/chats`

| Method | Endpoint | Purpose | Request Body |
|--------|----------|---------|--------------|
| POST | `/creator/chats` | Create new chat | `{assistant_id: int, title?: string}` |
| GET | `/creator/chats?assistant_id=X` | List user's chats | Query params: `assistant_id`, `include_archived`, `page`, `per_page` |
| GET | `/creator/chats/{chat_id}` | Get chat with messages | - |
| PUT | `/creator/chats/{chat_id}` | Update chat | `{title?: string, archived?: int}` |
| DELETE | `/creator/chats/{chat_id}` | Delete chat | - |

**Modified endpoint:**

| Method | Endpoint | Changes |
|--------|----------|---------|
| POST | `/creator/assistant/{id}/chat/completions` | Now accepts `chat_id` in body, returns `chat_id` in response/header |

---

## 🧪 Testing Checklist

### 1. Database Migration
```bash
# Check if table exists after starting backend
sqlite3 /opt/lamb/lamb_v4.db ".schema lamb_chats"
```

### 2. API Endpoints (curl tests)
```bash
# Get auth token first (replace with valid token)
TOKEN="your_auth_token"

# Create a chat
curl -X POST "http://localhost:9099/creator/chats" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"assistant_id": 1, "title": "Test Chat"}'

# List chats for assistant
curl "http://localhost:9099/creator/chats?assistant_id=1" \
  -H "Authorization: Bearer $TOKEN"

# Get specific chat
curl "http://localhost:9099/creator/chats/{chat_id}" \
  -H "Authorization: Bearer $TOKEN"

# Update title
curl -X PUT "http://localhost:9099/creator/chats/{chat_id}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "New Title"}'

# Delete chat
curl -X DELETE "http://localhost:9099/creator/chats/{chat_id}" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Frontend Testing
1. Navigate to Assistants → select an assistant → Chat tab
2. **Sidebar should appear** on the left with "Chat History" header and "New" button
3. **Send a message** → chat should be created, appear in sidebar
4. **Close tab, reopen** → chat should still be in sidebar
5. **Click chat in sidebar** → should load messages
6. **Click title** → should become editable
7. **Click X on chat** → should delete (with confirmation)

### 4. Activity Tab
1. Navigate to assistant → Activity tab
2. Should show chats from both sources
3. Each chat should have `source` field: "owi" or "lamb_internal"
4. Stats should include `owi_chats` and `lamb_internal_chats` counts

---

## ⚠️ Known Issues / Warnings

1. **Autofocus warning** in Svelte build (a11y warning, not error) - line 625
2. **Streaming response capture** - the `wrap_streaming_response_with_chat_save()` function captures streamed content, may need testing with edge cases

---

## 🔑 Key Code Locations

### Chat Persistence Flow

1. **Frontend sends message:**
   - `ChatInterface.svelte` → `handleSubmit()` 
   - Includes `chat_id` (null for new, UUID for existing)

2. **Backend receives:**
   - `learning_assistant_proxy.py` → `proxy_assistant_chat()`
   - Extracts `chat_id` from body
   - Calls `chats_service.add_user_message_and_create_if_needed()`

3. **After LLM response:**
   - Non-streaming: saves assistant response directly
   - Streaming: `wrap_streaming_response_with_chat_save()` captures and saves

4. **Frontend receives:**
   - Gets `chat_id` from response header (`X-Chat-Id`) or body
   - Updates `currentChatId` state
   - Refreshes chat list

### Activity Tab Union

- `chat_analytics_service.py` → `get_chats_for_assistant()`
- Calls `_get_lamb_internal_chats()` to get LAMB chats
- Merges with OWI chats, sorts by date
- Each chat has `source` field

---

## 🐛 Debugging Tips

### Backend Logs
```bash
# Watch for chat-related logs
tail -f /path/to/logs | grep -i "chat\|lamb_chat"
```

### Database Inspection
```bash
# Count chats
sqlite3 /opt/lamb/lamb_v4.db "SELECT COUNT(*) FROM lamb_chats"

# View recent chats
sqlite3 /opt/lamb/lamb_v4.db "SELECT id, title, user_id, assistant_id, created_at FROM lamb_chats ORDER BY created_at DESC LIMIT 10"

# Check chat JSON structure
sqlite3 /opt/lamb/lamb_v4.db "SELECT chat FROM lamb_chats LIMIT 1" | python -m json.tool
```

### Frontend Console
- Open browser DevTools → Console
- Look for `[timestamp] CHAT:` prefixed logs from `logWithTime()`

---

## 📚 Related Documentation

- `Documentation/chat_analytics_project.md` - Original analytics spec
- `Documentation/DOCUMENTATION_INDEX.md` - System overview
- Issue #173 on GitHub - Original issue description

---

## 🔄 Next Steps After Testing

1. **If bugs found:** Fix and re-test
2. **If working:** Mark todos complete, close issue
3. **Future:** Create separate issue for Pipeline Logging (as discussed in #173)

---

*Generated: December 29, 2025*

