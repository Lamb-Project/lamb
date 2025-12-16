# Multi-Tool Assistant System - Testing Checklist

**Date:** December 11, 2025  
**Status:** Ready for Testing  
**Fix Applied:** Endpoint mismatch corrected in `multiToolAssistantService.js`

---

## ✅ Pre-Testing: Verify Fix Applied

- [x] Frontend service updated to use `/creator/assistant/create_assistant`
- [x] Frontend service updated to use `/creator/assistant/update_assistant/{id}`
- [x] Frontend service updated to use `/lamb/v1/completions/tools`
- [x] Frontend service updated to use `/lamb/v1/completions/orchestrators`

---

## 🧪 Test Suite

### Phase 1: Basic Connectivity ⚠️ TEST REQUIRED

#### 1.1 Test Tools Discovery
```bash
# Should return list of available tools
curl -X GET 'http://localhost:9099/lamb/v1/completions/tools' \
  -H "Authorization: Bearer ${YOUR_TOKEN}"

# Expected: 200 OK
# Response should include: simple_rag, rubric_rag, single_file_rag, no_rag
```

**Status:** ⬜ Not tested

---

#### 1.2 Test Orchestrators Discovery
```bash
# Should return list of orchestrator strategies
curl -X GET 'http://localhost:9099/lamb/v1/completions/orchestrators' \
  -H "Authorization: Bearer ${YOUR_TOKEN}"

# Expected: 200 OK
# Response should include: sequential, parallel, etc.
```

**Status:** ⬜ Not tested

---

### Phase 2: Multi-Tool Assistant Creation ⚠️ TEST REQUIRED

#### 2.1 Create Multi-Tool Assistant (API Test)
```bash
curl -X POST 'http://localhost:9099/creator/assistant/create_assistant' \
  -H "Authorization: Bearer ${YOUR_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Test_Multi_Tool_Assistant",
    "description": "Testing multi-tool with simple RAG",
    "system_prompt": "You are a helpful assistant.",
    "prompt_template": "Context: {1_context}\n\nUser: {user_input}\nAssistant:",
    "metadata": "{\"assistant_type\":\"multi_tool\",\"orchestrator\":\"sequential\",\"connector\":\"openai\",\"llm\":\"gpt-4o-mini\",\"verbose\":false,\"tools\":[{\"plugin\":\"simple_rag\",\"placeholder\":\"1_context\",\"enabled\":true,\"config\":{\"collections\":[],\"top_k\":3}}]}"
  }'

# Expected: 201 Created
# Response should include assistant_id, name, metadata with assistant_type="multi_tool"
```

**Status:** ⬜ Not tested

---

#### 2.2 Create Multi-Tool Assistant (UI Test)
**Steps:**
1. Open browser to `http://localhost:5173` (or your frontend URL)
2. Log in with valid credentials
3. Navigate to "Multi-Tool Assistants" page
4. Click "Create Multi-Tool Assistant"
5. Fill in form:
   - Name: "Test Multi Tool Assistant"
   - Description: "Testing the multi-tool system"
   - System Prompt: "You are a helpful assistant."
   - Prompt Template: "Context: {1_context}\n\nUser: {user_input}\nAssistant:"
   - Orchestrator: Sequential
   - Add one tool: Simple RAG (with no collections for now)
6. Click "Create"
7. Verify success message and redirect

**Expected Results:**
- ✅ No console errors
- ✅ Success notification appears
- ✅ Redirected to assistants list
- ✅ New assistant appears in list

**Status:** ⬜ Not tested

---

### Phase 3: Multi-Tool Assistant Update ⚠️ TEST REQUIRED

#### 3.1 Update Multi-Tool Assistant (API Test)
```bash
# First, get the assistant_id from Phase 2.1 or 2.2
ASSISTANT_ID=123  # Replace with actual ID

curl -X PUT "http://localhost:9099/creator/assistant/update_assistant/${ASSISTANT_ID}" \
  -H "Authorization: Bearer ${YOUR_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Updated_Multi_Tool_Assistant",
    "description": "Updated description",
    "system_prompt": "You are an updated helpful assistant.",
    "prompt_template": "Updated template: {1_context}\n\nUser: {user_input}\nAssistant:",
    "metadata": "{\"assistant_type\":\"multi_tool\",\"orchestrator\":\"sequential\",\"connector\":\"openai\",\"llm\":\"gpt-4o\",\"verbose\":true,\"tools\":[{\"plugin\":\"simple_rag\",\"placeholder\":\"1_context\",\"enabled\":true,\"config\":{\"collections\":[],\"top_k\":5}}]}"
  }'

# Expected: 200 OK
# Response should include updated fields
```

**Status:** ⬜ Not tested

---

#### 3.2 Update Multi-Tool Assistant (UI Test)
**Steps:**
1. Navigate to assistants list
2. Click on the multi-tool assistant created in Phase 2
3. Click "Edit"
4. Modify fields:
   - Change orchestrator to "Parallel"
   - Add verbose mode
   - Update LLM model
5. Save changes
6. Verify updates are persisted

**Expected Results:**
- ✅ Edit form loads with current values
- ✅ Changes save successfully
- ✅ Updated values appear after refresh

**Status:** ⬜ Not tested

---

### Phase 4: Multi-Tool Completion Execution ⚠️ TEST REQUIRED

#### 4.1 Test Multi-Tool Completion (No RAG)
```bash
# Get the assistant API key from the assistant metadata
ASSISTANT_ID=123  # Replace with actual ID

# Call completion endpoint
curl -X POST 'http://localhost:9099/v1/chat/completions' \
  -H "Authorization: Bearer ${ASSISTANT_API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "'${ASSISTANT_ID}'",
    "messages": [
      {"role": "user", "content": "Hello, can you help me?"}
    ],
    "stream": false
  }'

# Expected: 200 OK
# Response should be OpenAI-compatible completion
# Check backend logs for multi-tool routing
```

**Backend Logs to Check:**
```
[INFO] Starting completion request: assistant=123
[INFO] Processing multi-tool completion (verbose=False, stream=False)
[INFO] Multi-tool orchestration succeeded
```

**Status:** ⬜ Not tested

---

#### 4.2 Test Multi-Tool Completion (With RAG)
**Prerequisites:**
- Create a knowledge base with test documents
- Update assistant to include the KB collection ID

```bash
# Update assistant to include real KB collection
ASSISTANT_ID=123
KB_COLLECTION_ID="your-kb-uuid"

curl -X PUT "http://localhost:9099/creator/assistant/update_assistant/${ASSISTANT_ID}" \
  -H "Authorization: Bearer ${YOUR_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Multi_Tool_With_RAG",
    "metadata": "{\"assistant_type\":\"multi_tool\",\"orchestrator\":\"sequential\",\"connector\":\"openai\",\"llm\":\"gpt-4o-mini\",\"verbose\":false,\"tools\":[{\"plugin\":\"simple_rag\",\"placeholder\":\"1_context\",\"enabled\":true,\"config\":{\"collections\":[\"'${KB_COLLECTION_ID}'\"],\"top_k\":3}}]}"
  }'

# Then test completion with a query that should retrieve from KB
curl -X POST 'http://localhost:9099/v1/chat/completions' \
  -H "Authorization: Bearer ${ASSISTANT_API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "'${ASSISTANT_ID}'",
    "messages": [
      {"role": "user", "content": "What does the documentation say about X?"}
    ],
    "stream": false
  }'

# Expected: 200 OK
# Response should include context from KB in the completion
```

**Status:** ⬜ Not tested

---

#### 4.3 Test Multi-Tool with Multiple Tools
**Setup: Create assistant with multiple tools**
```json
{
  "assistant_type": "multi_tool",
  "orchestrator": "sequential",
  "tools": [
    {
      "plugin": "simple_rag",
      "placeholder": "1_context",
      "enabled": true,
      "config": {"collections": ["kb-id-1"], "top_k": 3}
    },
    {
      "plugin": "rubric_rag",
      "placeholder": "2_rubric",
      "enabled": true,
      "config": {"rubric_id": 1, "format": "markdown"}
    }
  ]
}
```

**Prompt Template:**
```
Context from knowledge base: {1_context}

Assessment rubric: {2_rubric}

User question: {user_input}
Assistant response:
```

**Test:**
- Send query that requires both KB context and rubric
- Verify both placeholders are replaced in final prompt
- Check that sequential orchestration chains outputs correctly

**Status:** ⬜ Not tested

---

### Phase 5: Verbose Mode & Debugging ⚠️ TEST REQUIRED

#### 5.1 Test Verbose Mode
**Setup:** Update assistant with `verbose: true`

**Expected in Response:**
- Detailed execution report in markdown format
- Tool execution timestamps
- Placeholder replacement details
- Sources aggregated from all tools

**Status:** ⬜ Not tested

---

#### 5.2 Test Sequential Orchestration
**Behavior:**
- Tools execute one by one
- Each tool sees outputs from previous tools
- Prompt template updated progressively

**Status:** ⬜ Not tested

---

#### 5.3 Test Parallel Orchestration
**Behavior:**
- All tools execute simultaneously
- Independent tool execution
- Results merged at the end

**Status:** ⬜ Not tested

---

### Phase 6: Error Handling ⚠️ TEST REQUIRED

#### 6.1 Test Invalid Tool Configuration
**Setup:** Create assistant with invalid tool config (e.g., missing required fields)

**Expected:**
- Validation error on creation
- Clear error message

**Status:** ⬜ Not tested

---

#### 6.2 Test Tool Execution Failure
**Setup:** Configure tool with invalid data (e.g., non-existent KB collection)

**Expected:**
- Graceful error handling
- Error message in completion response
- System doesn't crash

**Status:** ⬜ Not tested

---

#### 6.3 Test Streaming with Multi-Tool
```bash
curl -X POST 'http://localhost:9099/v1/chat/completions' \
  -H "Authorization: Bearer ${ASSISTANT_API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "'${ASSISTANT_ID}'",
    "messages": [{"role": "user", "content": "Test"}],
    "stream": true
  }'

# Expected: SSE stream with tokens
```

**Status:** ⬜ Not tested

---

## 📊 Test Results Summary

| Phase | Test | Status | Notes |
|-------|------|--------|-------|
| 1.1 | Tools Discovery | ⬜ | |
| 1.2 | Orchestrators Discovery | ⬜ | |
| 2.1 | Create Multi-Tool (API) | ⬜ | |
| 2.2 | Create Multi-Tool (UI) | ⬜ | |
| 3.1 | Update Multi-Tool (API) | ⬜ | |
| 3.2 | Update Multi-Tool (UI) | ⬜ | |
| 4.1 | Completion (No RAG) | ⬜ | |
| 4.2 | Completion (With RAG) | ⬜ | |
| 4.3 | Completion (Multiple Tools) | ⬜ | |
| 5.1 | Verbose Mode | ⬜ | |
| 5.2 | Sequential Orchestration | ⬜ | |
| 5.3 | Parallel Orchestration | ⬜ | |
| 6.1 | Invalid Config Validation | ⬜ | |
| 6.2 | Tool Failure Handling | ⬜ | |
| 6.3 | Streaming Mode | ⬜ | |

**Legend:**
- ⬜ Not tested
- ✅ Passed
- ❌ Failed
- ⚠️ Partial/Issues

---

## 🐛 Known Issues / Limitations

### To Be Verified:
1. **Response format from create/update:** Backend returns full assistant object or just ID?
2. **API key in metadata:** How is assistant API key stored and retrieved for completions?
3. **Tool config validation:** Is validation done on backend or frontend?
4. **Placeholder auto-insertion:** Does UI help insert placeholders in template?
5. **Tool reordering:** Does drag-and-drop in UI work? Does it update placeholders correctly?

---

## 🔍 Debugging Tips

### Check Backend Logs
```bash
# Follow backend logs
docker-compose logs -f backend

# Look for:
# - "Processing multi-tool completion"
# - "Multi-tool orchestration succeeded"
# - Tool execution traces
# - Error messages
```

### Check Browser Console
```javascript
// In browser console, check for errors:
// - Network errors (404, 500, etc.)
// - CORS issues
// - Authentication failures
```

### Verify Assistant Metadata
```bash
# Get assistant and check metadata
curl -X GET 'http://localhost:9099/creator/assistant/get_assistant/123' \
  -H "Authorization: Bearer ${YOUR_TOKEN}" | jq '.metadata'

# Should contain:
# {
#   "assistant_type": "multi_tool",
#   "orchestrator": "sequential",
#   "tools": [...]
# }
```

---

## ✅ Definition of Done

Multi-tool system is **production ready** when:

1. ✅ Frontend can create multi-tool assistants via UI
2. ✅ Frontend can update multi-tool assistants via UI
3. ✅ Multi-tool assistants execute completions successfully
4. ✅ Tool orchestration works (both sequential and parallel)
5. ✅ Placeholder replacement works correctly
6. ✅ RAG tools retrieve and inject context
7. ✅ Multiple tools can be chained
8. ✅ Verbose mode produces detailed reports
9. ✅ Error handling is graceful
10. ✅ Streaming mode works

---

## 📝 Test Execution Log

**Tester:** _________________  
**Date:** _________________  
**Environment:** _________________

**Notes:**
```
(Add testing notes, issues found, observations here)
```

---

## 🚀 Next Steps After Testing

Once testing is complete:

1. **If all tests pass:**
   - Update documentation with testing results
   - Mark feature as stable
   - Consider adding integration tests
   - Update user documentation

2. **If issues found:**
   - Document issues in test log
   - Create GitHub issues for each problem
   - Prioritize fixes
   - Retest after fixes

3. **Future enhancements:**
   - RESTful endpoint aliases (optional)
   - Tool dependency management
   - Conditional orchestration
   - Tool output caching
   - UI drag-and-drop for tool reordering
