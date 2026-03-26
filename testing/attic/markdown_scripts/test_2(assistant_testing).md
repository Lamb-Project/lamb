# LAMB Application Quality Control Test - Test 2 (Assistant Testing)

## Overview

This document provides detailed test cases for verifying the assistant management and editing functionality of the LAMB (Learning Assistants Manager and Builder) application. These tests focus on the assistant detail view, editing capabilities, and configuration management.

## Prerequisites

### Environment Setup
- LAMB application running at `http://localhost:9099`
- User logged in with valid credentials
- At least one assistant created (from Test 1 or manually)
- Backend API accessible
- All required services running

### Required Information
- Test user credentials: `assistant@example.com` / `password123`
- Existing assistant for testing (e.g., "test_1" or "3_Test-Learning-Assistant")

## Test Case Overview

This test suite contains **15 test cases** organized into two main categories:

### **Assistant Management Testing (Test Cases 1-10)**
1. **Assistant Detail View Access** - Verifies navigation to assistant detail pages and proper information display
2. **Assistant Properties View** - Tests the Properties tab functionality and configuration visibility
3. **Assistant Edit Mode Access** - Validates access to assistant editing interface from detail view
4. **Assistant Information Editing** - Tests modification of basic assistant information (name, description)
5. **Prompt Template Management** - Verifies system prompt and prompt template editing capabilities
6. **Configuration Panel Management** - Tests advanced configuration options (LLM, connectors, processors)
7. **Description Auto-Generation** - Validates automated description generation from system prompts
8. **Chat Interface Access** - Tests direct chat functionality from assistant detail view
9. **Tab Navigation and Data Persistence** - Verifies seamless switching between Properties and Chat tabs
10. **Assistant Detail URL Handling** - Tests direct URL access and navigation to specific assistants

### **Assistant Interface i18n Testing (Test Cases 11-15)**
11. **Assistant Interface Language Switching** - Tests language switching within assistant management interface
12. **Assistant-Specific Translation Completeness** - Validates translations for all assistant-related UI elements
13. **Prompt Template Language Handling** - Tests multilingual support for prompt templates and system prompts
14. **Assistant Status and Action Translation** - Verifies proper translation of status indicators and action buttons
15. **Chat Interface Language Consistency** - Tests language consistency in assistant chat interactions

### **Testing Focus Areas**
- **Assistant Detail Navigation**: URL handling, tab switching, data persistence
- **Configuration Management**: Form editing, validation, advanced options, auto-generation
- **Data Integrity**: Save operations, field validation, configuration persistence
- **User Interface**: Tab functionality, button interactions, form responsiveness
- **Chat Integration**: Direct assistant interaction, response handling, session management
- **Internationalization**: Multi-language support for assistant-specific interfaces
- **Error Handling**: Invalid configurations, network failures, validation messages
- **Advanced Features**: Description generation, configuration complexity, template management

## Test Cases

### Test Case 1: Assistant Detail View Access

**Objective:** Verify users can access the assistant detail view and see all expected information.

**Steps:**
1. Navigate to Learning Assistants (`/assistants`)
2. Click on an existing assistant name to access detail view
3. Verify the detail page loads correctly

**Expected Results:**
- URL changes to `/assistants?view=detail&id=[assistant_id]` or similar
- Page shows "Detalle del Asistente" (Assistant Detail) tab as active
- Assistant ID is displayed (e.g., "Assistant Details (ID: 2)")
- Three main tabs visible:
  - "Properties" (Propiedades)
  - "Edit" 
  - "Chat with [assistant_name]"
- Assistant information displayed correctly
- No JavaScript errors in console

---

### Test Case 2: Assistant Properties View

**Objective:** Verify the assistant properties are displayed correctly in read-only mode.

**Steps:**
1. From the assistant detail view, ensure "Properties" tab is selected
2. Review all displayed information
3. Verify configuration details are shown

**Expected Results:**
- Assistant name displayed correctly
- Description shown (if available)
- System prompt visible in Spanish:
  - "Eres un asistente de aprendizaje que ayuda a los estudiantes a aprender sobre un tema específico. Utiliza el contexto para responder las preguntas del usuario."
- Configuration panel shows:
  - Prompt Processor: simple_augment
  - Connector: openai
  - Language Model (LLM): gpt-4o-mini
  - RAG Processor: No Rag (or configured option)
- All information is read-only in Properties view

---

### Test Case 3: Assistant Edit Mode Access

**Objective:** Verify users can access the assistant editing interface.

**Steps:**
1. From the assistant detail view, click the "Edit" tab
2. Verify the edit interface loads correctly
3. Check all form fields are accessible

**Expected Results:**
- "Edit" tab becomes active
- Page shows "Edit Assistant" heading
- Form displays with editable fields:
  - Name field (with current name, e.g., "test_1")
  - Description field with placeholder "A brief summary of the assistant"
  - System Prompt text area with current prompt
  - Prompt Template section
- Configuration panel remains visible on the right
- "Generate" button available next to description
- Placeholder insertion buttons available:
  - `--- {context} ---`
  - `--- {user_input} ---`

---

### Test Case 4: Assistant Information Editing

**Objective:** Verify users can edit basic assistant information.

**Steps:**
1. In Edit mode, modify the assistant name
2. Update the description field
3. Modify the system prompt
4. Save changes (if save button available)

**Expected Results:**
- Name field accepts text input (following naming conventions)
- Description field accepts text input
- System prompt text area accepts multi-line text
- Changes are reflected in real-time or after saving
- No validation errors for valid inputs
- Form validation works for invalid inputs (spaces in name, etc.)

**Error Scenarios:**
- **Invalid Name:** Names with spaces should show appropriate validation
- **Empty Required Fields:** Should show validation messages

---

### Test Case 5: Prompt Template Management

**Objective:** Verify the prompt template functionality and placeholder insertion.

**Steps:**
1. In Edit mode, locate the Prompt Template section
2. Test the placeholder insertion buttons:
   - Click `--- {context} ---` button
   - Click `--- {user_input} ---` button
3. Verify the template updates correctly
4. Test manual editing of the template

**Expected Results:**
- Prompt Template section shows current template
- Template includes system prompt text
- Context placeholder insertion works: "Este es el contexto: --- {context} ---"
- User input placeholder insertion works: "Ahora responde la pregunta del usuario: --- {user_input} ---"
- Manual editing of template is possible
- Template maintains proper formatting
- Placeholders are clearly marked and functional

---

### Test Case 6: Configuration Panel Management

**Objective:** Verify the configuration options can be viewed and modified.

**Steps:**
1. In Edit mode, review the Configuration panel
2. Test dropdown menus for each configuration option:
   - Prompt Processor
   - Connector
   - Language Model (LLM)
   - RAG Processor
3. Make configuration changes and verify they're reflected

**Expected Results:**
- Configuration panel shows current settings
- Dropdowns are functional:
  - Prompt Processor: simple_augment and other options
  - Connector: openai and other available connectors
  - Language Model: gpt-4o-mini, gpt-4o, and other models
  - RAG Processor: No Rag, Simple RAG, Single File RAG options
- Changes update the assistant configuration
- Configuration is preserved when switching between tabs

---

### Test Case 7: Description Auto-Generation

**Objective:** Verify the description generation functionality.

**Steps:**
1. In Edit mode, ensure name and system prompt are filled
2. Click the "Generate" button next to the description field
3. Verify description generation works

**Expected Results:**
- Generate button is functional
- Description field is populated automatically based on name and prompt
- Generated description is relevant and coherent
- User can still manually edit the generated description
- Generate function works multiple times

**Note:** This may require API connectivity and may not work if description generation service is offline

---

### Test Case 8: Chat Interface Access

**Objective:** Verify users can access the chat interface for testing the assistant.

**Steps:**
1. From the assistant detail view, click "Chat with [assistant_name]" tab
2. Verify the chat interface loads
3. Test basic chat functionality

**Expected Results:**
- "Chat with [assistant_name]" tab becomes active
- Chat interface loads without errors
- Chat input field is available
- Assistant configuration is applied in chat
- Messages can be sent and received (if backend is functional)

---

### Test Case 9: Tab Navigation and Data Persistence

**Objective:** Verify navigation between tabs maintains data and state.

**Steps:**
1. Start in Edit mode and make some changes
2. Switch to Properties tab
3. Switch to Chat tab
4. Return to Edit tab
5. Verify data persistence

**Expected Results:**
- Tab switching works smoothly
- Unsaved changes in Edit mode are preserved when switching tabs
- Properties tab shows updated information
- Chat tab maintains separate state
- No data loss during navigation
- No JavaScript errors during tab switches

---

### Test Case 10: Assistant Detail URL Handling

**Objective:** Verify direct URL access and browser navigation work correctly.

**Steps:**
1. Note the URL when viewing an assistant detail
2. Copy the URL and open in a new tab/window
3. Test browser back/forward navigation
4. Test refresh functionality

**Expected Results:**
- Direct URL access loads the correct assistant detail view
- URL parameters correctly identify the assistant
- Browser back/forward navigation works
- Page refresh maintains current state
- Deep linking to specific tabs works (if implemented)

---

## Performance and Technical Verification

### Console Output Verification

**Expected Console Messages:**
- Assistant loading messages
- Configuration loading confirmations
- API calls for assistant data retrieval
- No critical JavaScript errors
- Tab switching events logged

**Error Indicators to Watch For:**
- 404 errors for missing assistants
- Configuration loading failures
- Save operation errors
- Chat functionality errors

### Network Requests

**Expected API Calls:**
- `GET /creator/assistant/get_assistant?id=[id]` (loading assistant details)
- `PUT /creator/assistant/update` (saving changes)
- `POST /creator/assistant/generate_description` (description generation)
- Configuration and capability requests

### UI Responsiveness

**Verify:**
- Form fields respond quickly to input
- Tab switches are smooth
- Configuration dropdowns load promptly
- No UI freezing during operations

## Test Data Requirements

### Test Assistant Specifications
- **Name:** test_1 or similar
- **Description:** Brief descriptive text
- **System Prompt:** Spanish learning assistant prompt
- **Configuration:** 
  - Prompt Processor: simple_augment
  - Connector: openai
  - LLM: gpt-4o-mini
  - RAG: No Rag

## Known Issues and Workarounds

1. **Language Display:** Interface shows Spanish text in some areas (system prompts, templates)
2. **Description Generation:** May require external API connectivity
3. **Chat Functionality:** Depends on backend LLM connectivity
4. **Auto-Save:** Verify if changes auto-save or require manual save action

## Language Consistency Testing for Assistant Interface (i18n)

### Supported Languages in Assistant Interface
The assistant editing interface supports all 4 LAMB languages:
- **English (en)** - Default language
- **Spanish (es)** - Includes assistant-specific terminology
- **Catalan (ca)** - Complete assistant interface translation  
- **Basque (eu)** - Full assistant management support

---

### Test Case 11: Assistant Interface Language Switching

**Objective:** Verify language switching works correctly in the assistant detail and editing interface.

**Steps:**
1. Navigate to an assistant detail view
2. Switch to Spanish (ES) using the language selector
3. Verify all interface elements update:
   - Tab labels: "Propiedades", "Editar", "Chat con [nombre_asistente]"
   - Form labels and placeholders
   - Configuration panel labels
   - Button text
4. Repeat for Catalan (CA) and Basque (EU)
5. Test language persistence when navigating between assistant tabs

**Expected Results for Spanish:**
- Tab titles: "Propiedades", "Editar", "Chat con test_1"
- Form fields: "Nombre del Asistente", "Descripción", "Prompt del Sistema"
- Configuration labels: "Procesador de Prompt", "Conector", "LLM", "Procesador RAG"
- Buttons: "Generar", "Guardar", "Cancelar"
- Placeholder text: "Breve resumen del asistente", "Define el rol y objetivo del asistente..."

**Expected Results for Catalan:**
- Tab titles: "Propietats", "Editar", "Chat amb test_1"
- Form fields: "Nom de l'Assistent", "Descripció", "Prompt del Sistema"
- Configuration labels: "Processador de Prompt", "Connector", "LLM", "Processador RAG"
- Buttons: "Generar", "Desar", "Cancel·lar"

---

### Test Case 12: Assistant-Specific Translation Completeness

**Objective:** Verify all assistant-specific terminology is properly translated.

**Steps:**
1. In Spanish interface, check translation of:
   - "Detalles del Asistente (ID: X)"
   - Configuration dropdown options
   - Validation error messages
   - Success/failure notifications
   - Prompt template placeholder text
2. Test form validation errors in each language
3. Verify technical terms are consistently translated:
   - "simple_augment" (may remain technical)
   - "openai" (brand name, may remain unchanged)
   - "gpt-4o-mini" (model names, may remain unchanged)
   - "No Rag" vs "No RAG" consistency

**Expected Results:**
- Consistent terminology across all assistant interface elements
- Technical/brand names appropriately handled (may remain in English)
- Error messages in selected language
- Dropdown options translated where appropriate

---

### Test Case 13: Prompt Template Language Handling

**Objective:** Verify language handling in prompt templates and system prompts.

**Steps:**
1. Switch to different languages and check:
   - Default system prompt language
   - Prompt template structure text
   - Placeholder insertion button labels
   - Context and user input placeholder text
2. Test creating new assistants in different languages
3. Verify existing assistant prompts display correctly regardless of interface language

**Expected Results:**
- System prompts may be in Spanish by default (educational context)
- Placeholder insertion buttons show in interface language:
  - Spanish: "Insertar marcador", "--- {contexto} ---", "--- {entrada_usuario} ---"
  - Catalan: "Inserir marcador", "--- {context} ---", "--- {entrada_usuari} ---"
- Template instruction text respects interface language

---

### Test Case 14: Assistant Status and Action Translation

**Objective:** Verify assistant status indicators and action buttons are properly translated.

**Steps:**
1. Check status indicators in different languages:
   - "Published" / "Unpublished" states
   - "Loading assistants..." messages
   - "No assistants found" states
2. Test action button translations:
   - Edit, Duplicate, Export, Delete buttons
   - Modal dialog buttons (Save, Cancel, Confirm)
3. Verify confirmation dialog translations

**Expected Results for Spanish:**
- Status: "Publicado" / "No Publicado"
- Actions: "Editar", "Duplicar", "Exportar JSON", "Eliminar"
- Loading: "Cargando asistentes..."
- Confirmations: "¿Estás seguro de que quieres eliminar este asistente?"

**Expected Results for Catalan:**
- Status: "Publicat" / "No Publicat"
- Actions: "Editar", "Duplicar", "Exportar JSON", "Eliminar"
- Loading: "Carregant assistents..."
- Confirmations: "Estàs segur que vols eliminar aquest assistent?"

---

### Test Case 15: Chat Interface Language Consistency

**Objective:** Verify the "Chat with assistant" tab respects language settings.

**Steps:**
1. Access the chat tab in different languages
2. Check interface elements:
   - Tab title shows assistant name correctly
   - Chat input placeholder text
   - Send button text
   - Loading states and error messages
3. Test chat functionality with different interface languages

**Expected Results:**
- Tab title: "Chat con test_1" (ES), "Chat amb test_1" (CA)
- Chat interface elements translated appropriately
- Assistant responses may be in configured language (depends on system prompt)
- Interface controls (send, clear, etc.) in selected language

---

### Assistant Interface i18n Performance Verification

**Console Monitoring:**
- No missing translation warnings for assistant-specific keys
- Proper loading of assistant interface translations
- No console errors when switching languages in edit mode

**Network Efficiency:**
- Language resources cached effectively
- No unnecessary re-fetching when navigating between assistant tabs
- Smooth language switching without interface flickering

### Assistant Interface i18n Known Issues

1. **System Prompts:** Default prompts are in Spanish for educational context
2. **Technical Terms:** Model names (gpt-4o-mini) and some technical terms may remain in English
3. **Mixed Content:** Assistant names and user-generated content may be in different languages than interface
4. **OpenWebUI Integration:** Chat functionality may have different i18n support

---

## Success Criteria

All test cases should pass with:
- No critical errors in console
- All UI elements functional and accessible
- Proper data persistence across tab navigation
- Correct assistant configuration management
- Functional editing capabilities
- Proper validation and error handling
- **Complete translation of assistant interface elements**
- **Consistent language use across Properties, Edit, and Chat tabs**
- **Proper handling of multilingual assistant content**
- **Language switching without data loss in edit mode**

---

**Document Version:** 1.1  
**Last Updated:** January 2025  
**Based on Testing:** LAMB v0.1 assistant detail and editing interface  
**Screenshot Reference:** Assistant editing interface with ID: 2, showing Properties/Edit/Chat tabs  
**i18n Support:** Full support for English (en), Spanish (es), Catalan (ca), Basque (eu)