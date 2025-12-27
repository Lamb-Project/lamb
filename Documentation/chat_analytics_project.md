# LAMB Chat Analytics Integration Project

**Version:** 1.0  
**Date:** December 27, 2025  
**Status:** Planning  

---

## Executive Summary

This document outlines the plan to integrate chat analytics functionality from the `openwebui-db-inspect` prototype into the LAMB platform. The goal is to provide learning assistant creators with insights into how their assistants are being used through chat conversations stored in the Open WebUI database.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Current Architecture](#2-current-architecture)
3. [Proposed Changes](#3-proposed-changes)
4. [Technical Design](#4-technical-design)
5. [Implementation Plan](#5-implementation-plan)
6. [Frontend Design](#6-frontend-design)
7. [API Specification](#7-api-specification)
8. [Data Models](#8-data-models)
9. [Questions and Considerations](#9-questions-and-considerations)
10. [Timeline and Milestones](#10-timeline-and-milestones)

---

## 1. Problem Statement

### Context

LAMB integrates with Open WebUI (OWI) for the end-user chat interface. Each LAMB assistant published to OWI creates a corresponding model record (`lamb_assistant.{assistant_id}`). Chat conversations are stored in OWI's SQLite database, but there's currently **no way for creators to view or analyze these conversations**.

### Goals

1. **Refactor owi_bridge**: Convert `owi_router.py` from an API router pattern to a service layer pattern consistent with other LAMB services
2. **Build Analytics Services**: Create services to query and analyze OWI chat data
3. **Expose Analytics via Creator Interface**: Add endpoints in `creator_interface` for frontend consumption
4. **Frontend Analytics Tab**: Add a "Chat Analytics" tab within the assistant detail view

### Reference Implementation

The `openwebui-db-inspect` Flask app demonstrates the core functionality:
- List chats with filtering by date range and model
- View individual chat conversations with messages
- Parse JSON chat structure from OWI database

---

## 2. Current Architecture

### OWI Bridge Module Structure

```
backend/lamb/owi_bridge/
├── owi_database.py    # Database connection and queries
├── owi_users.py       # User management (class: OwiUserManager)
├── owi_group.py       # Group management (class: OwiGroupManager)
├── owi_model.py       # Model management (class: OWIModel)
├── owi_router.py      # FastAPI router (PROBLEM: Mixed pattern)
└── readme.md          # Documentation
```

### Current Pattern Issues

**Problem 1: owi_router.py mixes concerns**

The `owi_router.py` file is 1,174 lines and:
- Acts as a FastAPI router with endpoints
- Contains business logic directly in endpoint handlers
- Is mounted directly on `/lamb/v1/OWI`
- Mixes API-level concerns with service-level logic

**Correct pattern (used elsewhere):**
- `lamb/services/` contains service classes (AssistantService, OrganizationService, etc.)
- `creator_interface/` routers call these services
- Clean separation of concerns

### OWI Database Schema (Relevant Tables)

**chat table:**
```sql
CREATE TABLE IF NOT EXISTS "chat" (
    "id" VARCHAR(255) NOT NULL,
    "user_id" VARCHAR(255) NOT NULL,
    "title" TEXT NOT NULL,
    "share_id" VARCHAR(255),
    "archived" INTEGER NOT NULL,
    "created_at" DATETIME NOT NULL,
    "updated_at" DATETIME NOT NULL,
    chat JSON,
    pinned BOOLEAN,
    meta JSON DEFAULT '{}' NOT NULL,
    folder_id TEXT
);
```

**chat JSON structure:**
```json
{
  "id": "",
  "title": "Chat Title",
  "models": ["lamb_assistant.1"],
  "params": {},
  "history": {
    "messages": {
      "message-uuid-1": {
        "id": "message-uuid-1",
        "parentId": null,
        "childrenIds": ["message-uuid-2"],
        "role": "user",
        "content": "Message text...",
        "timestamp": 1758180800,
        "models": ["lamb_assistant.1"]
      },
      "message-uuid-2": {
        "parentId": "message-uuid-1",
        "id": "message-uuid-2",
        "role": "assistant",
        "content": "Response text..."
      }
    }
  }
}
```

**user table:**
```sql
CREATE TABLE "user" (
    "id" VARCHAR(255) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "email" VARCHAR(255) NOT NULL,
    "role" VARCHAR(255) NOT NULL,
    ...
);
```

---

## 3. Proposed Changes

### Phase 1: OWI Bridge Refactoring

**Create: `backend/lamb/services/owi_bridge_service.py`**

This new service will consolidate functionality from the existing OWI bridge classes:

```python
class OwiBridgeService:
    """
    Unified service for OWI database operations.
    Wraps OwiDatabaseManager, OwiUserManager, OwiGroupManager, OWIModel
    """
    
    def __init__(self):
        self.db = OwiDatabaseManager()
        self.users = OwiUserManager()
        self.groups = OwiGroupManager()
        self.models = OWIModel(self.db)
```

**Refactor: `backend/lamb/owi_bridge/owi_router.py`**

Convert to thin API layer that delegates to services:
- Move business logic to service classes
- Keep only HTTP handling in router
- Consider deprecating `/lamb/v1/OWI` endpoints in favor of `/creator/` unified API

### Phase 2: Chat Analytics Services

**Create: `backend/lamb/services/chat_analytics_service.py`**

```python
class ChatAnalyticsService:
    """
    Service for analyzing OWI chat data
    """
    
    # Core functionality
    def get_chats_for_assistant(assistant_id, filters) -> List[ChatSummary]
    def get_chat_detail(chat_id) -> ChatDetail
    def get_chat_messages(chat_id) -> List[Message]
    
    # Analytics
    def get_assistant_chat_stats(assistant_id) -> AssistantChatStats
    def get_unique_users_count(assistant_id) -> int
    def get_message_count(assistant_id) -> int
    def get_chat_timeline(assistant_id, period) -> List[TimelinePoint]
```

### Phase 3: Creator Interface Endpoints

**New endpoints in `creator_interface/`:**

```
GET  /creator/assistant/{id}/chats
     List chats for an assistant with pagination and filters
     
GET  /creator/assistant/{id}/chats/{chat_id}
     Get detailed chat conversation

GET  /creator/assistant/{id}/analytics
     Get analytics summary for assistant
     
GET  /creator/assistant/{id}/analytics/timeline
     Get chat activity over time
```

### Phase 4: Frontend Analytics Tab

**Add to assistant detail view (`+page.svelte`):**

New tab "Analytics" alongside existing tabs:
- Properties
- Edit  
- Share
- Chat
- **Analytics** ← NEW

---

## 4. Technical Design

### 4.1 Service Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Creator Interface                          │
│  /creator/assistant/{id}/chats                               │
│  /creator/assistant/{id}/analytics                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                              │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │OwiBridgeService  │  │   ChatAnalyticsService           │ │
│  │- users           │  │   - get_chats_for_assistant()   │ │
│  │- groups          │  │   - get_chat_detail()           │ │
│  │- models          │  │   - get_assistant_chat_stats()  │ │
│  └─────────┬────────┘  └─────────────────┬───────────────┘ │
└────────────┼────────────────────────────┼─────────────────┘
             │                            │
             ▼                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  OWI Database Layer                          │
│  OwiDatabaseManager (backend/lamb/owi_bridge/owi_database.py) │
│  - execute_query()                                           │
│  - get_connection()                                          │
└─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│              Open WebUI SQLite Database                      │
│              $OWI_PATH/webui.db                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Query Design

**Get chats for assistant:**
```sql
SELECT 
    c.id,
    c.user_id,
    c.title,
    c.created_at,
    c.updated_at,
    c.chat,
    u.name as user_name,
    u.email as user_email
FROM chat c
JOIN user u ON c.user_id = u.id
WHERE json_extract(c.chat, '$.models') LIKE '%lamb_assistant.{assistant_id}%'
  AND c.created_at >= ?
  AND c.created_at <= ?
ORDER BY c.created_at DESC
LIMIT ? OFFSET ?
```

**Get message count:**
```sql
SELECT 
    COUNT(DISTINCT c.id) as chat_count,
    (SELECT COUNT(*) 
     FROM chat c2, 
     json_each(json_extract(c2.chat, '$.history.messages'))
     WHERE json_extract(c2.chat, '$.models') LIKE '%lamb_assistant.{assistant_id}%'
    ) as message_count
FROM chat c
WHERE json_extract(c.chat, '$.models') LIKE '%lamb_assistant.{assistant_id}%'
```

### 4.3 Authorization Model

Creators should only see analytics for:
1. Assistants they own
2. Assistants shared with them (with appropriate permissions)

The authorization check happens at the creator_interface layer before calling services.

---

## 5. Implementation Plan

### Phase 1: Service Layer Refactoring (3-4 hours)

**Step 1.1: Create OwiBridgeService**
- Create `backend/lamb/services/owi_bridge_service.py`
- Wrap existing manager classes
- Add any missing functionality

**Step 1.2: Refactor owi_router.py**
- Extract business logic to services
- Keep only HTTP handling
- Update creator_interface to use new services

### Phase 2: Chat Analytics Service (4-6 hours)

**Step 2.1: Create ChatAnalyticsService**
- Create `backend/lamb/services/chat_analytics_service.py`
- Implement core chat querying methods
- Implement analytics calculations

**Step 2.2: Add to OwiDatabaseManager**
- Add new query methods for chat data
- Optimize queries for large datasets

### Phase 3: Creator Interface Endpoints (3-4 hours)

**Step 3.1: Create analytics_router.py**
- Or add endpoints to existing assistant_router.py
- Implement GET endpoints for chats and analytics
- Add proper authorization

### Phase 4: Frontend Implementation (6-8 hours)

**Step 4.1: Create ChatAnalytics component**
- Svelte component for displaying analytics
- Charts for timeline data
- Table for chat list

**Step 4.2: Integrate into assistant detail view**
- Add "Analytics" tab
- Wire up API calls
- Handle loading/error states

---

## 6. Frontend Design

### Tab Location

```
┌─────────────────────────────────────────────────────────────┐
│  [Properties] [Edit] [Share] [Chat] [Analytics]              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Analytics Tab Content                                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Analytics Tab Layout

```
┌─────────────────────────────────────────────────────────────┐
│ 📊 Chat Analytics for: {Assistant Name}                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Stats Cards Row:                                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │Total    │ │Unique   │ │Total    │ │Avg Msgs │           │
│  │Chats    │ │Users    │ │Messages │ │Per Chat │           │
│  │  247    │ │   89    │ │  1,456  │ │   5.9   │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                                                               │
│  Activity Timeline:                                          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ [Chart: Chats over time - bar chart or line chart]      │ │
│  │                                                          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Recent Chats:                                               │
│  ┌───────────────────────────────────────────────────┬─────┐ │
│  │ Date Range: [Start] - [End]   Model: [dropdown]   │ 🔍  │ │
│  ├─────────┬────────────┬──────────────┬─────────────┼─────┤ │
│  │ Date    │ User       │ Title        │ Messages    │ View│ │
│  ├─────────┼────────────┼──────────────┼─────────────┼─────┤ │
│  │ Dec 27  │ user@edu   │ Math Help    │     8       │  👁  │ │
│  │ Dec 26  │ stud@edu   │ Essay Review │    12       │  👁  │ │
│  │ ...     │ ...        │ ...          │   ...       │ ... │ │
│  └─────────┴────────────┴──────────────┴─────────────┴─────┘ │
│                                                               │
│  [< Prev] Page 1 of 25 [Next >]                              │
└─────────────────────────────────────────────────────────────┘
```

### Chat Detail Modal

```
┌─────────────────────────────────────────────────────────────┐
│ 💬 Chat: "Math Help"                           [Close ✕]    │
├─────────────────────────────────────────────────────────────┤
│ User: user@edu.com                                          │
│ Started: Dec 27, 2025 10:30 AM                              │
│ Messages: 8                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────────────────────────────────┐              │
│  │ 👤 User (10:30 AM)                         │              │
│  │ Can you help me understand quadratic       │              │
│  │ equations?                                 │              │
│  └───────────────────────────────────────────┘              │
│                                                               │
│  ┌───────────────────────────────────────────┐              │
│  │ 🤖 Assistant (10:30 AM)                    │              │
│  │ Of course! Quadratic equations are         │              │
│  │ polynomial equations of degree 2...        │              │
│  └───────────────────────────────────────────┘              │
│                                                               │
│  ... more messages ...                                       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. API Specification

### 7.1 List Chats for Assistant

```http
GET /creator/assistant/{assistant_id}/chats
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter    | Type     | Required | Description                     |
|-------------|----------|----------|---------------------------------|
| start_date  | datetime | No       | Filter chats from this date     |
| end_date    | datetime | No       | Filter chats until this date    |
| user_email  | string   | No       | Filter by specific user         |
| page        | int      | No       | Page number (default: 1)        |
| per_page    | int      | No       | Items per page (default: 20)    |

**Response:**
```json
{
  "chats": [
    {
      "id": "493b9867-ce4d-497a-a174-8034065b3e1b",
      "title": "Math Help",
      "user_id": "26de440e-adf5-47ed-ba98-c147f6c5fbb1",
      "user_name": "John Student",
      "user_email": "john@edu.com",
      "message_count": 8,
      "created_at": "2025-12-27T10:30:00Z",
      "updated_at": "2025-12-27T10:45:00Z"
    }
  ],
  "total": 247,
  "page": 1,
  "per_page": 20,
  "total_pages": 13
}
```

### 7.2 Get Chat Detail

```http
GET /creator/assistant/{assistant_id}/chats/{chat_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "493b9867-ce4d-497a-a174-8034065b3e1b",
  "title": "Math Help",
  "user": {
    "id": "26de440e-adf5-47ed-ba98-c147f6c5fbb1",
    "name": "John Student",
    "email": "john@edu.com"
  },
  "created_at": "2025-12-27T10:30:00Z",
  "updated_at": "2025-12-27T10:45:00Z",
  "messages": [
    {
      "id": "f498e761-6bb2-4fc4-9f63-4543ffb54cec",
      "role": "user",
      "content": "Can you help me understand quadratic equations?",
      "timestamp": "2025-12-27T10:30:00Z"
    },
    {
      "id": "ceefb82e-5154-4c32-b738-4b31a5cb90aa",
      "role": "assistant",
      "content": "Of course! Quadratic equations are...",
      "timestamp": "2025-12-27T10:30:05Z"
    }
  ]
}
```

### 7.3 Get Analytics Summary

```http
GET /creator/assistant/{assistant_id}/analytics
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter    | Type     | Required | Description                     |
|-------------|----------|----------|---------------------------------|
| start_date  | datetime | No       | Stats from this date            |
| end_date    | datetime | No       | Stats until this date           |

**Response:**
```json
{
  "assistant_id": 1,
  "period": {
    "start": "2025-01-01T00:00:00Z",
    "end": "2025-12-27T23:59:59Z"
  },
  "stats": {
    "total_chats": 247,
    "unique_users": 89,
    "total_messages": 1456,
    "avg_messages_per_chat": 5.9,
    "avg_chat_duration_minutes": 8.5
  }
}
```

### 7.4 Get Analytics Timeline

```http
GET /creator/assistant/{assistant_id}/analytics/timeline
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter   | Type   | Required | Description                          |
|------------|--------|----------|--------------------------------------|
| period     | string | No       | "day", "week", "month" (default: day)|
| start_date | datetime| No      | Timeline from this date              |
| end_date   | datetime| No      | Timeline until this date             |

**Response:**
```json
{
  "assistant_id": 1,
  "period": "day",
  "data": [
    {"date": "2025-12-20", "chat_count": 12, "message_count": 67},
    {"date": "2025-12-21", "chat_count": 15, "message_count": 89},
    {"date": "2025-12-22", "chat_count": 8, "message_count": 42},
    ...
  ]
}
```

---

## 8. Data Models

### 8.1 Pydantic Models (Backend)

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatSummary(BaseModel):
    id: str
    title: str
    user_id: str
    user_name: str
    user_email: str
    message_count: int
    created_at: datetime
    updated_at: datetime

class ChatListResponse(BaseModel):
    chats: List[ChatSummary]
    total: int
    page: int
    per_page: int
    total_pages: int

class ChatUser(BaseModel):
    id: str
    name: str
    email: str

class ChatMessage(BaseModel):
    id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime

class ChatDetail(BaseModel):
    id: str
    title: str
    user: ChatUser
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage]

class AnalyticsPeriod(BaseModel):
    start: datetime
    end: datetime

class AnalyticsStats(BaseModel):
    total_chats: int
    unique_users: int
    total_messages: int
    avg_messages_per_chat: float
    avg_chat_duration_minutes: Optional[float]

class AnalyticsSummaryResponse(BaseModel):
    assistant_id: int
    period: AnalyticsPeriod
    stats: AnalyticsStats

class TimelineDataPoint(BaseModel):
    date: str
    chat_count: int
    message_count: int

class AnalyticsTimelineResponse(BaseModel):
    assistant_id: int
    period: str
    data: List[TimelineDataPoint]
```

### 8.2 TypeScript Types (Frontend)

```typescript
interface ChatSummary {
  id: string;
  title: string;
  user_id: string;
  user_name: string;
  user_email: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

interface ChatListResponse {
  chats: ChatSummary[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface ChatDetail {
  id: string;
  title: string;
  user: {
    id: string;
    name: string;
    email: string;
  };
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

interface AnalyticsStats {
  total_chats: number;
  unique_users: number;
  total_messages: number;
  avg_messages_per_chat: number;
  avg_chat_duration_minutes?: number;
}

interface TimelineDataPoint {
  date: string;
  chat_count: number;
  message_count: number;
}
```

---

## 9. Questions and Considerations

### Architecture Questions

1. **Should we deprecate `/lamb/v1/OWI/*` endpoints?**
   - Current: These endpoints exist and may be used
   - Proposal: Keep for backward compatibility, mark as deprecated, use new services internally
   - **Decision needed:** Deprecation timeline?

2. **Should analytics be a separate router or part of assistant_router?**
   - Option A: `creator_interface/analytics_router.py` (new file)
   - Option B: Add to `creator_interface/assistant_router.py`
   - **Recommendation:** Option A for cleaner separation

3. **How to handle large chat history JSON parsing?**
   - OWI stores entire conversation in JSON
   - For analytics, we need to parse and count messages
   - **Consideration:** Performance with large datasets

### Security Considerations

4. **Should creators see chat content or just metadata?**
   - Option A: Full content (for quality assurance)
   - Option B: Metadata only (privacy first)
   - Option C: Configurable per organization
   - **Recommendation:** Organization setting with default to full access for assistant owners

5. **What about user privacy?**
   - Students using assistants may have privacy expectations
   - **Consideration:** Add disclosure in OWI UI that chats may be reviewed?

### Feature Scope Questions

6. **Should we support exporting chat data?**
   - CSV export for research purposes
   - **Recommendation:** Phase 2 feature

7. **Should we support chat search by content?**
   - Full-text search within messages
   - **Recommendation:** Phase 2 feature, requires FTS index

8. **Real-time updates?**
   - WebSocket for live analytics updates
   - **Recommendation:** Out of scope for v1

### Performance Considerations

9. **How to handle organizations with many chats?**
   - Pagination is implemented
   - Consider caching statistics
   - **Recommendation:** Add optional caching layer in Phase 2

10. **Index requirements on OWI database?**
    - May need to add indexes for efficient querying
    - **Concern:** We shouldn't modify OWI schema
    - **Solution:** Optimize queries, accept some performance limitations

---

## 10. Timeline and Milestones

### Estimated Total: 16-22 hours

| Phase | Task | Estimate | Priority |
|-------|------|----------|----------|
| **1** | **OWI Bridge Refactoring** | **3-4 hrs** | **High** |
| 1.1 | Create OwiBridgeService | 2 hrs | |
| 1.2 | Refactor owi_router.py | 1-2 hrs | |
| **2** | **Chat Analytics Service** | **4-6 hrs** | **High** |
| 2.1 | Create ChatAnalyticsService | 3-4 hrs | |
| 2.2 | Add DB query methods | 1-2 hrs | |
| **3** | **Creator Interface Endpoints** | **3-4 hrs** | **High** |
| 3.1 | Create analytics endpoints | 2-3 hrs | |
| 3.2 | Add authorization | 1 hr | |
| **4** | **Frontend Implementation** | **6-8 hrs** | **Medium** |
| 4.1 | Create analytics components | 4-5 hrs | |
| 4.2 | Integrate into detail view | 2-3 hrs | |

### Milestones

- **M1:** OWI Router removed (security) ✅ COMPLETED Dec 27, 2025
- **M2:** Chat analytics service created ✅ COMPLETED Dec 27, 2025
- **M3:** Creator interface endpoints deployed ✅ COMPLETED Dec 27, 2025  
- **M4:** Frontend analytics tab live ✅ COMPLETED Dec 27, 2025

---

## Appendix A: File Changes Summary

### New Files

```
backend/lamb/services/owi_bridge_service.py     # NEW
backend/lamb/services/chat_analytics_service.py # NEW
backend/creator_interface/analytics_router.py   # NEW (or extend assistant_router.py)
frontend/svelte-app/src/lib/components/analytics/ChatAnalytics.svelte      # NEW
frontend/svelte-app/src/lib/components/analytics/ChatDetailModal.svelte    # NEW
frontend/svelte-app/src/lib/components/analytics/StatsCards.svelte         # NEW
frontend/svelte-app/src/lib/services/analyticsService.js                   # NEW
```

### Modified Files

```
backend/lamb/owi_bridge/owi_router.py           # Refactor to thin layer
backend/lamb/owi_bridge/owi_database.py         # Add chat query methods
backend/creator_interface/main.py               # Mount new router
frontend/svelte-app/src/routes/assistants/+page.svelte  # Add Analytics tab
```

---

## Appendix B: Reference - openwebui-db-inspect Code

The prototype implementation provides these key patterns:

### Chat List Query
```python
query = """
    SELECT c.id, c.title, c.created_at, c.chat 
    FROM chat c 
    WHERE json_extract(c.chat, '$.models') LIKE ?
"""
```

### Model Extraction
```python
def get_unique_models():
    query = "SELECT DISTINCT json_each.value as model FROM chat, json_each(chat, '$.models')"
```

### Message Parsing
```python
chat_data = json.loads(chat_record['chat'])
messages = chat_data.get("messages", [])
# Note: OWI uses history.messages structure
messages = chat_data.get("history", {}).get("messages", {})
```

---

## Appendix C: Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| Dec 27, 2025 | Delete all `/lamb/v1/OWI/*` endpoints | Security risk - these endpoints should not be exposed |
| Dec 27, 2025 | Privacy: Organization-defined, default anonymized | Owner can access chat activity but user identifiers are anonymized by default |
| Dec 27, 2025 | Create separate `analytics_router.py` | Clean separation of concerns |
| Dec 27, 2025 | Basic features first, inspired by openwebui-db-inspect | Start with list/filter/view functionality |
| Dec 27, 2025 | Refresh on demand, no real-time | Sufficient for v1, reduces complexity |

---

**Document Status:** APPROVED - Implementation Started  
**Decisions Made:**
1. ✅ Delete OWI router endpoints (security risk)
2. ✅ Privacy: Organization-configurable, default = anonymized users
3. ✅ Create separate analytics_router.py
4. ✅ All analytics features approved, basic first
5. ✅ Refresh on demand (no WebSocket)

