# LAMB Project Release Notes - End User Guide

**Period:** October 2025 - January 2026  
**Document Version:** 1.0  
**Last Updated:** January 13, 2026

---

## Welcome!

This document summarizes all the new features, improvements, and changes in LAMB that affect your daily experience. Whether you're an educator creating AI assistants, an administrator managing users, or an end user chatting with assistants, you'll find relevant information here.

---

## Table of Contents

1. [What's New - Feature Highlights](#1-whats-new---feature-highlights)
2. [Assistant Creation & Management](#2-assistant-creation--management)
3. [Knowledge Base Enhancements](#3-knowledge-base-enhancements)
4. [User & Organization Management](#4-user--organization-management)
5. [Chat & Interaction Improvements](#5-chat--interaction-improvements)
6. [Interface & Navigation Updates](#6-interface--navigation-updates)
7. [Version History](#7-version-history)

---

## 1. What's New - Feature Highlights

### 🌟 LAMB Evaluaitor - Assessment Rubrics System
**Available since:** October 2025

Create and manage assessment rubrics that can be integrated with your AI assistants for consistent, criteria-based feedback.

**What you can do:**
- Create custom rubrics with multiple criteria and scoring levels
- Share rubrics with colleagues in your organization
- Attach rubrics to assistants for assessment-focused conversations
- Use showcase templates as starting points

**How to access:** Navigate to **Sources of Knowledge → Rubrics** in the main menu.

---

### 🌟 Prompt Templates
**Available since:** October 2025 | Issue #72

Save your favorite assistant configurations as reusable templates.

**What you can do:**
- Save system prompts and configurations as templates
- Share templates with your organization
- Quickly apply templates when creating new assistants
- Duplicate and modify existing templates
- Export/import templates for backup

**How to access:** Go to **Learning Assistants** and click the **Prompt Templates** tab.

---

### 🌟 Chat Analytics Dashboard
**Available since:** December 2025 | Issue #64

Monitor how your assistants are being used with the new analytics feature.

**What you can do:**
- View usage statistics for your assistants
- Track conversation counts and patterns
- Analyze assistant performance

**How to access:** Go to **Learning Assistants**, select an assistant, and click the **Activity** tab.

---

### 🌟 Knowledge Base Sharing
**Available since:** October 2025 | Issue #83

Share your Knowledge Bases with colleagues while maintaining ownership.

**What you can do:**
- Toggle sharing on/off for your Knowledge Bases
- Access shared KBs from colleagues in your organization
- Use shared KBs in your own assistants (read-only)

**How to access:** Go to **Sources of Knowledge → Knowledge Bases** and click the **Share** button in the Actions column for your KB.

---

### 🌟 Assistant Sharing (Restored)
**Available since:** January 2026 | Issue #193

Share assistants with specific users or groups in your organization.

**What you can do:**
- Share assistants with other users
- Control who can access your assistants
- Use the Share tab in assistant details

**How to access:** Open an assistant and use the **Share** tab.

---

### 🌟 Vision/Multimodal Support - Send Images to AI
**Available since:** December 2025 | Issue #123

Create assistants that can understand and analyze images you send them.

**What you can do:**
- Send images to vision-capable assistants
- Get AI analysis of photos, diagrams, documents
- Use with GPT-4o, GPT-4 Vision, and other vision models

**How to use:**
1. Create an assistant with a vision-capable model (e.g., gpt-4o)
2. In the chat, click the image attachment button
3. Upload or paste an image
4. Ask questions about the image

**Use Cases:**
- Analyze diagrams or charts
- Get feedback on student work (photos of handwriting)
- Describe images for accessibility
- Extract text from images

---

### 🌟 AI Image Generation with Gemini
**Available since:** December 2025 | PR #145

Create assistants that generate images using Google Gemini models.

**What you can do:**
- **Text-to-Image:** Describe what you want, get an AI-generated image
- **Image-to-Image:** Upload an image and ask the AI to modify it
- Support for multiple aspect ratios and output formats

**How to create an Image Generation Assistant:**
1. Go to **Learning Assistants** → **+ Create Assistant**
2. In **Configuration**, set:
   - **Connector:** `Gemini Image (banana_img)`
   - **Model:** Select a Gemini image model (e.g., `gemini-2.5-flash-image-preview`)
3. Save and publish

**Image-to-Image Example:**
1. Open your image generation assistant
2. Upload a photo
3. Type: "Make this image look like a watercolor painting"
4. The AI will generate a modified version

**Note:** Requires Google API key configured by your administrator.

---

## 2. Assistant Creation & Management

### New Features

| Feature | Description | When Added |
|---------|-------------|------------|
| **Rubric RAG Integration** | Attach rubrics to assistants for assessment feedback | Oct 2025 |
| **Vision/Multimodal Support** | Send images to assistants and get AI analysis | Dec 2025 |
| **AI Image Generation** | Create assistants that generate images with Gemini | Dec 2025 |
| **Image-to-Image** | Modify images using AI (style transfer, edits) | Dec 2025 |
| **Creation/Update Dates** | See when assistants were created and last modified | Nov 2025 |
| **Global Model Configuration** | Organizations can set default models for all assistants | Dec 2025 |

### Improvements

- **LLM Selection Bug Fixed** (Issue #62) - You can now reliably change the model of an assistant
- **RAG Processor Editing** (Issue #35, #155) - RAG settings properly restore when editing
- **System Prompt Updates** (Issue #122) - System prompts now save correctly when editing
- **Graceful Failures** (Issue #55) - Better error messages when assistants encounter issues
- **Description Updates Sync** (Issue #109) - Changes to descriptions now sync to Open WebUI

### How to Create an Assistant with Rubric

1. Go to **Learning Assistants** → click **+ Create Assistant** tab
2. Fill in name and description
3. In the **Configuration** section, select **Rubric Rag** from the **RAG Processor** dropdown
4. Choose a rubric from your library or shared rubrics
5. Select format (Markdown or JSON)
6. Complete other settings and save

---

## 3. Knowledge Base Enhancements

### New Features

| Feature | Description | When Added |
|---------|-------------|------------|
| **Organization-specific KB Servers** | Each organization can have its own KB server | Nov 2025 |
| **URL Ingestion (Firecrawl)** | Ingest web pages directly into Knowledge Bases | Dec 2025 |
| **YouTube Smart Filenames** | YouTube videos get meaningful filenames | Nov 2025 |
| **PDF Image Extraction** | PDFs are processed with image extraction | Jan 2026 |
| **Processing Statistics** | See detailed stats during file ingestion | Jan 2026 |
| **Enhanced File Upload** | Better feedback during upload with debouncing | Dec 2025 |

### Improvements

- **Upload Feedback** (Issue #126) - Better visibility of upload progress on small screens
- **KB Name Validation** (Issue #15) - Client-side validation prevents invalid names
- **Connection Testing** - Test KB server connection from settings panel
- **File Deletion** (Issue #16) - Delete individual files from Knowledge Bases
- **Shared KB Permissions** - Clear indicators when viewing shared (read-only) KBs

### How to Ingest a Web URL

1. Open a Knowledge Base
2. Go to the **Ingest** tab
3. Select **URL** as the source
4. Enter the web URL
5. Click **Ingest** - Firecrawl will extract and process the content

---

## 4. User & Organization Management

### For Administrators

| Feature | Description | When Added |
|---------|-------------|------------|
| **User Blocking** | Disable users without deleting them | Oct 2025 |
| **Bulk User Import** | Import multiple users at once (Org Admins) | Nov 2025 |
| **User Deletion with Checks** | Safe deletion with dependency warnings | Dec 2025 |
| **Organization Migration** | Move users between organizations | Oct 2025 |
| **Bulk Operations** | Enable/disable multiple users at once | Oct 2025 |

### New User Types

| Type | Description | Access |
|------|-------------|--------|
| **Creator** | Full access to create and manage assistants | Creator Interface |
| **End User** | Chat-only access, redirects to Open WebUI | Open WebUI only |

### For Organization Admins

- **Simplified Organization Creation** (Issue #102)
- **Role Management** - Assign org-admin roles to users
- **API Configuration** - Configure API keys and models per organization
- **Signup Key Validation** - Clear feedback on signup key requirements

### Improvements

- **Client-side Filtering** (Issue #84) - Filter, sort, and paginate user lists
- **Fixed "Organization 'list' not found"** (Issue #39)
- **Fixed server error when disabling users** (Issue #40)
- **Better Loading States** - Smoother experience when loading data

---

## 5. Chat & Interaction Improvements

### New Features

| Feature | Description | When Added |
|---------|-------------|------------|
| **Markdown Rendering Toggle** | Enable/disable markdown in chat responses | Dec 2025 |
| **Image Support** | Send and view images in chat (with capable models) | Dec 2025 |
| **Internal Chat Persistence** | Chat history saved within LAMB | Dec 2025 |
| **Context-Aware RAG** | Assistants can use full conversation context | Dec 2025 |

### LTI Integration (Moodle)

- **Fixed OAuth Issues** (Issue #70) - LTI authentication works reliably
- **Non-admin Login** (Issue #26) - Regular users can log in without LTI
- **Improved Error Handling** - Better messages when LTI fails
- **X-Forwarded-Prefix Support** - Works correctly behind reverse proxies

---

## 6. Interface & Navigation Updates

### Visual Improvements (Version 0.3)

- **Navigation Fixes** - Menu reorganization for better workflow
- **News Caching** - Dynamic news system with language support
- **Brand Colors** - Consistent blue color throughout
- **Wider Forms** - 80% wider prompt template forms
- **Removed Blank Spaces** - Cleaner org-admin interface

### Settings Page

- **API Status Overview** - Fixed disappearing after refresh (Issue #91)
- **Loading States** - Clear indicators when loading configurations
- **API Key Security** - Keys are no longer exposed in responses
- **Google Gemini Support** - Configure Gemini API keys

### Accessibility

- **Screen Reader Improvements** - Better a11y across the interface
- **Text Colors Fixed** - Visible text in all input fields
- **Confirmation Modals** - Clear confirmations before destructive actions

### Version Information

You can now see the current LAMB version in the footer and navigation, helping you know which features are available.

---

## 7. Version History

### Version 0.3 (January 2026)
- Assistant Sharing restored
- Moodle LTI integration tests
- LangSmith tracing integration
- API key security fix
- Enhanced KB server availability checks
- Chat Analytics feature
- UI/UX improvements
- **Vision/Multimodal Support** - Send images to AI assistants
- **AI Image Generation** - Create images with Gemini (text-to-image)
- **Image-to-Image Generation** - Modify images with AI prompts
- News caching system
- Internal chat persistence
- Multimodal support
- Context-aware RAG

### Version 0.2 (October-November 2025)
- LAMB Evaluaitor (Rubrics)
- Prompt Templates
- Knowledge Base Sharing
- User Blocking feature
- End User type
- Organization migration
- Client-side filtering

---

## Issues Resolved (User-Facing)

| Issue # | Problem | Status |
|---------|---------|--------|
| #193 | Share assistant missing | ✅ Fixed |
| #189 | API config UX issues | ✅ Fixed |
| #170 | User interface updates | ✅ Complete |
| #168 | Hardcoded API keys | ✅ Fixed |
| #155 | Cannot change RAG Processor | ✅ Fixed |
| #126 | Upload feedback off-screen | ✅ Fixed |
| #123 | Multimodality/Vision support | ✅ Complete |
| #122 | System prompt not updating | ✅ Fixed |
| #109 | Description not syncing to OWI | ✅ Fixed |
| #106 | Missing markdown in chat | ✅ Fixed |
| #91 | Settings disappearing | ✅ Fixed |
| #86 | Signup key validation | ✅ Fixed |
| #84 | No filtering in lists | ✅ Fixed |
| #83 | KB sharing | ✅ Complete |
| #81 | User blocking | ✅ Complete |
| #77 | UI refactoring | ✅ Complete |
| #72 | Prompt templates | ✅ Complete |
| #70 | LTI OAuth failing | ✅ Fixed |
| #62 | Cannot change model | ✅ Fixed |
| #55 | Assistant failures | ✅ Fixed |
| #53 | User deletion | ✅ Complete |
| #50 | Infinite loading | ✅ Fixed |
| #45 | Table columns hidden | ✅ Fixed |
| #40 | Error disabling users | ✅ Fixed |

---

## Getting Help

If you encounter any issues or have questions:

1. Check the [LAMB Documentation](./README.md)
2. Visit the [GitHub Issues](https://github.com/Lamb-Project/lamb/issues)
3. Contact your organization administrator

---

**Thank you for using LAMB!**

