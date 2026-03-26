# LAMB File Manager TFG Project Proposal


---

## 1. Project Title

**"Design and Implementation of a Secure Multi-Tenant File Management System for LAMB Educational AI Platform"**


---

## 2. Project Description

### 2.1 Context

LAMB (Learning Assistants Manager and Builder) is an open-source platform that enables educators to create, configure, and deploy AI-powered learning assistants without requiring technical expertise. The platform follows a privacy-first approach where all data remains within institutional control.

Currently, LAMB has a rudimentary file management system with significant limitations that affect user experience, security, and scalability. This project aims to design and implement a comprehensive file management system that addresses these shortcomings while introducing modern features for educational AI workflows.

### 2.2 Problem Statement

The current LAMB file management implementation presents several critical issues:

#### Current Architecture (Problematic)
```
backend/static/public/{user_id}/
    ├── uploaded_files/          # Files for single_file_rag.py processing
    │   ├── document.pdf
    │   └── notes.md
    └── img/                      # Generated images from banana_img.py connector
        ├── img_1705123456_abc123.jpg
        └── img_1705123457_def456.png
```

#### Identified Problems

1. **No User File Manager Interface**
   - Users cannot browse, organize, or manage their uploaded files
   - No visibility into storage usage or file metadata
   - Files are uploaded but essentially "forgotten" by the system

2. **No Admin/Organization File Management**
   - Organization administrators cannot view or manage member files
   - No tools for storage policy enforcement
   - No ability to clean up orphaned files

3. **Insecure URL System**
   - Static folder path is predictable (`/static/public/{user_id}/`)
   - File URLs can be guessed by enumerating user IDs
   - No access control on public file URLs
   - No expiring links or permission-based access

4. **No Quota Management**
   - Users can upload unlimited files
   - No storage limits per user or organization
   - No alerts when approaching limits
   - Potential for storage abuse

5. **Limited Multimodal Support**
   - Vision capability currently supports single image only
   - Images in chat are handled by Open WebUI, not stored in LAMB
   - No file attachment support for chat completions
   - No support for documents (PDF, text files) in conversations

---

## 3. Project Objectives

### 3.1 Primary Objectives

1. **Design a Secure File Storage Architecture**
   - Define a secure storage model with proper access control
   - Implement secure, non-guessable permalinks for file access
   - Design database schema for file metadata and permissions

2. **Implement User File Manager**
   - Create intuitive file browser interface in Svelte 5
   - Support file upload, download, rename, delete, and organize
   - Display storage usage and quota information
   - Support drag-and-drop operations

3. **Implement Admin File Management**
   - Organization-level file overview and statistics
   - User storage usage monitoring
   - Bulk file operations for administrators
   - Orphaned file detection and cleanup tools

4. **Implement Quota Management System**
   - Per-user storage quotas configurable by organization
   - Real-time quota tracking and enforcement
   - Alert system for quota warnings
   - Admin override capabilities

5. **Implement Secure Permalink System**
   - UUID-based non-guessable file URLs
   - Optional expiring links
   - Access permission validation
   - Support for public sharing with revocable links

### 3.2 Secondary Objectives

6. **Enhanced Multimodal Support**
   - Enable multiple images in vision-enabled assistants
   - Implement file attachments for chat completions
   - Support text files (txt, md, json) and documents (PDF)
   - Define storage vs. temporary pool strategy for chat files

7. **File Processing Pipeline**
   - Automatic metadata extraction
   - Thumbnail generation for images
   - File type validation and sanitization
   - Virus/malware scanning integration point

8. **Integration with Existing LAMB Features**
   - Link files to assistants (system prompt resources)
   - Connect with Knowledge Base system
   - Support for RAG processor file sources
   - Chat analytics file attachment tracking

---

## 4. Technical Requirements

### 4.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LAMB File Manager                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │  File Manager UI │  │  Admin File UI   │  │  Chat Multimodal │      │
│  │    (Svelte 5)    │  │   (Svelte 5)     │  │    UI Updates    │      │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘      │
│           │                      │                      │                │
│           └──────────────────────┼──────────────────────┘                │
│                                  │                                       │
│                                  ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                    File Manager API                            │     │
│  │                  (FastAPI Router)                              │     │
│  │                                                                 │     │
│  │  /creator/files/                                               │     │
│  │    ├── list              - List user files                     │     │
│  │    ├── upload            - Upload files                        │     │
│  │    ├── download/{id}     - Download file                       │     │
│  │    ├── delete/{id}       - Delete file                         │     │
│  │    ├── move              - Move/rename file                    │     │
│  │    ├── share/{id}        - Generate share link                 │     │
│  │    ├── quota             - Get quota status                    │     │
│  │    └── folders/          - Folder operations                   │     │
│  │                                                                 │     │
│  │  /creator/admin/files/                                         │     │
│  │    ├── stats             - Organization storage stats          │     │
│  │    ├── users/{id}/files  - User file listing (admin)          │     │
│  │    ├── quotas            - Quota management                    │     │
│  │    └── cleanup           - Orphaned file cleanup               │     │
│  │                                                                 │     │
│  │  /files/{permalink}      - Public file access (secure)         │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                  │                                       │
│                                  ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                    File Storage Layer                          │     │
│  │                                                                 │     │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │     │
│  │  │  File Metadata  │  │  Physical Store │  │  Quota Manager │ │     │
│  │  │   (SQLite)      │  │  (Filesystem)   │  │   (Service)    │ │     │
│  │  └─────────────────┘  └─────────────────┘  └────────────────┘ │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Database Schema

```sql
-- File metadata table
CREATE TABLE files (
    id TEXT PRIMARY KEY,              -- UUID
    owner_id INTEGER NOT NULL,        -- FK to Creator_users.id
    organization_id INTEGER NOT NULL, -- FK to organizations.id
    
    -- File information
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,        -- UUID-based name on disk
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    checksum TEXT,                    -- SHA-256 hash
    
    -- Organization
    folder_path TEXT DEFAULT '/',     -- Virtual folder path
    
    -- Security
    permalink TEXT UNIQUE NOT NULL,   -- Secure public access token
    is_public BOOLEAN DEFAULT FALSE,
    public_expires_at DATETIME,       -- NULL = never expires
    
    -- Metadata
    metadata JSON,                    -- Extensible metadata
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    accessed_at DATETIME,
    
    -- Source tracking
    source_type TEXT,                 -- 'upload', 'generated', 'chat_attachment'
    source_reference TEXT,            -- e.g., assistant_id, chat_id
    
    FOREIGN KEY (owner_id) REFERENCES Creator_users(id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- File shares table (for sharing with other users)
CREATE TABLE file_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    shared_with_user_id INTEGER,      -- NULL = public link
    shared_by_user_id INTEGER NOT NULL,
    permission TEXT DEFAULT 'read',   -- 'read', 'write'
    share_token TEXT UNIQUE,          -- For link-based sharing
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user_id) REFERENCES Creator_users(id),
    FOREIGN KEY (shared_by_user_id) REFERENCES Creator_users(id)
);

-- Quota configuration table
CREATE TABLE storage_quotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    user_id INTEGER,                  -- NULL = org default
    
    max_storage_bytes INTEGER NOT NULL,
    max_file_size_bytes INTEGER,
    max_files_count INTEGER,
    allowed_mime_types TEXT,          -- JSON array or NULL for all
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (user_id) REFERENCES Creator_users(id),
    UNIQUE(organization_id, user_id)
);

-- Storage usage tracking (for efficient quota queries)
CREATE TABLE storage_usage (
    user_id INTEGER PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    total_bytes INTEGER DEFAULT 0,
    file_count INTEGER DEFAULT 0,
    last_calculated DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES Creator_users(id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Chat file attachments (temporary pool)
CREATE TABLE chat_attachments (
    id TEXT PRIMARY KEY,              -- UUID
    chat_id TEXT NOT NULL,            -- OWI chat ID
    message_index INTEGER,
    file_id TEXT,                     -- FK to files (if persisted)
    
    -- For non-persisted attachments
    temp_path TEXT,
    original_name TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    
    -- Lifecycle
    is_persisted BOOLEAN DEFAULT FALSE,
    expires_at DATETIME,              -- For cleanup
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Indexes for performance
CREATE INDEX idx_files_owner ON files(owner_id);
CREATE INDEX idx_files_org ON files(organization_id);
CREATE INDEX idx_files_permalink ON files(permalink);
CREATE INDEX idx_files_folder ON files(owner_id, folder_path);
CREATE INDEX idx_file_shares_file ON file_shares(file_id);
CREATE INDEX idx_file_shares_token ON file_shares(share_token);
CREATE INDEX idx_chat_attachments_chat ON chat_attachments(chat_id);
CREATE INDEX idx_chat_attachments_expires ON chat_attachments(expires_at);
```

### 4.3 API Specification

#### User File Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/creator/files/list` | List files with pagination, filtering |
| POST | `/creator/files/upload` | Upload one or more files |
| GET | `/creator/files/{id}` | Get file metadata |
| GET | `/creator/files/{id}/download` | Download file |
| DELETE | `/creator/files/{id}` | Delete file |
| PUT | `/creator/files/{id}` | Update file metadata |
| POST | `/creator/files/{id}/move` | Move/rename file |
| POST | `/creator/files/{id}/copy` | Copy file |
| GET | `/creator/files/quota` | Get quota status |
| POST | `/creator/files/folders` | Create folder |
| DELETE | `/creator/files/folders` | Delete folder |

#### Sharing Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/creator/files/{id}/share` | Create share link |
| GET | `/creator/files/{id}/shares` | List file shares |
| DELETE | `/creator/files/{id}/shares/{share_id}` | Revoke share |
| GET | `/files/s/{token}` | Access shared file (public) |

#### Admin Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/creator/admin/files/stats` | Organization storage stats |
| GET | `/creator/admin/files/users` | Per-user storage breakdown |
| GET | `/creator/admin/files/users/{id}` | User's files (admin view) |
| PUT | `/creator/admin/quotas` | Set organization quota defaults |
| PUT | `/creator/admin/quotas/users/{id}` | Set user-specific quota |
| POST | `/creator/admin/files/cleanup` | Trigger cleanup of orphaned files |
| GET | `/creator/admin/files/orphaned` | List orphaned files |

### 4.4 Security Requirements

1. **Access Control**
   - All file operations require authentication
   - Users can only access their own files (unless shared)
   - Admin operations require admin role
   - Organization isolation enforced at data layer

2. **Secure URLs**
   - Permalink format: `/files/{uuid-v4}` (not guessable)
   - Share tokens: 32-character cryptographically random strings
   - No sequential IDs exposed in URLs

3. **File Validation**
   - MIME type validation against whitelist
   - File size limits enforced before upload completion
   - Filename sanitization (prevent path traversal)
   - Optional virus scanning hook

4. **Storage Security**
   - Files stored with UUID names (original name in database)
   - Storage path not exposed to clients
   - Serve files through application (not direct static)

### 4.5 Technology Stack

| Component | Technology | Justification |
|-----------|------------|---------------|
| Backend API | FastAPI (Python 3.11+) | Consistent with LAMB architecture |
| Database | SQLite with WAL | Consistent with LAMB, sufficient for file metadata |
| Frontend | Svelte 5, SvelteKit | Consistent with LAMB frontend |
| File Storage | Local filesystem | Simple, performant, institution-controlled |
| Styling | TailwindCSS | Consistent with LAMB frontend |

### 4.6 Frontend Components

#### File Manager View (`/files`)
```
┌─────────────────────────────────────────────────────────────────┐
│  📁 My Files                                    [Upload] [+ Folder]│
├─────────────────────────────────────────────────────────────────┤
│  Storage: ████████░░ 1.2 GB / 2 GB (60%)                        │
├─────────────────────────────────────────────────────────────────┤
│  📁 /documents/                                    ⬆️ Parent      │
├─────────────────────────────────────────────────────────────────┤
│  ☐ │ Name           │ Size    │ Modified     │ Actions         │
│────│────────────────│─────────│──────────────│─────────────────│
│  ☐ │ 📁 assignments │ --      │ Jan 15, 2026 │ ⋮               │
│  ☐ │ 📁 resources   │ --      │ Jan 10, 2026 │ ⋮               │
│  ☐ │ 📄 syllabus.pdf│ 2.3 MB  │ Jan 18, 2026 │ ⬇️ 🔗 🗑️        │
│  ☐ │ 🖼️ diagram.png │ 456 KB  │ Jan 17, 2026 │ ⬇️ 🔗 🗑️        │
│  ☐ │ 📝 notes.md    │ 12 KB   │ Jan 16, 2026 │ ⬇️ 🔗 🗑️        │
├─────────────────────────────────────────────────────────────────┤
│  ☑️ 2 selected                      [Move] [Delete] [Share]     │
└─────────────────────────────────────────────────────────────────┘
```

#### Admin Storage Dashboard
```
┌─────────────────────────────────────────────────────────────────┐
│  📊 Organization Storage Dashboard                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Total Storage: 45.2 GB / 100 GB    Files: 1,234                │
│  ████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 45%      │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Top Users by Storage:                                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ User                │ Used      │ Quota   │ Files │ %    │   │
│  │─────────────────────│───────────│─────────│───────│──────│   │
│  │ professor@upc.edu   │ 8.5 GB    │ 10 GB   │ 234   │ 85%  │   │
│  │ teacher1@upc.edu    │ 5.2 GB    │ 5 GB    │ 156   │ 104% │ ⚠️│
│  │ admin@upc.edu       │ 3.1 GB    │ 10 GB   │ 89    │ 31%  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  [Set Default Quota] [Manage User Quotas] [Cleanup Orphaned]    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Multimodal Chat Enhancement

### 5.1 Current State Analysis

Based on code analysis:

1. **Vision Support** (`simple_augment.py`):
   - Assistants with `capabilities.vision = true` support images
   - Currently handles single image via OpenAI format
   - Images passed as URLs or base64, not stored in LAMB

2. **Image Generation** (`banana_img.py`):
   - Generated images stored in `/static/public/{user_id}/img/`
   - Returns markdown with direct URL
   - No integration with file manager

3. **Open WebUI Integration**:
   - Chat images managed by OWI, not LAMB
   - No file attachment support in completions

### 5.2 Proposed Enhancements

#### Multiple Images in Vision

```python
# Enhanced message format for multiple images
{
    "role": "user",
    "content": [
        {"type": "text", "text": "Compare these two diagrams"},
        {"type": "image_url", "image_url": {"url": "file:///{file_id_1}"}},
        {"type": "image_url", "image_url": {"url": "file:///{file_id_2}"}}
    ]
}
```

#### File Attachments in Chat

```python
# New message format for file attachments
{
    "role": "user", 
    "content": [
        {"type": "text", "text": "Review this document"},
        {"type": "file", "file": {
            "id": "file_abc123",
            "name": "report.pdf",
            "mime_type": "application/pdf"
        }}
    ]
}
```

#### Storage Strategy

| File Source | Storage Strategy | Cleanup Policy |
|-------------|------------------|----------------|
| User uploaded (File Manager) | Permanent in user storage | User-managed |
| Generated images | Permanent in user storage | User-managed |
| Chat image attachment | Temporary pool | Auto-cleanup after 7 days |
| Chat file attachment | Option to persist | Auto-cleanup or persist |

### 5.3 LLM Compatibility

| File Type | Processing Strategy |
|-----------|---------------------|
| Images (jpg, png, gif, webp) | Pass to vision-capable LLM directly |
| Text files (txt, md, json) | Extract content, inject in prompt |
| PDF documents | Extract text via library, inject in prompt |
| Other | Reject or store for reference only |

---

## 6. Implementation Phases

### Phase 1: Core File Storage (Weeks 1-4)

**Deliverables:**
- [ ] Database schema implementation and migrations
- [ ] File storage service (upload, download, delete)
- [ ] Secure permalink generation and validation
- [ ] Basic quota tracking
- [ ] Unit tests for storage layer

**Key Tasks:**
1. Design and implement database schema
2. Create FileStorageManager class
3. Implement secure file upload with validation
4. Implement UUID-based storage naming
5. Create permalink system with access control
6. Write comprehensive unit tests

### Phase 2: User File Manager UI (Weeks 5-8)

**Deliverables:**
- [ ] File browser Svelte component
- [ ] File upload with drag-and-drop
- [ ] Folder navigation and management
- [ ] File operations (rename, move, delete)
- [ ] Storage quota display

**Key Tasks:**
1. Create FileManager route and layout
2. Implement FileList component with sorting/filtering
3. Build FileUploader with progress indication
4. Create FolderTree navigation component
5. Implement file preview for images and text
6. Add context menu for file operations
7. Integration tests for frontend

### Phase 3: Sharing and Permissions (Weeks 9-11)

**Deliverables:**
- [ ] Share link generation UI
- [ ] Public file access endpoint
- [ ] Share management (revoke, expiry)
- [ ] User-to-user sharing

**Key Tasks:**
1. Implement share token generation
2. Create public file access route
3. Build share management modal
4. Add sharing to file context menu
5. Implement expiry handling
6. Security audit of sharing system

### Phase 4: Admin and Quota Management (Weeks 12-14)

**Deliverables:**
- [ ] Admin storage dashboard
- [ ] Per-user file viewing (admin)
- [ ] Quota configuration UI
- [ ] Orphaned file cleanup tools
- [ ] Storage alerts system

**Key Tasks:**
1. Create admin storage overview page
2. Implement quota configuration endpoints
3. Build quota warning system
4. Create orphaned file detection
5. Implement bulk cleanup operations
6. Add storage usage reports

### Phase 5: Multimodal Enhancement (Weeks 15-18)

**Deliverables:**
- [ ] Multiple image support in vision
- [ ] File attachment in chat completions
- [ ] Temporary file pool management
- [ ] PDF/text file content extraction
- [ ] Integration with completion pipeline

**Key Tasks:**
1. Enhance simple_augment.py for multiple images
2. Implement file:// URL resolution
3. Create chat attachment handling
4. Integrate PDF text extraction
5. Build temporary pool cleanup job
6. Update OWI integration if needed

### Phase 6: Testing, Documentation, and Polish (Weeks 19-22)

**Deliverables:**
- [ ] Comprehensive test suite
- [ ] User documentation
- [ ] Admin documentation
- [ ] API documentation
- [ ] Performance optimization
- [ ] Security audit fixes

**Key Tasks:**
1. Write E2E tests with Playwright
2. Create user guide with screenshots
3. Document admin procedures
4. Generate OpenAPI documentation
5. Performance profiling and optimization
6. External security review
7. Fix identified issues

---

## 7. Success Metrics

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Users can upload files up to configured size limit | Must |
| FR-02 | Users can browse and organize files in folders | Must |
| FR-03 | Users can download their files | Must |
| FR-04 | Users can delete their files | Must |
| FR-05 | Users can generate secure share links | Must |
| FR-06 | Admins can view organization storage usage | Must |
| FR-07 | Admins can configure quotas | Must |
| FR-08 | System enforces storage quotas | Must |
| FR-09 | Permalinks are secure (non-guessable) | Must |
| FR-10 | Multiple images work in vision assistants | Should |
| FR-11 | File attachments work in chat | Should |
| FR-12 | Orphaned files can be cleaned up | Should |
| FR-13 | Share links can expire | Could |
| FR-14 | User-to-user file sharing | Could |

### Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | File upload supports files up to 100MB | 100MB |
| NFR-02 | File list loads in under 500ms | <500ms |
| NFR-03 | System handles 1000+ files per user | 1000+ |
| NFR-04 | Quota calculation is real-time accurate | <1s delay |
| NFR-05 | Test coverage for backend | >80% |
| NFR-06 | Supports all major browsers | Chrome, Firefox, Safari, Edge |

---

## 8. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Storage performance with many files | High | Medium | Implement pagination, caching, lazy loading |
| Security vulnerabilities in file handling | High | Medium | Security audit, input validation, sandboxing |
| Open WebUI integration complexity | Medium | Medium | Minimize OWI changes, use LAMB-side processing |
| Quota enforcement race conditions | Medium | Low | Database transactions, optimistic locking |
| Large file upload failures | Medium | Medium | Chunked uploads, resume capability |
| Browser compatibility issues | Low | Low | Use established libraries, progressive enhancement |

---

## 9. Dependencies

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.100+ | API framework |
| Svelte | 5.x | Frontend framework |
| python-magic | latest | MIME type detection |
| Pillow | latest | Image processing, thumbnails |
| PyPDF2 or pdfplumber | latest | PDF text extraction |
| aiofiles | latest | Async file operations |

### Internal Dependencies

| Component | Dependency Type | Notes |
|-----------|-----------------|-------|
| Authentication system | Required | Reuse existing token validation |
| Database migrations | Required | Add new tables |
| Organization config | Required | For quota defaults |
| Completion pipeline | Required | For multimodal integration |

---

## 10. Estimated Effort

| Phase | Duration | Effort (hours) |
|-------|----------|----------------|
| Phase 1: Core File Storage | 4 weeks | 80 |
| Phase 2: User File Manager UI | 4 weeks | 80 |
| Phase 3: Sharing and Permissions | 3 weeks | 60 |
| Phase 4: Admin and Quota Management | 3 weeks | 60 |
| Phase 5: Multimodal Enhancement | 4 weeks | 80 |
| Phase 6: Testing and Documentation | 4 weeks | 80 |
| **Total** | **22 weeks** | **440 hours** |

Additional time for:
- Project management and meetings: 40 hours
- Research and learning: 30 hours
- Final presentation and defense: 30 hours

**Total Estimated Effort: 540 hours** (aligned with TFG credits)

---

## 11. Deliverables

### Code Deliverables

1. **Backend Module:** `backend/lamb/file_manager/`
   - `file_storage.py` - Core storage service
   - `quota_manager.py` - Quota tracking and enforcement
   - `share_manager.py` - Sharing functionality
   - `file_router.py` - API endpoints

2. **Frontend Module:** `frontend/svelte-app/src/routes/files/`
   - `+page.svelte` - Main file manager view
   - `components/` - Reusable components

3. **Admin Module:** Extension to existing admin routes

4. **Database Migrations:** New tables and indexes

5. **Tests:** Unit, integration, and E2E tests

### Documentation Deliverables

1. **Technical Documentation**
   - Architecture design document
   - API reference (OpenAPI)
   - Database schema documentation

2. **User Documentation**
   - File manager user guide
   - Admin guide for storage management

3. **Project Documentation**
   - TFG memory (required format)
   - Presentation slides
   - Demo video

---

## 12. References

### LAMB Documentation
- [LAMB Architecture v2](../lamb_architecture_v2.md)
- [LAMB PRD](../prd.md)
- [Chat Analytics Project](../chat_analytics_project.md)

### Technical References
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Svelte 5 Documentation: https://svelte.dev/docs
- OpenAI Vision API: https://platform.openai.com/docs/guides/vision
- SQLite Documentation: https://www.sqlite.org/docs.html

### Security References
- OWASP File Upload Security: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- CWE-434: Unrestricted Upload of File with Dangerous Type

---

## 13. Appendix

### A. Current Code References

**Current file upload implementation:**
- `backend/creator_interface/main.py` - `/creator/files/upload` endpoint
- `backend/lamb/completions/rag/single_file_rag.py` - File-based RAG processor
- `backend/lamb/completions/connectors/banana_img.py` - Image generation storage

**Current multimodal handling:**
- `backend/lamb/completions/pps/simple_augment.py` - Vision capability check
- `backend/lamb/completions/connectors/openai.py` - Multimodal message handling

### B. Glossary

| Term | Definition |
|------|------------|
| LAMB | Learning Assistants Manager and Builder |
| OWI | Open WebUI - Chat interface component |
| RAG | Retrieval-Augmented Generation |
| TFG | Treball de Fi de Grau (Final Degree Project) |
| Permalink | Permanent link - secure URL for file access |
| Quota | Storage limit assigned to user/organization |

---


