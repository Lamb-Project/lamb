## Task 1: Tests for single_file_rag (RED)
- Created: `testing/unit-tests/completions/test_single_file_rag.py`
- 11 test cases covering: LM success, connection error, 404, 500, missing env vars, file_path backward compat, file not found, missing metadata, partial metadata, invalid JSON, library_id precedence over file_path
