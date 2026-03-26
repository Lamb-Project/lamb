---
description: Instructions for enabling or disabling LangSmith tracing in the LAMB backend container
---

# Toggle LangSmith Tracing

Use these instructions when the user asks to enable or disable LangSmith tracing (LangChain tracing) in the backend.

## Core Workflow

1. **Modify Environment**:
   - Locate the `backend/.env` file.
   - Use `replace_string_in_file` to change `LANGCHAIN_TRACING_V2`.
   - Set to `true` to enable, or `false` to disable.
   - Ensure `LANGCHAIN_API_KEY` and `LANGCHAIN_PROJECT` are present if enabling.

2. **Apply Changes**:
   - You MUST recreate the container for the environment variable changes to take effect.
   - Run: `docker compose up -d backend`
   - Note: `docker compose restart` is NOT sufficient for new environment variables in some setups; `up -d` is safer.

3. **Verify Status**:
   - Run the verification script inside the container:
     `docker compose exec backend python test_langsmith.py`
   - Check the output for `Tracing Enabled: True` or `False`.

## Key Rules
- Always check the current state of `backend/.env` before making changes.
- Never leave `LANGCHAIN_TRACING_V2` as `true` if the `LANGCHAIN_API_KEY` is missing or invalid.
- Always confirm the container is running after the update.
