# Test 5: Organization-Scoped Configuration Management

## Overview

This test validates the complete implementation of organization-scoped assistant defaults and capabilities management (Phases 1, 2, and 3) as described in `config_org_management.md`.

## Prerequisites

- LAMB system running with multi-organization support
- Admin access to the system
- At least one OpenAI API key configured
- Test organization created (or ability to create one)

## Test Environment Setup

### 1. Admin Login
```bash
# Navigate to LAMB frontend
http://localhost:9099

# Login as system admin
Email: admin@owi.com
Password: admin
```

### 2. Verify System Organization
- Navigate to **Admin** → **Organizations**
- Confirm "lamb" system organization exists
- Note the organization ID and configuration

### 3. Create Test Organization (if needed)
- Click "Create Organization"
- Name: "Test Engineering Org"
- Slug: "test-eng"
- Assign admin user
- Set signup key: "test-eng-2024"

---

## Phase 1 Tests: Organization-Scoped Assistant Defaults

### Test 1.1: System Organization Bootstrap
**Objective**: Verify system org seeds assistant_defaults from defaults.json

**Steps**:
1. Navigate to **Admin** → **Organizations**
2. Click "View Configuration" for "lamb" organization
3. Look for `assistant_defaults` object in JSON

**Expected Results**:
- ✅ `assistant_defaults` object exists in system org config
- ✅ Contains keys from `/backend/static/json/defaults.json`:
  - `system_prompt`
  - `prompt_template` 
  - `connector` (should be "openai")
  - `llm` (should be "gpt-4o-mini" or similar)
  - `rag_processor`
  - `prompt_processor`
- ✅ Values match those in the static defaults file

### Test 1.2: Organization Creation Inheritance
**Objective**: Verify new organizations inherit assistant_defaults

**Steps**:
1. Create a new test organization (if not done in setup)
2. Immediately view its configuration
3. Check for `assistant_defaults` object

**Expected Results**:
- ✅ New organization has `assistant_defaults` object
- ✅ Values match system organization at time of creation
- ✅ All keys from system org are present

### Test 1.3: System Sync Preservation
**Objective**: Verify system sync preserves customizations

**Steps**:
1. Navigate to **Org Admin** → **Settings**
2. Edit Assistant Defaults JSON to add custom field:
   ```json
   {
     "assistant_defaults": {
       "system_prompt": "Custom test prompt",
       "connector": "openai",
       "llm": "gpt-4o-mini",
       "custom_field": "test_value",
       ...existing fields...
     }
   }
   ```
3. Save changes
4. Restart LAMB system (simulates sync)
5. Check assistant defaults again

**Expected Results**:
- ✅ Custom fields are preserved after restart
- ✅ New keys from defaults.json are added if any
- ✅ Existing customizations remain unchanged

---

## Phase 2 Tests: Org-Aware Capabilities and UI

### Test 2.1: Organization-Aware Capabilities
**Objective**: Verify capabilities endpoint returns org-specific models

**Steps**:
1. Login as user in test organization
2. Navigate to **Learning Assistants** → **Create Assistant**
3. Open browser developer tools → Network tab
4. Check the request to `/lamb/v1/completions/list`
5. Verify response contains organization-specific models

**Expected Results**:
- ✅ Request includes Authorization header
- ✅ Response shows models enabled for user's organization
- ✅ Models list differs from system-wide defaults if org has restrictions

### Test 2.2: Assistant Defaults API Endpoints
**Objective**: Test the assistant defaults API endpoints

**Manual API Testing**:
```bash
# Get assistant defaults for current user's org
curl -H "Authorization: Bearer <USER_TOKEN>" \
  http://localhost:9099/creator/assistant/defaults

# Get specific org assistant defaults (admin only)
curl -H "Authorization: Bearer <ADMIN_TOKEN>" \
  http://localhost:9099/creator/admin/organizations/test-eng/assistant-defaults

# Update org assistant defaults (admin only)
curl -X PUT \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"assistant_defaults":{"connector":"openai","llm":"gpt-4o","system_prompt":"Updated prompt"}}' \
  http://localhost:9099/creator/admin/organizations/test-eng/assistant-defaults
```

**Expected Results**:
- ✅ GET endpoints return organization-specific defaults
- ✅ PUT endpoint updates defaults successfully
- ✅ Unknown keys are preserved in updates
- ✅ Proper authentication required

### Test 2.3: Org Admin UI - Assistant Defaults Management
**Objective**: Test the Assistant Defaults UI in Org Admin

**Steps**:
1. Login as organization admin
2. Navigate to **Org Admin** → **Settings**
3. Scroll to "Assistant Defaults" section
4. Verify JSON editor loads with current defaults
5. Make a change to the JSON (e.g., change llm model)
6. Click "Save Assistant Defaults"
7. Click "Reload" to verify changes persisted

**Expected Results**:
- ✅ Assistant Defaults section is visible
- ✅ JSON editor loads with organization's current defaults
- ✅ JSON validation works (try invalid JSON)
- ✅ Save functionality works (currently may show 405 error - known issue)
- ✅ Reload shows updated values
- ✅ Unknown keys are preserved

### Test 2.4: Assistant Form Uses Org Defaults
**Objective**: Verify assistant creation form uses org-scoped defaults

**Steps**:
1. Navigate to **Learning Assistants** → **Create Assistant**
2. Check default values in form fields
3. Compare with organization's assistant_defaults
4. Check available models in dropdowns

**Expected Results**:
- ✅ Form fields populate with organization defaults
- ✅ System prompt matches org's `system_prompt`
- ✅ Default connector matches org's `connector`
- ✅ Default model matches org's `llm`
- ✅ Available models list matches org's enabled models

---

## Phase 3 Tests: Connector Runtime Fallback

### Test 3.1: OpenAI Model Fallback
**Objective**: Test OpenAI connector fallback logic

**Setup**:
1. Configure test organization with limited OpenAI models:
   - Enabled models: `["gpt-4o", "gpt-3.5-turbo"]`
   - Default model: `"gpt-4o"`

**Test Cases**:

#### Test 3.1a: Requested Model Available
```bash
# Create assistant with available model
# Set LLM to "gpt-4o" (which is in enabled list)
# Execute the assistant
```
**Expected**: ✅ Uses requested model, no fallback

#### Test 3.1b: Fallback to Org Default
```bash
# Create assistant with unavailable model
# Set LLM to "gpt-4o-mini" (not in enabled list)
# Execute the assistant
```
**Expected**: 
- ✅ Falls back to org default "gpt-4o"
- ✅ Warning logged about fallback
- ✅ Console shows fallback message

#### Test 3.1c: Fallback to First Available
```bash
# Configure org with no default_model set
# Request unavailable model
# Execute the assistant
```
**Expected**:
- ✅ Falls back to first available model
- ✅ Warning logged about fallback
- ✅ Assistant execution succeeds

### Test 3.2: Ollama Model Fallback
**Objective**: Test Ollama connector fallback logic

**Setup** (if Ollama is available):
1. Configure test organization with limited Ollama models:
   - Enabled models: `["llama3.1", "codellama"]`
   - Default model: `"llama3.1"`

**Test Cases**:
Follow similar pattern as OpenAI tests above.

**Expected Results**:
- ✅ Same fallback behavior as OpenAI
- ✅ Proper logging and console messages
- ✅ Graceful handling when no models configured

### Test 3.3: System Organization Legacy Fallback
**Objective**: Verify system org maintains env var compatibility

**Steps**:
1. Create assistant owned by system org admin
2. Request model not in system org config
3. Verify fallback to environment variables

**Expected Results**:
- ✅ System org falls back to `OPENAI_MODEL` env var
- ✅ Logging indicates env var fallback used
- ✅ Maintains backward compatibility

---

## Integration Tests

### Test 4.1: End-to-End Assistant Creation and Execution
**Objective**: Complete workflow using org-scoped configuration

**Steps**:
1. Login as test organization user
2. Create new assistant with default values
3. Customize assistant with unavailable model
4. Save assistant
5. Execute assistant with test message
6. Verify execution uses fallback model

**Expected Results**:
- ✅ Assistant created with org defaults
- ✅ Execution succeeds with model fallback
- ✅ Response indicates which model was actually used
- ✅ Fallback logged appropriately

### Test 4.2: Multi-Organization Isolation
**Objective**: Verify organizations don't interfere with each other

**Steps**:
1. Configure different defaults for two organizations
2. Create assistants in each organization
3. Execute assistants and verify they use their respective configs

**Expected Results**:
- ✅ Each org uses its own configuration
- ✅ No cross-contamination of settings
- ✅ Proper isolation maintained

---

## Error Handling Tests

### Test 5.1: Invalid Configuration Handling
**Test Cases**:
- Organization with no models enabled
- Organization with invalid default_model
- Missing API keys for non-system org
- Malformed assistant_defaults JSON

**Expected Results**:
- ✅ Clear error messages
- ✅ Graceful degradation where possible
- ✅ Proper logging of issues
- ✅ System remains stable

### Test 5.2: Fallback Chain Exhaustion
**Steps**:
1. Configure org with no available models
2. Request unavailable model
3. Verify error handling

**Expected Results**:
- ✅ Clear error message about no available models
- ✅ Execution fails gracefully
- ✅ User receives actionable error information

---

## Performance Tests

### Test 6.1: Configuration Resolution Performance
**Objective**: Verify org config resolution doesn't impact performance

**Steps**:
1. Create multiple assistants with different owners
2. Execute them concurrently
3. Monitor response times and resource usage

**Expected Results**:
- ✅ No significant performance degradation
- ✅ Config caching works effectively
- ✅ Concurrent execution handles properly

---

## Logging and Monitoring Tests

### Test 7.1: Logging Verification
**Objective**: Verify proper logging of configuration sources and fallbacks

**Steps**:
1. Execute assistants with various configurations
2. Check application logs for relevant messages
3. Verify log levels and content

**Expected Log Messages**:
- ✅ Organization config usage: `"Using organization config for user@example.com (org: Test Org)"`
- ✅ Environment fallback: `"Using environment variable configuration (fallback)"`
- ✅ Model fallback warnings: `"Model 'gpt-4o-mini' not available for org 'Test Org', using org default: 'gpt-4o'"`
- ✅ Config source indicators in console output

---

## Regression Tests

### Test 8.1: Backward Compatibility
**Objective**: Ensure existing functionality still works

**Steps**:
1. Test assistant creation/execution without explicit organization context
2. Verify environment variable fallback for system organization
3. Test existing API endpoints

**Expected Results**:
- ✅ Legacy behavior maintained where expected
- ✅ No breaking changes to existing functionality
- ✅ Smooth migration path

---

## Known Issues to Verify

### Issue 1: Save Assistant Defaults (405 Error)
**Current Status**: Known issue in Phase 2

**Test**:
1. Navigate to Org Admin → Settings → Assistant Defaults
2. Try to save changes
3. Verify error occurs

**Expected**: ⚠️ 405 Method Not Allowed error (to be fixed)

**Workaround Test**:
- Use direct API calls to verify endpoints work
- Confirm issue is only in UI integration

---

## Test Results Summary

| Test Category | Total Tests | Passed | Failed | Notes |
|---------------|-------------|--------|--------|-------|
| Phase 1 - Storage | 3 | | | |
| Phase 2 - Org-Aware | 4 | | | |
| Phase 3 - Fallback | 3 | | | |
| Integration | 2 | | | |
| Error Handling | 2 | | | |
| Performance | 1 | | | |
| Logging | 1 | | | |
| Regression | 1 | | | |
| **TOTAL** | **17** | | | |

---

## Cleanup

After testing, clean up test data:
1. Remove test assistants created during testing
2. Reset organization configurations if modified
3. Clear any test organizations if no longer needed

---

## Next Steps

Based on test results:
1. **Fix Known Issues**: Address the 405 error in save functionality
2. **Performance Optimization**: If any performance issues identified
3. **Additional Features**: Based on user feedback from testing
4. **Documentation Updates**: Update user guides based on test findings

---

*Test document created for LAMB v0.1 - Organization-Scoped Configuration Management*
*Last updated: $(date)*
