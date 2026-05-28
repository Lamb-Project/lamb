# Single File RAG → Library Manager: Implementation Changelog

## Task 1: Tests for single_file_rag (RED)
- Created: `testing/unit-tests/completions/test_single_file_rag.py`
- 11 test cases covering: LM success, connection error, 404, 500, missing env vars, file_path backward compat, file not found, missing metadata, partial metadata, invalid JSON, library_id precedence over file_path
- Results: 7 failed, 4 passed (correct for RED phase)
- Added `id` attribute to MockAssistant (current single_file_rag.py accesses assistant.id in debug log)

## Task 2: Implement single_file_rag with LM support (GREEN)
- Modified: `backend/lamb/completions/rag/single_file_rag.py` (full rewrite, ~95 lines)
- New functions: `_fetch_from_library_manager()`, `_read_from_static_file()`
- Priority: library_id+item_id > file_path
- Sources format aligned with simple_rag: {title, url, similarity}
  - LM path: title="Library Document", url="/docs/{lib_id}/{item_id}", similarity=1.0
  - file_path: title=basename, url="/static/public/{path}", similarity=1.0
- Error handling: LM errors return empty context; file_path errors preserve old behavior (error message in context)
- Uses httpx.get() with LAMB_LIBRARY_SERVER and LAMB_LIBRARY_TOKEN env vars
- Backward compat: file_path still reads from static/public/

## Task 3: Metadata validation for single_file_rag
- Created: `testing/unit-tests/assistant_router/test_metadata_validation.py` (7 tests)
- Created: `backend/creator_interface/metadata_validators.py` (extracted from assistant_router.py, zero heavy deps)
- Modified: `backend/creator_interface/assistant_router.py` (delegates to metadata_validators)
- Validates: library_id+item_id pair, or file_path, for single_file_rag
- Other RAG processors are unaffected
- Extraction avoids heavy import chain in tests
