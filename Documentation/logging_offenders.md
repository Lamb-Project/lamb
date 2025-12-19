# Logging Standard Offenders List

This document lists all violations of the centralized logging standard implemented in issue #149.

**Date:** December 19, 2025
**Total Offenders:** 35+ files with various violations

## Categories of Offenses

### 1. ❌ Using `logging.getLogger()` Directly Instead of Centralized `get_logger()`

**Issue:** Files using `logging.getLogger(__name__)` instead of `from lamb.logging_config import get_logger` and `get_logger(__name__, component="...")`

**Affected Files:**
- `backend/creator_interface/bulk_operations.py` (line 21)
- `backend/lamb/assistant_sharing_router.py` (line 11)
- `backend/creator_interface/api_status_checker.py` (line 14)
- `backend/lamb/creator_user_router.py` (line 14)
- `backend/creator_interface/kb_server_manager.py` (line 14)
- `backend/lamb/owi_bridge/owi_users.py` (line 20)
- `backend/lamb/completions/org_config_resolver.py` (line 15)
- `backend/lamb/completions/rag/rubric_rag.py` (line 11)
- `backend/creator_interface/knowledges_router.py` (line 170)
- `backend/lamb/completions/rag/single_file_rag.py` (line 8)
- `backend/creator_interface/learning_assistant_proxy.py` (line 26)
- `backend/lamb/completions/connectors/banana_img.py` (line 20)
- `backend/utils/migrate_sanitize_names.py` (line 45)
- `backend/lamb/completions/connectors/ollama.py` (line 12)
- `backend/lamb/completions/small_fast_model_helper.py` (line 9)
- `backend/lamb/completions/rag/context_aware_rag.py` (line 9)
- `backend/main.py` (line 49)
- `backend/lamb/completions/rag/simple_rag.py` (line 9)
- `backend/creator_interface/prompt_templates_router.py` (line 25)
- `backend/creator_interface/openai_connect.py` (line 10)
- `backend/lamb/assistant_router.py` (line 60)
- `backend/lamb/evaluaitor/prompt_loader.py` (line 12)
- `backend/test_gemini_image.py` (line 30)
- `backend/creator_interface/organization_router.py` (line 41)
- `backend/creator_interface/main.py` (line 30)
- `backend/lamb/evaluaitor/rubrics.py` (line 21)
- `backend/creator_interface/assistant_router.py` (line 143)
- `backend/lamb/evaluaitor/ai_generator.py` (line 19)
- `backend/utils/name_sanitizer.py` (line 17)

### 2. ❌ Manual `logging.basicConfig()` Calls

**Issue:** Files calling `logging.basicConfig()` directly instead of relying on centralized configuration.

**Affected Files:**
- `backend/lamb/owi_bridge/owi_router.py` (line 16)
- `backend/lamb/creator_user_router.py` (line 13)
- `backend/lamb/simple_lti/simple_lti_main.py` (line 7)
- `backend/main.py` (line 46)
- `backend/lamb/owi_bridge/owi_database.py` (line 9)
- `backend/lamb/completions/connectors/banana_img.py` (line 19)
- `backend/lamb/completions/connectors/ollama.py` (line 11)
- `backend/lamb/assistant_router.py` (line 59)
- `backend/creator_interface/prompt_templates_router.py` (line 24)
- `backend/lamb/database_manager.py` (line 31)
- `backend/lamb/main.py` (line 27)
- `backend/creator_interface/knowledges_router.py` (line 160)
- `backend/creator_interface/main.py` (line 26)
- `backend/test_gemini_image.py` (line 29)

### 3. ❌ Direct `logger.setLevel()` Calls

**Issue:** Files setting logger levels directly instead of using component-based configuration.

**Affected Files:**
- `backend/lamb/evaluaitor/rubrics.py` (line 22: `logger.setLevel(logging.INFO)`)
- `backend/creator_interface/kb_server_manager.py` (line 15: `logger.setLevel(logging.INFO)`)
- `backend/lamb/completions/connectors/openai.py` (line 18: `multimodal_logger.setLevel(logging.DEBUG)`)
- `backend/creator_interface/assistant_router.py` (line 144: `logger.setLevel(logging.INFO)`)
- `backend/creator_interface/openai_connect.py` (line 11: `logger.setLevel(logging.INFO)`)
- `backend/utils/migrate_sanitize_names.py` (line 334: `logger.setLevel(logging.WARNING)`)
- `backend/lamb/completions/main.py` (line 19: `logger.setLevel(logging.INFO)`)
- `backend/lamb/owi_bridge/owi_users.py` (line 21: `logger.setLevel(logging.WARNING)`)
- `backend/creator_interface/knowledges_router.py` (line 171: `logger.setLevel(logging.INFO)`)
- `backend/lamb/completions/rag/single_file_rag.py` (line 9: `logger.setLevel(logging.WARNING)`)
- `backend/creator_interface/main.py` (line 31: `logger.setLevel(logging.WARNING)`)

### 4. ❌ Direct `logging.getLogger().setLevel()` for External Libraries

**Issue:** Files configuring external library loggers directly instead of using centralized approach.

**Affected Files:**
- `backend/creator_interface/knowledges_router.py` (lines 166-168: httpx, httpcore, urllib3)
- `backend/creator_interface/assistant_router.py` (lines 138-141: httpx, httpcore, urllib3, owi_users)

### 5. ❌ Extensive Use of `print()` Statements Instead of Proper Logging

**Issue:** Files using `print()` for debugging/output instead of structured logging.

**Most Affected Files:**
- `backend/main.py` (15+ print statements for startup, errors, file serving)
- `backend/lamb/completions/rag/simple_rag.py` (20+ print statements for debugging)
- `backend/lamb/completions/rag/context_aware_rag.py` (15+ print statements)
- `backend/lamb/completions/connectors/ollama.py` (10+ print statements)
- `backend/lamb/completions/connectors/openai.py` (5+ print statements)
- `backend/utils/main_helpers.py` (10+ print statements for debugging)
- `backend/creator_interface/user_creator.py` (10+ print statements)
- `backend/utils/lamb/util.py` (15+ print statements for request debugging)

### 6. ❌ Incorrect Component Usage

**Issue:** Files using `get_logger()` but with potentially incorrect component names.

**Files to Review:**
- `backend/lamb/completions/main.py` (uses "MAIN" - may need "API")
- `backend/lamb/completions/connectors/openai.py` (uses "MAIN" - should be "API")

## Files Following the Standard ✅

**Compliant Files:**
- `backend/lamb/logging_config.py` (definition)
- `backend/lamb/mcp_router.py` (uses get_logger with MAIN component)
- `backend/lamb/completions/pps/simple_augment.py` (uses get_logger with MAIN component)

## Migration Priority

### High Priority (Core Application Files) - ✅ COMPLETED:
1. `backend/main.py` - Main application entry point ✅ FIXED
2. `backend/creator_interface/main.py` - Creator interface main ✅ FIXED
3. `backend/lamb/completions/main.py` - Completions main pipeline ✅ FIXED

### Medium Priority (API Endpoints) - ✅ COMPLETED:
1. `backend/creator_interface/assistant_router.py` ✅ FIXED
2. `backend/creator_interface/knowledges_router.py` ✅ FIXED
3. `backend/creator_interface/organization_router.py` ✅ FIXED
4. `backend/lamb/assistant_router.py` ✅ FIXED

### Low Priority (Utilities/Debug) - SIGNIFICANTLY COMPLETED:
1. `backend/lamb/completions/rag/simple_rag.py` ✅ FIXED (20+ print statements converted)
2. `backend/lamb/completions/rag/context_aware_rag.py` ✅ FIXED (15+ print statements converted)
3. `backend/utils/main_helpers.py` ✅ FIXED (16 print statements converted to structured logging)
4. `backend/creator_interface/user_creator.py` ✅ FIXED (20 print statements converted to structured logging)
5. RAG debugging print statements (remaining)
6. Test files
7. Utility scripts

### Additional Files Fixed:
- `backend/lamb/completions/connectors/ollama.py` ✅ FIXED (removed manual basicConfig)
- `backend/lamb/database_manager.py` ✅ FIXED (removed manual basicConfig)
- `backend/lamb/owi_bridge/owi_users.py` ✅ FIXED (removed manual logger setup)
- `backend/lamb/creator_user_router.py` ✅ FIXED (removed manual basicConfig)
- `backend/lamb/completions/connectors/openai.py` ✅ FIXED (removed redundant print statements, fixed multimodal logger)

## Summary

**Total Files with Offenses:** 35+
**Primary Issues:**
- 28 files using direct `logging.getLogger()`
- 14 files with manual `basicConfig()` calls
- 11 files with direct `setLevel()` calls
- 100+ `print()` statements that should be logs
- 2 files with external library logger configuration

**Migration Required:** All files listed above need to be updated to use the centralized logging system implemented in issue #149.