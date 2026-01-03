# LAMB Application Quality Control Test - Test 3 (Advanced Assistant Operations)

## Overview

This document provides detailed test cases for verifying advanced assistant operations and workflows in the LAMB (Learning Assistants Manager and Builder) application. These tests focus on assistant lifecycle management, import/export functionality, publishing workflows, and advanced chat interactions.

## Prerequisites

### Environment Setup
- LAMB application running at `http://localhost:9099`
- User logged in with valid credentials
- At least one test assistant available (from Test 1 or Test 2)
- Backend API accessible with all services running
- OpenWebUI integration functional
- File system access for import/export operations

### Required Information
- Test user credentials: `assistant@example.com` / `password123`
- Existing test assistant (e.g., "Test-Learning-Assistant")
- Sample JSON files for import testing
- Access to file download verification

## Test Case Overview

This test suite contains **13 test cases** organized into four main categories:

### **Advanced Operations Testing (Test Cases 1-5)**
1. **Advanced Chat Interface Functionality** - Tests comprehensive chat functionality with conversation flow and session management
2. **JSON Export Functionality** - Verifies assistants can be exported to JSON format with complete configuration data
3. **Assistant Duplication Functionality** - Tests assistant duplication with proper naming and configuration inheritance
3A. **Complete Export-Import Workflow** - Verifies round-trip functionality of exporting and importing assistants
4. **Assistant Publishing Workflow** - Tests publishing and unpublishing functionality for OpenWebUI integration
5. **Assistant Deletion Workflow** - Verifies secure deletion with proper confirmations and cleanup

### **Workflow and Configuration Testing (Test Cases 6-10)**
6. **Publishing Status Workflow Verification** - Tests publishing functionality from detail view and OpenWebUI integration
7. **Advanced Configuration Mode Testing** - Verifies Advanced Mode toggle and additional configuration options
8. **Assistant Configuration Edge Cases** - Tests complex configurations, special characters, and maximum length inputs
9. **Assistant Performance and Stress Testing** - Verifies performance under various load conditions and concurrent operations
10. **Integration and Workflow Testing** - Tests complete workflows combining multiple assistant operations

### **OpenWebUI Integration Testing (Test Cases 11-12)**
11. **OpenWebUI Interface Access and Integration** - Verifies OpenWebUI chatbot interface integration with user assistants in model dropdown
12. **OpenWebUI Cross-Language Integration Testing** - Tests OpenWebUI integration across all LAMB language interfaces

### **Advanced i18n Testing (Test Case 13)**
13. **Advanced i18n for Assistant Operations** - Verifies all advanced operations work correctly across all 4 supported languages

### **Testing Focus Areas**
- **Lifecycle Management**: Complete assistant lifecycle from creation to deletion
- **Data Import/Export**: JSON export/import functionality with full configuration fidelity
- **Publishing Integration**: OpenWebUI synchronization and authentication token handling
- **OpenWebUI Interface**: Chatbot interface access, model dropdown verification, assistant functionality
- **Authentication Integration**: SSO token handling and session persistence across platforms
- **Model Synchronization**: Assistant availability and configuration consistency between LAMB and OpenWebUI
- **Advanced Configuration**: Complex settings, edge cases, and configuration validation
- **Performance Testing**: Load conditions, concurrent operations, memory management
- **File Operations**: Export downloads, import validation, file format handling
- **Workflow Integration**: Multi-step operations and state consistency
- **Error Handling**: Validation failures, network issues, data corruption recovery
- **Internationalization**: Multi-language support for advanced operations and OpenWebUI integration
- **Security**: Deletion confirmations, data protection, permission validation

### **Key Features Tested**
- **Chat Interface**: Advanced chat functionality with conversation persistence
- **Export/Import**: Complete configuration round-trip with data validation
- **Duplication**: Independent assistant copies with proper naming conventions
- **Publishing**: OpenWebUI integration and status synchronization
- **OpenWebUI Access**: Seamless interface access with authentication token integration
- **Model Dropdown**: User assistant availability and naming consistency in OpenWebUI
- **Cross-Platform Chat**: Assistant functionality verification across LAMB and OpenWebUI interfaces
- **Session Management**: Authentication persistence and token synchronization
- **Deletion**: Secure removal with confirmation dialogs
- **Advanced Mode**: Complex configuration options and validation
- **Edge Cases**: Special characters, maximum lengths, complex templates
- **Performance**: Stress testing and concurrent operation handling

## Test Cases

### Test Case 1: Advanced Chat Interface Functionality

**Objective:** Verify comprehensive chat functionality with assistant including conversation flow, response quality, and session management.

**Steps:**
1. Navigate to an assistant detail view
2. Click "Chat with [assistant_name]" tab
3. Verify chat interface components load correctly
4. Send multiple test messages:
   - Simple question: "What is machine learning?"
   - Follow-up question: "Can you give me an example?"
   - Complex query: "Explain the difference between supervised and unsupervised learning"
   - Empty message (test validation)
5. Test conversation history and scrolling
6. Test chat session persistence across tab switches
7. Verify response formatting and readability

**Expected Results:**
- Chat interface loads without errors ✅
- Input field accepts text and validates empty submissions ✅
- Messages display in proper conversation format ✅
- Assistant responses are contextually relevant ✅
- Conversation history is maintained ✅
- Timestamps and message indicators are present ✅
- Chat session persists when switching between tabs ✅
- Scroll functionality works for long conversations ✅

**Performance Criteria:**
- Response time under 10 seconds for standard queries
- No memory leaks in extended chat sessions
- Proper handling of concurrent messages

---

### Test Case 2: JSON Export Functionality

**Objective:** Verify assistants can be exported to JSON format with complete configuration data.

**Steps:**
1. Navigate to Learning Assistants list
2. Locate a test assistant
3. Click "Export JSON" button for the assistant
4. Verify download initiation
5. Check downloaded file:
   - File format is valid JSON
   - Contains all assistant configuration
   - Includes metadata (name, description, prompts)
   - Contains technical configuration (LLM, connectors, etc.)
6. Test export from assistant detail view
7. Compare exported data with displayed configuration

**Expected Results:**
- Export button triggers immediate download ✅
- Downloaded file has correct naming convention ✅
- JSON structure is valid and parseable ✅
- All assistant data is preserved in export ✅
- File contains complete configuration:
  - Basic info: name, description, system_prompt ✅
  - Technical config: llm_model, connector, rag_processor ✅
  - Template and processing information ✅
- Export works from both list and detail views ✅
- File size is reasonable (< 50KB for standard assistant) ✅

**Data Verification:**
```json
{
  "name": "Test-Learning-Assistant",
  "description": "...",
  "system_prompt": "...",
  "prompt_template": "...",
  "config": {
    "llm_model": "gpt-4o-mini",
    "connector": "openai",
    "prompt_processor": "simple_augment",
    "rag_processor": "no_rag"
  }
}
```

---

### Test Case 3: Assistant Duplication Functionality

**Objective:** Verify assistants can be duplicated with proper naming and configuration inheritance.

**Steps:**
1. From assistants list, click "Duplicate" button on existing assistant
2. Verify duplication dialog/process
3. Check if new assistant is created with:
   - Modified name (e.g., "Copy of [original_name]" or incremented number)
   - Identical configuration to original
   - Independent ID and status
4. Test duplication from assistant detail view
5. Verify original assistant is unchanged
6. Test editing duplicated assistant independently

**Expected Results:**
- Duplication process completes successfully ✅
- New assistant appears in list with modified name ✅
- All configuration copied correctly:
  - System prompt identical ✅
  - Prompt template identical ✅
  - LLM and connector settings preserved ✅
  - RAG processor settings maintained ✅
- New assistant has unique ID ✅
- Original assistant remains unchanged ✅
- Duplicated assistant starts as "Unpublished" ✅
- Both assistants can be edited independently ✅

**Naming Convention Verification:**
- Original: "Test-Learning-Assistant"
- Duplicate: "Copy_of_Test-Learning-Assistant" or "Test-Learning-Assistant_2"

---

### Test Case 3A: Complete Export-Import Workflow

**Objective:** Verify the complete round-trip functionality of exporting an assistant and importing it as a new assistant to ensure full data fidelity.

**Steps:**

**Phase 1: Export Existing Assistant**
1. Navigate to assistants list view
2. Select an existing assistant with complex configuration:
   - Must have system prompt and prompt template
   - Should include RAG processor settings (if available)
   - Should have advanced configuration options
3. Click "Export JSON" button for the selected assistant
4. Verify JSON file downloads successfully with correct naming
5. Locate and inspect the downloaded JSON file:
   - Verify file is valid JSON format
   - Check all expected fields are present
   - Note the configuration details for comparison

**Phase 2: Import Assistant via Create Form**
1. Navigate to "Create Assistant" tab
2. Locate and click "Import from JSON" button in form header
3. Select the previously exported JSON file from file chooser
4. Verify import validation process:
   - Check console for validation messages
   - Ensure no critical validation errors
   - Confirm form population occurs automatically

**Phase 3: Verification and Configuration**
1. Review auto-populated form fields:
   - **Name field:** Should match original (may need modification)
   - **Description:** Should be identical to original
   - **System Prompt:** Must match original exactly
   - **Prompt Template:** Must match original exactly
   - **Configuration Settings:** Verify dropdowns are set correctly
   - **RAG Settings:** Confirm RAG processor and related fields
2. Modify assistant name to avoid conflicts (e.g., "Imported_[Original_Name]")
3. Verify all configuration dropdowns show correct selections
4. Check that Advanced Mode is properly configured if needed

**Phase 4: Save and Compare**
1. Save the imported assistant using the "Save" button
2. Verify successful creation message
3. Navigate back to assistants list
4. Compare original and imported assistants:
   - **Side-by-side comparison** of technical details
   - **Configuration row verification** (Prompt Processor, Connector, LLM, RAG Processor)
   - **Status verification** (both should be "Unpublished")

**Phase 5: Functional Testing**
1. Test both assistants in chat mode to verify identical behavior
2. Verify both assistants operate independently:
   - Edit one assistant without affecting the other
   - Publish/unpublish status should be independent
   - Deletion of one should not affect the other

**Phase 6: Edge Case Testing**
1. Test importing with different language interface:
   - Switch to Spanish/Catalan/Basque and repeat import
   - Verify translations work correctly throughout process
2. Test error handling:
   - Import a corrupted JSON file (invalid JSON syntax)
   - Import a JSON file missing required fields
   - Import a JSON file with invalid configuration values
3. Test with complex configurations:
   - Assistant with knowledge base selections
   - Assistant with single file RAG configuration
   - Assistant with advanced prompt processor settings

**Expected Results:**
- Export generates complete, valid JSON file within 5 seconds ✅
- JSON file contains all configuration data ✅
- Import validation passes for valid exported file ✅
- Form auto-population completes within 3 seconds ✅
- All configuration fields populate correctly and accurately ✅
- Assistant name conflict handling works appropriately ✅
- Imported assistant saves successfully ✅
- Round-trip maintains 100% fidelity of configuration ✅
- Both assistants function identically in chat mode ✅
- Both assistants operate independently without interference ✅
- Language interface changes don't affect import functionality ✅
- Error handling provides clear feedback for invalid files ✅
- No data corruption or loss during export-import cycle ✅

**Performance Benchmarks:**
- Export operation: < 5 seconds
- File download: < 2 seconds  
- Import validation: < 3 seconds
- Form population: < 2 seconds
- Save operation: < 5 seconds

**Data Integrity Verification:**
```json
Original vs Imported Configuration Comparison:
{
  "name": "Test-Assistant" vs "Imported_Test-Assistant",
  "description": "[identical]",
  "system_prompt": "[identical]", 
  "prompt_template": "[identical]",
  "api_callback": {
    "prompt_processor": "[identical]",
    "connector": "[identical]", 
    "llm": "[identical]",
    "rag_processor": "[identical]"
  },
  "RAG_Top_k": "[identical]",
  "RAG_collections": "[identical]"
}
```

---

### Test Case 4: Assistant Publishing Workflow

**Objective:** Verify the publishing and unpublishing functionality for assistants.

**Steps:**
1. Select an unpublished assistant
2. Click "Publish" button
3. Verify status change and any confirmations
4. Check published assistant behavior:
   - Status indicator changes
   - Assistant becomes available in OpenWebUI
   - Any restrictions or changes in editing
5. Test unpublishing process:
   - Click publish button again (toggle behavior)
   - Or find unpublish option
   - Verify status reverts to unpublished
6. Test publishing workflow in different languages
7. Verify publishing permissions and restrictions

**Expected Results:**
- Publish button changes assistant status to "Published" ✅
- Status indicator updates immediately ✅
- Published assistant integration with OpenWebUI works ✅
- Publishing confirmation/success message appears ✅
- Unpublishing process works correctly ✅
- Status changes are persistent across page reloads ✅
- Publishing state affects assistant availability ✅
- No data loss during publish/unpublish cycles ✅

**Integration Verification:**
- Published assistant appears in OpenWebUI assistant list
- Unpublished assistant is hidden from OpenWebUI
- Configuration changes require republishing (if applicable)

---

### Test Case 5: Assistant Deletion Workflow

**Objective:** Verify secure deletion of assistants with proper confirmations and cleanup.

**Steps:**
1. Navigate to assistant list
2. Click "Delete" button on a test assistant
3. Verify deletion confirmation dialog appears
4. Test cancellation of deletion
5. Confirm deletion and verify:
   - Assistant removed from list
   - No orphaned data remains
   - Operation cannot be undone
6. Test deletion from assistant detail view
7. Verify deletion of published vs unpublished assistants
8. Test deletion with proper error handling

**Expected Results:**
- Delete button triggers confirmation dialog ✅
- Confirmation dialog clearly explains consequences ✅
- Cancellation preserves assistant without changes ✅
- Successful deletion removes assistant from list ✅
- Deletion is permanent (no undo functionality) ✅
- No orphaned database entries remain ✅
- Published assistants require additional confirmation ✅
- Error handling for deletion failures works ✅

**Security Verification:**
- Deletion requires explicit confirmation
- No accidental deletions possible
- Published assistants have additional protection
- Operation logs are maintained (if applicable)

---

### Test Case 6: Publishing Status Workflow Verification

**Objective:** Verify publishing functionality is properly integrated and accessible only from the detail view.

**Steps:**
1. Navigate to assistant list view
2. Verify NO publish button exists in list view (only: View, Duplicate, Export JSON, Delete)
3. Click on assistant name to access detail view
4. Navigate to Properties tab
5. Verify Publish button is available alongside: Edit, Duplicate, Export, Delete
6. Test publish button functionality:
   - Click Publish button
   - Verify status change from "Unpublished" to "Published"
   - Check if button changes to "Unpublish" or similar
7. Test published assistant integration with OpenWebUI
8. Return to list view and verify status display changes

**Expected Results:**
- NO publish functionality in list view ✅
- Publish button ONLY available in detail view Properties tab ✅
- Publishing changes status immediately ✅
- Status change persists across page navigation ✅
- Published assistant available in OpenWebUI ✅
- List view reflects publishing status correctly ✅
- Unpublishing functionality works (if available) ✅

**Integration Verification:**
- Published assistant synchronizes with OpenWebUI
- Authentication token included in OpenWebUI link
- Publishing status affects assistant availability in external systems

---

### Test Case 7: Advanced Configuration Mode Testing

**Objective:** Verify the Advanced Mode toggle provides additional configuration options correctly.

**Steps:**
1. Navigate to Create Assistant form
2. Verify initial state shows simplified configuration:
   - Only LLM Model and RAG Processor dropdowns visible
   - Advanced Mode checkbox unchecked
3. Click "Advanced Mode" checkbox to enable
4. Verify additional configuration options appear:
   - Prompt Processor dropdown
   - Connector dropdown (bypass, llm, openai, ollama)
5. Test all configuration combinations:
   - Different Prompt Processors
   - Various Connectors
   - Multiple LLM models
   - Different RAG processors
6. Verify configuration persistence when toggling modes
7. Test configuration validation and constraints
8. Create assistant with advanced configuration and verify settings are saved

**Expected Results:**
- Advanced Mode toggle works smoothly ✅
- Additional dropdowns appear when enabled ✅
- All configuration combinations are valid ✅
- Configuration persists when switching modes ✅
- Created assistant preserves advanced settings ✅
- Default values are appropriate for each mode ✅
- No conflicts between configuration options ✅

**Configuration Options Verification:**
- Prompt Processors: simple_augment (and others if available)
- Connectors: bypass, llm, openai, ollama
- LLM Models: gpt-4o-mini, gpt-4o
- RAG Processors: Simple Rag, No Rag, Single File Rag

---

### Test Case 8: Assistant Configuration Edge Cases

**Objective:** Verify robust handling of complex and edge-case assistant configurations.

**Steps:**
1. Test maximum length inputs:
   - Very long assistant names (approaching limits)
   - Extremely long descriptions (1000+ characters)
   - Complex system prompts with special characters
2. Test special character handling:
   - Unicode characters in names and descriptions
   - Emojis and symbols
   - Multilingual text in prompts
3. Test configuration combinations:
   - All available LLM models
   - Different connector types
   - Various RAG processor configurations
4. Test template complexity:
   - Multiple placeholders
   - Nested templates
   - Complex formatting

**Expected Results:**
- Character limits are enforced gracefully ✅
- Special characters are preserved correctly ✅
- All LLM/connector combinations work ✅
- Complex templates are processed accurately ✅
- Error messages for invalid configurations are clear ✅
- Unicode and multilingual content is supported ✅
- Configuration validation prevents invalid states ✅

**Data Integrity Verification:**
- Special characters survive export/import cycles
- Configuration changes are saved correctly
- Template placeholders are processed properly

---

### Test Case 9: Assistant Performance and Stress Testing

**Objective:** Verify assistant operations perform well under various load conditions.

**Steps:**
1. Test rapid operations:
   - Quick successive exports
   - Rapid creation and deletion cycles
   - Fast language switching during operations
2. Test large data handling:
   - Assistants with very long system prompts
   - Complex prompt templates
   - Large conversation histories in chat
3. Test concurrent operations:
   - Multiple browser tabs with same assistant
   - Simultaneous editing and chatting
   - Multiple users if available
4. Test memory and resource usage:
   - Extended chat sessions
   - Multiple assistants open simultaneously
   - Long-running browser sessions

**Expected Results:**
- Rapid operations don't cause conflicts ✅
- Large data is handled efficiently ✅
- Concurrent operations are synchronized properly ✅
- Memory usage remains stable ✅
- No degradation over extended sessions ✅
- Error recovery works for failed operations ✅

**Performance Benchmarks:**
- Chat responses under 10 seconds
- Export operations under 5 seconds
- Page loads under 3 seconds
- No memory leaks over 1-hour sessions

---

### Test Case 10: Integration and Workflow Testing

**Objective:** Verify complete workflows combining multiple assistant operations.

**Steps:**
1. Complete assistant lifecycle (available functionality):
   - Create → Edit → Publish → Chat → Export → Delete
2. Test assistant sharing workflow:
   - Export assistant to JSON file
   - Verify exported file contains complete configuration
   - Manual recreation from exported configuration (since import not available)
3. Test OpenWebUI integration workflow:
   - Publish assistant and verify in OpenWebUI
   - Test assistant functionality in OpenWebUI chat
   - Verify authentication token synchronization
   - Test assistant responses match LAMB configuration
4. Test duplication workflow:
   - Duplicate existing assistant
   - Modify duplicated assistant independently
   - Verify original remains unchanged

**Expected Results:**
- Complete available lifecycle works without data loss ✅
- Export captures all necessary configuration data ✅
- Manual recreation from export is feasible ✅
- OpenWebUI integration is seamless ✅
- Published assistants work correctly in OpenWebUI ✅
- Duplication creates truly independent copies ✅
- Workflows are intuitive within available functionality ✅

---

### Test Case 11: OpenWebUI Interface Access and Integration

**Objective:** Verify the OpenWebUI chatbot interface integration works correctly with user assistants appearing in model dropdown and functioning properly.

**Steps:**

**Phase 1: OpenWebUI Interface Access**
1. From LAMB application (logged in), locate the "OpenWebUI" button/link in the user profile area
2. Click the OpenWebUI button to open the chatbot interface
3. Verify OpenWebUI interface loads correctly:
   - Interface opens in new tab/window
   - Authentication token is properly included in URL
   - User session is authenticated automatically
   - No login required (seamless SSO)

**Phase 2: Model Dropdown Verification**
1. In OpenWebUI interface, locate the model selection dropdown
2. Click the model dropdown to view available models
3. Verify ALL user's assistants from LAMB appear in dropdown:
   - Count total assistants in LAMB vs OpenWebUI dropdown
   - Check assistant names match exactly (including prefixes like "3_")
   - Verify only PUBLISHED assistants appear (unpublished should be hidden)
   - Confirm model naming convention follows: `lamb_assistant.{id}` format

**Phase 3: Assistant Functionality Testing**
1. Select first assistant from dropdown (e.g., "lamb_assistant.7")
2. Send test message: "Hello, please introduce yourself"
3. Verify assistant responds correctly:
   - Response matches assistant's configured system prompt
   - Response time under 10 seconds
   - Message format is proper chat format
4. Test conversation continuity:
   - Send follow-up question: "What can you help me with?"
   - Verify assistant maintains context from system prompt
   - Check response quality and relevance

**Phase 4: Multiple Assistants Testing**
1. Switch to second assistant in dropdown
2. Send same test message: "Hello, please introduce yourself"
3. Compare response differences:
   - Different assistants should have distinct responses
   - Responses should reflect individual assistant configurations
   - No conversation bleed between different assistants
4. Test switching between assistants:
   - Start conversation with Assistant A
   - Switch to Assistant B mid-conversation
   - Verify conversation history is separate

**Phase 5: Configuration Consistency Verification**
1. Return to LAMB interface (original tab)
2. Check assistant configurations in LAMB detail view
3. Compare with OpenWebUI behavior:
   - Assistant responses should match configured system prompts
   - LLM model settings should be consistent (gpt-4o-mini vs gpt-4o)
   - RAG processor settings should affect responses appropriately
4. Test published vs unpublished status:
   - Unpublish an assistant in LAMB
   - Refresh OpenWebUI model dropdown
   - Verify unpublished assistant no longer appears

**Phase 6: Authentication and Session Testing**
1. Test authentication token persistence:
   - Close and reopen OpenWebUI tab using LAMB button
   - Verify no re-authentication required
   - Check token validity across sessions
2. Test session synchronization:
   - Make changes to assistant in LAMB (edit system prompt)
   - Publish/republish the assistant
   - Test if changes reflect in OpenWebUI (may require refresh)

**Expected Results:**
**Interface Access:**
- OpenWebUI button opens interface in new tab/window ✅
- Authentication is seamless with proper token inclusion ✅
- No manual login required in OpenWebUI ✅
- Interface loads without errors ✅

**Model Dropdown:**
- ALL user's published assistants appear in model dropdown ✅
- Assistant names match LAMB exactly (including prefixes) ✅
- Model format follows `lamb_assistant.{id}` convention ✅
- Only PUBLISHED assistants are visible (unpublished hidden) ✅
- Dropdown count matches published assistant count in LAMB ✅

**Assistant Functionality:**
- Selected assistants respond correctly to test messages ✅
- Response times under 10 seconds ✅
- Responses match configured system prompts ✅
- Conversation continuity works within same assistant ✅
- Different assistants provide distinct, appropriate responses ✅

**Configuration Consistency:**
- OpenWebUI assistant behavior matches LAMB configuration ✅
- LLM model settings are properly applied ✅
- System prompts are correctly implemented ✅
- Publish/unpublish status synchronizes correctly ✅
- Assistant changes in LAMB reflect in OpenWebUI after republishing ✅

**Authentication and Session:**
- Authentication tokens work consistently ✅
- Session persistence across tab closures ✅
- No authentication errors or timeouts ✅
- Token synchronization between LAMB and OpenWebUI ✅

**Performance Benchmarks:**
- OpenWebUI interface load time: < 5 seconds
- Model dropdown population: < 3 seconds
- Assistant response time: < 10 seconds
- Model switching time: < 2 seconds

**Integration Verification Checklist:**
```
LAMB Assistants vs OpenWebUI Models:
□ Assistant Count Match (Published only)
□ Names Match Exactly  
□ IDs Correspond Correctly
□ System Prompts Applied
□ LLM Models Applied
□ RAG Settings Applied
□ Unpublished Assistants Hidden
□ Authentication Token Valid
□ Response Quality Consistent
□ Conversation Isolation Working
```

---

### Test Case 12: OpenWebUI Cross-Language Integration Testing

**Objective:** Verify OpenWebUI integration works correctly across all supported LAMB languages.

**Steps:**
1. Test OpenWebUI access from each LAMB language interface:
   - Switch LAMB to Spanish (ES) and access OpenWebUI
   - Switch LAMB to Catalan (CA) and access OpenWebUI  
   - Switch LAMB to Basque (EU) and access OpenWebUI
   - Switch LAMB to English (EN) and access OpenWebUI
2. Verify OpenWebUI functionality remains consistent:
   - Model dropdown contains same assistants regardless of LAMB language
   - Assistant responses are in expected language based on system prompts
   - Authentication works from all language interfaces
3. Test language-specific assistant configurations:
   - Create assistants with Spanish system prompts in LAMB-ES
   - Create assistants with English system prompts in LAMB-EN
   - Verify language consistency in OpenWebUI responses

**Expected Results:**
- OpenWebUI access works from all LAMB language interfaces ✅
- Model dropdown content consistent across languages ✅
- Assistant responses match configured prompt languages ✅
- Authentication tokens work from all language interfaces ✅
- No language-specific integration failures ✅

---

## Advanced Language Consistency Testing (i18n)

### Test Case 13: Advanced i18n for Assistant Operations

**Objective:** Verify all advanced operations work correctly across all supported languages.

**Steps:**
1. Test export functionality in each language:
   - Verify export button labels
   - Check download confirmations
   - Validate error messages
2. Test import functionality translations:
   - File selection dialogs
   - Validation error messages
   - Success confirmations
3. Test publishing workflow translations:
   - Status indicators ("Publicado", "Publicat")
   - Confirmation dialogs
   - Success/error messages
4. Test deletion workflow translations:
   - Confirmation dialog text
   - Warning messages
   - Success confirmations

**Expected Results for Spanish:**
- Export: "Exportar JSON", "Descarga completada"
- Import: "Importar", "Archivo inválido", "Importación exitosa"
- Publish: "Publicar", "¿Publicar asistente?", "Asistente publicado"
- Delete: "Eliminar", "¿Estás seguro?", "Asistente eliminado"

**Expected Results for Catalan:**
- Export: "Exportar JSON", "Descàrrega completada"
- Import: "Importar", "Fitxer invàlid", "Importació exitosa"
- Publish: "Publicar", "Publicar assistent?", "Assistent publicat"
- Delete: "Eliminar", "Estàs segur?", "Assistent eliminat"

---

## Performance and Technical Verification

### Console Output Verification

**Expected Console Messages:**
- Export operation logs with file details
- Import validation messages
- Publishing state change confirmations
- Chat session initialization and message logs
- No critical errors during operations

**Error Indicators to Watch For:**
- Failed export/import operations
- Publishing state sync failures
- Chat response timeouts
- Memory leaks in extended sessions

### Network Requests

**Expected API Calls:**
- `GET /creator/assistant/export/{id}` (export operations)
- `PUT /creator/assistant/publish` (publishing toggles)
- `DELETE /creator/assistant/delete` (deletion operations)
- `POST /creator/assistant/duplicate` (duplication operations)
- `GET /models` (chat model loading)
- `GET /creator/assistant/get_assistants_by_owner` (OpenWebUI model list synchronization)
- OpenWebUI authentication token validation endpoints
- Chat API calls to configured LLM endpoints
- OpenWebUI model selection and chat endpoints

### File System Verification

**Download Verification:**
- Exported JSON files are valid and complete
- File naming follows consistent conventions
- Downloads complete without corruption
- File sizes are reasonable and expected

## Success Criteria

All test cases should pass with:
- No data loss during any operations
- All file operations (export/import) work correctly
- Publishing workflow integrates properly with OpenWebUI
- OpenWebUI interface access works seamlessly with proper authentication
- User assistants appear correctly in OpenWebUI model dropdown (published only)
- Assistant functionality is consistent between LAMB and OpenWebUI interfaces
- Authentication tokens work correctly across both platforms
- Model synchronization maintains configuration consistency
- Chat functionality provides responsive, relevant interactions in both interfaces
- All operations work consistently across supported languages
- Cross-language OpenWebUI integration functions properly
- Performance meets specified benchmarks
- Error handling provides clear, actionable feedback
- Security measures prevent accidental data loss

## Known Issues and Workarounds

1. **Import Functionality:** ✅ **IMPLEMENTED** - assistants can now be imported from exported JSON files via the "Import from JSON" button in the create assistant form
2. **Bulk Operations:** Not available - operations must be performed individually
3. **Publishing Location:** Publish functionality only available in detail view, not in list view
4. **Search/Filtering:** Not currently implemented for assistant management
5. **Chat Performance:** Response times may vary based on LLM endpoint availability
6. **File Downloads:** Browser security settings may affect automatic downloads
7. **OpenWebUI Integration:** Requires proper authentication token synchronization

---

**Document Version:** 1.0  
**Last Updated:** January 2025  
**Based on Testing:** LAMB v0.1 advanced assistant operations  
**Dependencies:** Test 1 (core functionality) and Test 2 (assistant interface) must pass  
**i18n Support:** Full support for English (en), Spanish (es), Catalan (ca), Basque (eu)