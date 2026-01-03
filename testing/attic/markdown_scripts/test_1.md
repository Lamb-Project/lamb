# LAMB Application Quality Control Test - Test 1

## Overview

This document provides detailed test cases for verifying the core functionality of the LAMB (Learning Assistants Manager and Builder) application. These tests should be performed to ensure the application is working correctly and can be used for quality control validation.

## Prerequisites

### Environment Setup
- LAMB application running at `http://localhost:9099`
- Backend API accessible
- Database properly initialized
- All required services running (OWI, knowledge base server, etc.)

### Required Information
- Default signup secret key: `pepino-secret-key` (from backend config)
- Test user credentials will be created during testing

## Test Case Overview

This test suite contains **12 test cases** organized into two main categories:

### **Core Application Testing (Test Cases 1-8)**
1. **Application Access and Initial Load** - Verifies basic application startup, UI components, and initial page rendering
2. **User Account Creation (Signup)** - Tests new user registration process with form validation and i18n support
3. **User Authentication (Login)** - Validates user login functionality, session creation, and navigation updates
4. **Learning Assistants Access** - Verifies authenticated access to assistant management interface
5. **Assistant Creation** - Tests complete assistant creation workflow with configuration options
6. **Assistant List Management** - Validates assistant listing, filtering, and management operations
7. **Navigation and Session Management** - Tests application navigation, tab switching, and state persistence
8. **Logout Functionality** - Verifies secure logout process and session cleanup

### **Internationalization Testing (Test Cases 9-12)**
9. **Language Selector Functionality** - Tests language switching across all 4 supported languages (EN/ES/CA/EU)
10. **Translation Completeness and Consistency** - Validates all UI elements have proper translations
11. **Mixed Content Detection** - Identifies and reports any untranslated content (literal translation keys)
12. **Language-Specific Content Handling** - Tests language-specific formatting, layout, and user experience

### **Testing Focus Areas**
- **Authentication & Authorization**: User registration, login, session management
- **Core Functionality**: Assistant creation, management, and configuration
- **User Interface**: Navigation, form handling, error messaging
- **Internationalization**: Multi-language support across English, Spanish, Catalan, and Basque
- **Data Validation**: Form validation, error handling, data persistence
- **Performance**: Page load times, operation responsiveness, session stability

## Test Cases

### Test Case 1: Application Access and Initial Load

**Objective:** Verify the application loads correctly and displays the login page.

**Steps:**
1. Navigate to `http://localhost:9099`
2. Wait for page to fully load

**Expected Results:**
- Page loads without errors
- LAMB logo and branding visible
- Login form displayed with:
  - Email input field
  - Password input field  
  - "Login" button
  - "Sign up" link at bottom
- Navigation bar shows:
  - Home (active)
  - Learning Assistants (disabled)
  - Knowledge Bases (disabled)
  - MCP Testing (disabled)
- Version "v0.1" displayed
- Application tagline: "Learning Assistants Manager and Builder"

**Console Check:** 
- No critical JavaScript errors
- i18n setup messages present
- Configuration loading messages present

---

### Test Case 2: User Account Creation (Signup)

**Objective:** Verify new user accounts can be created successfully.

**Steps:**
1. Click the "Sign up" button/link
2. Fill in the signup form:
   - **Name:** `Assistant`
   - **Email:** `assistant@example.com`
   - **Password:** `password123`
   - **Secret Key:** `pepino-secret-key`
3. Click "Sign Up" button

**Expected Results:**
- Form switches to signup view with heading "Sign Up"
- All form fields accept input correctly
- Success message appears: "Account created successfully"
- Form automatically switches back to login view
- No error messages displayed

**Error Scenarios:**
- **Wrong Secret Key:** Should display "Invalid secret key" error
- **Missing Fields:** Should show appropriate validation messages
- **Duplicate Email:** Should show user already exists error

---

### Test Case 3: User Authentication (Login)

**Objective:** Verify user can log in with created credentials.

**Steps:**
1. On login form, enter:
   - **Email:** `assistant@example.com`
   - **Password:** `password123`
2. Click "Login" button

**Expected Results:**
- Successful login occurs
- Page remains at root URL (`/`)
- Navigation changes:
  - All navigation links become active (clickable)
  - User profile area appears in top-right showing:
    - User name: "Assistant"
    - "OpenWebUI" link
    - "Logout" button
- Main content area shows:
  - "No news to display." message
  - "View Learning Assistants" link
- Console shows authentication success messages

**Error Scenarios:**
- **Wrong Credentials:** Should display "Invalid credentials" error
- **Empty Fields:** Should show validation messages

---

### Test Case 4: Learning Assistants Access

**Objective:** Verify authenticated users can access the Learning Assistants section.

**Steps:**
1. Click on "Learning Assistants" in navigation OR click "View Learning Assistants" link
2. Verify page loads correctly

**Expected Results:**
- URL changes to `/assistants`
- Page heading: "Learning Assistants"
- Tab navigation shows:
  - "My Assistants" (active)
  - "Create Assistant" (clickable)
- Initially shows: "You don't have any assistants yet"
- Console shows assistant loading messages
- No JavaScript errors

---

### Test Case 5: Assistant Creation

**Objective:** Verify new learning assistants can be created successfully.

**Steps:**
1. Click "Create Assistant" tab
2. Fill in the form with valid data:
   - **Name:** `Test-Learning-Assistant` (no spaces, use hyphens/underscores only)
   - **Description:** `A test assistant for learning and educational purposes`
   - **System Prompt:** `You are a learning assistant that helps students learn about specific topics. Use the provided context to answer user questions in a helpful and educational manner.`
   - Leave other fields as defaults
3. Click "Save" button

**Expected Results:**
- URL changes to `/assistants?view=create`
- Form loads with all required fields
- Default system prompt provided (in Spanish initially)
- Configuration options available:
  - Language Model dropdown (GPT-4o-mini, GPT-4o)
  - RAG Processor options (Simple RAG, No RAG, Single File RAG)
  - Advanced Mode checkbox
- After clicking Save:
  - Success message or redirect to assistant list
  - New assistant appears in list with:
    - Name: "3_Test-Learning-Assistant" (prefixed)
    - Status: "Unpublished"
    - Description matches input
    - Configuration details shown
    - Action buttons: View, Duplicate, Export JSON, Delete

**Error Scenarios:**
- **Invalid Name:** Names with spaces should show error: "Assistant name can only contain letters, numbers, underscores and hyphens. No spaces or special characters allowed."
- **Missing Required Fields:** Should show validation errors

---

### Test Case 6: Assistant List Management

**Objective:** Verify assistants are properly listed and managed.

**Steps:**
1. Return to "My Assistants" tab
2. Verify the created assistant is displayed
3. Check all action buttons are present

**Expected Results:**
- Assistant table displays with columns:
  - Name (with publish status)
  - Description  
  - Actions (with ID)
- Created assistant shows:
  - Name: "3_Test-Learning-Assistant"
  - Status: "Unpublished"
  - Description: "A test assistant for learning and educational purposes"
  - ID: 1 (or incremented number)
- Technical details row shows:
  - Prompt Processor: simple_augment
  - Connector: openai
  - LLM: gpt-4o-mini
  - RAG Processor: no_rag
- Action buttons present:
  - View (eye icon)
  - Duplicate (copy icon)
  - Export JSON (download icon)
  - Delete (trash icon)

---

### Test Case 7: Navigation and Session Management

**Objective:** Verify navigation works correctly and user session is maintained.

**Steps:**
1. Navigate between different sections:
   - Click "Home" 
   - Click "Learning Assistants"
   - Click "Knowledge Bases"
   - Click "MCP Testing"
2. Verify user remains logged in
3. Check OpenWebUI link functionality

**Expected Results:**
- All navigation links are functional
- User profile remains visible in all sections
- Session persists across navigation
- OpenWebUI link contains proper authentication token
- Each section has appropriate content (even if placeholder)

---

### Test Case 8: Logout Functionality

**Objective:** Verify user can log out successfully.

**Steps:**
1. Click "Logout" button in user profile area
2. Verify logout behavior

**Expected Results:**
- User is logged out
- Page returns to login state
- Navigation links become disabled again
- User profile area disappears
- Session is cleared

---

## Performance and Technical Verification

### Console Output Verification

**Expected Console Messages (Normal Operation):**
- i18n setup and locale loading messages
- Configuration loading messages (`LAMB_CONFIG` found)
- Assistant loading messages
- API call logs with curl command equivalents
- No critical errors

**Error Indicators to Watch For:**
- 404 errors for missing resources
- Authentication failures (401/403)
- JavaScript runtime errors
- Failed API calls

### Network Requests

**Expected API Calls:**
- `POST /creator/signup` (during signup)
- `POST /creator/login` (during login)  
- `GET /creator/assistant/get_assistants` (loading assistants)
- `POST /creator/assistant/create` (creating assistant)
- Various configuration and capability requests

### Database Verification

After successful test completion, verify:
- User created in Creator_users table
- Corresponding OWI user created
- Assistant created with correct configuration
- All foreign key relationships intact

## Test Data Cleanup

After testing, optionally clean up test data:
- Delete created assistant
- Remove test user account
- Reset any modified configurations

## Automation Notes

This test suite can be automated using:
- Playwright for browser automation
- API testing tools for backend verification
- Database queries for data validation

## Known Issues and Workarounds

1. **Assistant Name Validation:** Names cannot contain spaces - use hyphens or underscores
2. **Language Display:** Some interface elements may show in Spanish initially
3. **Console Warnings:** Autocomplete warnings for password fields are expected and harmless

## Language Consistency Testing (i18n)

### Supported Languages
LAMB supports the following languages:
- **English (en)** - Default/fallback language
- **Spanish (es)** - Español
- **Catalan (ca)** - Català 
- **Basque (eu)** - Euskera

### Test Case 9: Language Selector Functionality

**Objective:** Verify the language selector works correctly and switches interface language.

**Steps:**
1. Locate the language selector button (shows current language, e.g., "EN")
2. Click the language selector button
3. Select each available language (Spanish, Catalan, Basque)
4. Verify the interface updates to the selected language
5. Test language persistence across page reloads

**Expected Results:**
- Language selector displays current language
- Dropdown shows all 4 supported languages: EN, ES, CA, EU
- Interface text updates immediately upon language selection
- Language preference persists across browser sessions
- Navigation, buttons, and form labels translate correctly
- No mixed language content in the same view

---

### Test Case 10: Translation Completeness and Consistency

**Objective:** Verify translations are complete and consistent across different sections.

**Steps:**
1. Switch to Spanish (ES) and navigate through all sections:
   - Home page (check news content and navigation)
   - Login/Signup forms (check all form labels and messages)
   - Learning Assistants page (check table headers, buttons, status messages)
   - Knowledge Bases page (check error messages, UI text)
   - MCP Testing page (check interface elements)
2. Repeat for Catalan (CA) and Basque (EU)
3. Check for untranslated text (text still appearing in English)
4. Verify translation consistency (same terms translated the same way)

**Expected Results for Spanish (ES):**
- Navigation: "Inicio", "Asistentes de Aprendizaje", "Bases de Conocimiento", "Pruebas MCP"
- Login form: "Iniciar Sesión", "Correo Electrónico", "Contraseña", "Registrarse"
- Assistant page: "Asistentes de Aprendizaje", "Mis Asistentes", "Crear Asistente"
- Buttons: "Editar", "Duplicar", "Eliminar", "Publicar"
- Status messages: "Publicado", "No Publicado"

**Expected Results for Catalan (CA):**
- Navigation: "Inici", "Assistents d'Aprenentatge", "Bases de Coneixement", "Proves MCP"
- Login form: "Iniciar Sessió", "Correu Electrònic", "Contrasenya", "Registrar-se"
- Assistant page: "Assistents d'Aprenentatge", "Els Meus Assistents", "Crear Assistent"
- Buttons: "Editar", "Duplicar", "Eliminar", "Publicar"
- Status messages: "Publicat", "No Publicat"

**Expected Results for Basque (EU):**
- All interface elements should be translated to Basque
- Consistent terminology usage throughout the application
- No English fallback text visible in production interface

---

### Test Case 11: Mixed Content Detection

**Objective:** Identify and verify handling of mixed language content.

**Steps:**
1. Switch to Spanish and check for any English text remaining
2. Pay special attention to:
   - Error messages and validation text
   - Dynamically loaded content (news, notifications)
   - Placeholder text in forms
   - Tooltip text and help messages
   - System prompts and templates (may be intentionally in Spanish)
3. Check console for any i18n loading errors or missing translation warnings

**Expected Results:**
- No English text in Spanish interface (except where intentionally mixed)
- System prompts may legitimately be in Spanish even when interface is in English
- Error messages display in the selected interface language
- All user-facing text respects the language selection

---

### Test Case 12: Language-Specific Content Handling

**Objective:** Verify language-specific content is handled correctly.

**Steps:**
1. Test assistant creation with different languages selected
2. Verify system prompts are provided in appropriate languages
3. Check if default templates change based on selected language
4. Test error messages during form validation in different languages

**Expected Results:**
- Default system prompts provided in the interface language
- Error messages appear in the selected language
- Form placeholders and hints respect language selection
- Date/time formatting may be locale-appropriate (if implemented)

---

## Test Case 13: LLM Conversation Preservation Verification

**Objective:** Verify that the LLM connection preserves full conversation history and enhances current user input with RAG context.

**Prerequisites:**
1. Create a test user account using signup secret "pepino-secret-key"
2. Create and publish a test assistant with RAG enabled
3. Have access to backend API endpoints

**Steps:**
1. **User Account Creation:**
   - Navigate to `http://localhost:9099`
   - Click "Sign up" button
   - Fill form with:
     - Name: `Test User`
     - Email: `test@example.com`
     - Password: `password123`
     - Secret Key: `pepino-secret-key`
   - Click "Sign Up" and verify account creation

2. **User Authentication:**
   - Login with credentials from step 1
   - Verify navigation becomes active and user profile appears

3. **Assistant Creation:**
   - Navigate to "Learning Assistants" → "Create Assistant"
   - Fill form:
     - Name: `Test-Conversation`
     - Description: `A test assistant for verifying conversation preservation`
     - Keep default system prompt and template
     - Set RAG Processor to "Simple Rag" (if KB server available)
   - Click "Save" to create assistant

4. **Assistant Publishing:**
   - In assistant list, click "View" for the created assistant
   - Click "Publish" button to make assistant available

5. **Conversation Preservation Testing:**

   **Method A: Direct API Testing (Recommended)**
   Use curl commands to test conversation preservation:

   ```bash
   # First message - establish context
   curl -X POST "http://localhost:9099/lamb/v1/completions/" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -d '{
       "assistant": 2,
       "messages": [
         {"role": "user", "content": "My name is John and I am learning about machine learning."}
       ],
       "stream": false
     }'

   # Second message - test context preservation
   curl -X POST "http://localhost:9099/lamb/v1/completions/" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -d '{
       "assistant": 2,
       "messages": [
         {"role": "user", "content": "My name is John and I am learning about machine learning."},
         {"role": "assistant", "content": "Hello John! Machine learning is a fascinating field..."},
         {"role": "user", "content": "What specific topics should I focus on?"}
       ],
       "stream": false
     }'
   ```

   **Method B: Browser-based Testing (if Chat interface available)**
   - Navigate to assistant detail view
   - Click "Chat" button
   - Send multiple messages and verify context is maintained
   - Check that responses reference previous conversation elements

**Expected Results:**
- **Full Conversation History Preserved:** LLM receives complete message history including system prompt, previous user messages, and assistant responses
- **Current Input Enhancement:** Latest user message is enhanced via prompt template with `{user_input}` placeholder
- **RAG Context Integration:** If RAG is enabled, relevant context is inserted via `{context}` placeholder
- **Contextual Responses:** Assistant responses should reference and build upon previous conversation elements
- **Proper Message Flow:** System prompt → Previous conversation → Enhanced current input → LLM processing

**Technical Verification:**
- Check that `llm_connect()` in `openai.py` receives full `messages` array
- Verify `simple_augment.py` preserves all previous messages
- Confirm RAG context (if enabled) is properly inserted into prompt template
- Validate that OpenAI API receives complete conversation context

**Console/Debug Verification:**
- Backend logs should show complete message arrays being processed
- OpenAI API calls should include full conversation history
- RAG queries (if enabled) should use last user message as search query
- Response processing should maintain conversation continuity

**Error Scenarios:**
- **Missing Authentication:** Should return 401 Unauthorized
- **Invalid Assistant ID:** Should return 404 Not Found
- **RAG Server Unavailable:** Should fallback gracefully with empty context
- **OpenAI API Errors:** Should be properly handled and logged

**Performance Expectations:**
- Response times should be reasonable (< 30 seconds for complex queries)
- Memory usage should remain stable across multiple conversation turns
- No memory leaks in conversation state management

---

### Language Testing Performance Verification

**Console Monitoring for i18n:**
- i18n initialization messages: "Initializing svelte-i18n with initial locale: [locale]"
- Locale loading confirmations: "Locale set to: [locale]"
- No missing translation warnings
- No i18n loading errors

**Network Requests for Language Files:**
- Verify locale JSON files are loaded when language changes
- Check for efficient caching of language resources
- Ensure no unnecessary re-fetching of already loaded languages

### Language Testing Known Issues

1. **News Content:** May appear in Spanish even when interface is in other languages (content-specific)
2. **System Prompts:** Intentionally multilingual - Spanish prompts are expected
3. **OpenWebUI Integration:** May have different language support than LAMB core
4. **MCP Server Names:** Technical names may remain in English across all languages

---

## Success Criteria

All test cases should pass with:
- No critical errors in console
- All expected UI elements present and functional
- Proper data persistence
- Correct user session management
- Appropriate error handling for invalid inputs
- **Complete language consistency in selected language**
- **No mixed language content in user interface**
- **Language preference persistence across sessions**
- **All 4 supported languages functional and complete**

---

**Document Version:** 1.1  
**Last Updated:** January 2025  
**Based on Testing:** LAMB v0.1 application testing on localhost:9099  
**i18n Support:** English (en), Spanish (es), Catalan (ca), Basque (eu)