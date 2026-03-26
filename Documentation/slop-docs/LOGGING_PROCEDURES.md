# LAMB Logging Procedures

**Version:** 1.0  
**Date:** December 19, 2025  
**Related Issue:** #149 - Centralize logging configuration  
**Status:** Active

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Logging Components](#logging-components)
4. [Standard Procedures](#standard-procedures)
5. [Log Levels](#log-levels)
6. [Best Practices](#best-practices)
7. [Configuration](#configuration)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)
10. [Migration Guide](#migration-guide)

---

## Overview

LAMB uses a **centralized logging system** that provides:
- ✅ Single point of control via environment variables
- ✅ Component-specific logging levels
- ✅ Container-friendly stdout logging
- ✅ Consistent logging patterns across the codebase
- ✅ No manual logger configuration needed

**Key Principle:** All logging goes through `lamb.logging_config.get_logger()` - no manual `logging.basicConfig()` or direct `logging.getLogger()` calls.

---

## Quick Start

### For New Modules

```python
# 1. Import the centralized logger
from lamb.logging_config import get_logger

# 2. Create a logger instance (choose appropriate component)
logger = get_logger(__name__, component="API")

# 3. Use standard logging methods
logger.debug("Detailed debugging information")
logger.info("General informational message")
logger.warning("Warning about potential issue")
logger.error("Error that needs attention")
logger.critical("Critical error affecting operation")
```

**That's it!** No need to configure handlers, formatters, or log levels manually.

---

## Logging Components

LAMB organizes logging into **seven components** for fine-grained control:

| Component | Purpose | Use When |
|-----------|---------|----------|
| **MAIN** | Main application logic | Core application flow, startup, general operations |
| **API** | API endpoints and routers | FastAPI routes, HTTP request handling, API responses |
| **DB** | Database operations | Database queries, transactions, schema operations |
| **RAG** | RAG pipeline operations | Knowledge base queries, document retrieval, context generation |
| **EVALUATOR** | Evaluation and grading | Assessment logic, rubric processing, scoring |
| **OWI** | Open WebUI integration | OWI bridge operations, user sync, model management |
| **LTI** | LTI integration | LTI launches, OAuth signature verification, LMS integration |

### Component Selection Guide

```python
# Main application files (main.py, startup logic)
logger = get_logger(__name__, component="MAIN")

# API endpoints and routers
logger = get_logger(__name__, component="API")

# Database operations
logger = get_logger(__name__, component="DB")

# RAG/Knowledge base operations
logger = get_logger(__name__, component="RAG")

# Evaluation/grading logic
logger = get_logger(__name__, component="EVALUATOR")

# Open WebUI integration
logger = get_logger(__name__, component="OWI")

# LTI integration (launches, OAuth, LMS)
logger = get_logger(__name__, component="LTI")
```

---

## Standard Procedures

### 1. Creating a New Module

```python
"""
Module description here.
"""

# Standard imports first
import json
import os
from typing import Dict, Any, List

# External dependencies
from fastapi import APIRouter, HTTPException
import httpx

# LAMB imports
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger  # Import logger

# Create logger instance (REQUIRED)
logger = get_logger(__name__, component="API")  # Choose appropriate component

# Rest of your code
router = APIRouter()

@router.get("/endpoint")
async def my_endpoint():
    logger.info("Processing endpoint request")
    try:
        # Your logic here
        result = process_data()
        logger.debug(f"Result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in endpoint: {e}")
        raise
```

### 2. Converting Existing Modules

**Step 1:** Add the import
```python
from lamb.logging_config import get_logger
```

**Step 2:** Replace old logging setup
```python
# ❌ REMOVE THIS:
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ REPLACE WITH:
from lamb.logging_config import get_logger
logger = get_logger(__name__, component="API")
```

**Step 3:** Replace print statements
```python
# ❌ REMOVE THIS:
print(f"Processing user {user_id}")
print(f"Error: {error_message}")

# ✅ REPLACE WITH:
logger.info(f"Processing user {user_id}")
logger.error(f"Error: {error_message}")
```

**Step 4:** Remove manual logger configuration
```python
# ❌ REMOVE ALL OF THIS:
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
```

### 3. Testing Your Logging

```bash
# Test with different log levels
GLOBAL_LOG_LEVEL=DEBUG python your_module.py

# Test component-specific level
API_LOG_LEVEL=DEBUG python your_module.py

# Test in production mode (only warnings and errors)
GLOBAL_LOG_LEVEL=WARNING python your_module.py
```

---

## Log Levels

### When to Use Each Level

#### DEBUG (Development/Troubleshooting)
```python
logger.debug(f"Request parameters: {params}")
logger.debug(f"Database query: {query}")
logger.debug(f"Raw API response: {response}")
```

**Use for:** Variable values, function parameters, intermediate results, detailed flow information.

#### INFO (Normal Operation)
```python
logger.info(f"User {email} logged in successfully")
logger.info(f"Assistant created: {assistant_name}")
logger.info(f"Processing {count} items")
```

**Use for:** Important business events, successful operations, major state changes.

#### WARNING (Potential Issues)
```python
logger.warning(f"Using fallback model: {fallback_model}")
logger.warning(f"API rate limit approaching: {remaining} requests left")
logger.warning(f"Configuration missing for {organization}, using defaults")
```

**Use for:** Recoverable issues, fallback behavior, configuration problems, deprecated usage.

#### ERROR (Failures)
```python
logger.error(f"Failed to connect to database: {error}")
logger.error(f"API call failed for user {user_id}: {error}")
logger.error(f"Invalid data format received: {data}")
```

**Use for:** Operation failures, API errors, validation failures, data corruption.

#### CRITICAL (System Failures)
```python
logger.critical(f"Database connection pool exhausted")
logger.critical(f"Unable to start server: {error}")
logger.critical(f"Critical service unavailable: {service}")
```

**Use for:** System-wide failures, service unavailability, data loss scenarios.

---

## Best Practices

### ✅ DO

1. **Always use the centralized logger**
   ```python
   from lamb.logging_config import get_logger
   logger = get_logger(__name__, component="API")
   ```

2. **Include context in log messages**
   ```python
   # Good: Includes user_id and organization
   logger.info(f"Created assistant '{name}' for user {user_id} in org {org_id}")
   
   # Bad: Vague message
   logger.info("Created assistant")
   ```

3. **Use appropriate log levels**
   ```python
   logger.debug("Detailed debugging info")     # Development
   logger.info("Normal operation event")       # Production
   logger.warning("Potential issue")           # Attention needed
   logger.error("Operation failed")            # Immediate attention
   logger.critical("System failure")           # Critical attention
   ```

4. **Log exceptions with context**
   ```python
   try:
       result = risky_operation()
   except Exception as e:
       logger.error(f"Failed to process {item_id}: {e}")
       raise
   ```

5. **Use structured data in logs**
   ```python
   logger.info(f"Assistant created: id={assistant_id}, owner={owner}, org={org_name}")
   ```

6. **Log at entry and exit of critical operations**
   ```python
   def critical_operation(user_id):
       logger.info(f"Starting critical operation for user {user_id}")
       try:
           result = perform_operation()
           logger.info(f"Completed critical operation for user {user_id}")
           return result
       except Exception as e:
           logger.error(f"Failed critical operation for user {user_id}: {e}")
           raise
   ```

### ❌ DON'T

1. **Don't use print() statements**
   ```python
   # ❌ Bad
   print(f"Processing request for {user_id}")
   
   # ✅ Good
   logger.info(f"Processing request for {user_id}")
   ```

2. **Don't use direct logging module**
   ```python
   # ❌ Bad
   import logging
   logging.info("Message")
   
   # ✅ Good
   from lamb.logging_config import get_logger
   logger = get_logger(__name__, component="API")
   logger.info("Message")
   ```

3. **Don't manually configure loggers**
   ```python
   # ❌ Bad
   logging.basicConfig(level=logging.INFO)
   logger.setLevel(logging.DEBUG)
   
   # ✅ Good
   # Use environment variables instead:
   # GLOBAL_LOG_LEVEL=DEBUG or API_LOG_LEVEL=DEBUG
   ```

4. **Don't log sensitive information**
   ```python
   # ❌ Bad
   logger.info(f"User password: {password}")
   
   # ✅ Good
   logger.info(f"User {email} password updated")
   ```

5. **Don't log excessive data in production**
   ```python
   # ❌ Bad (in production)
   logger.info(f"Full response: {json.dumps(large_object)}")
   
   # ✅ Good (use debug level for detailed data)
   logger.debug(f"Full response: {json.dumps(large_object)[:500]}...")
   logger.info(f"Response received with {len(items)} items")
   ```

6. **Don't hardcode log levels**
   ```python
   # ❌ Bad
   if DEBUG_MODE:
       logger.debug("Debug info")
   
   # ✅ Good (logger handles level automatically)
   logger.debug("Debug info")
   ```

---

## Configuration

### Environment Variables

#### Global Control
```bash
# Set global log level for ALL components
GLOBAL_LOG_LEVEL=WARNING  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

#### Component-Specific Overrides
```bash
# Override specific components while others use global level
GLOBAL_LOG_LEVEL=INFO          # Default for all
API_LOG_LEVEL=DEBUG           # API endpoints get debug
RAG_LOG_LEVEL=DEBUG           # RAG operations get debug
DB_LOG_LEVEL=WARNING          # Database only warnings+
```

### Common Configurations

#### Development (Verbose)
```bash
GLOBAL_LOG_LEVEL=DEBUG
```

#### Development (Targeted Debugging)
```bash
GLOBAL_LOG_LEVEL=INFO
API_LOG_LEVEL=DEBUG
DB_LOG_LEVEL=DEBUG
LTI_LOG_LEVEL=DEBUG
```

#### Production (Clean)
```bash
GLOBAL_LOG_LEVEL=WARNING
```

#### Production (Monitoring Specific Issues)
```bash
GLOBAL_LOG_LEVEL=WARNING
OWI_LOG_LEVEL=INFO           # Monitor OWI integration
API_LOG_LEVEL=INFO           # Monitor API traffic
LTI_LOG_LEVEL=DEBUG          # Debug LTI OAuth issues
```

### Docker Compose Configuration
```yaml
services:
  lamb-backend:
    environment:
      - GLOBAL_LOG_LEVEL=INFO
      - API_LOG_LEVEL=DEBUG
      - RAG_LOG_LEVEL=DEBUG
      - LTI_LOG_LEVEL=DEBUG
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## Examples

### Example 1: API Endpoint
```python
from fastapi import APIRouter, HTTPException
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="API")
router = APIRouter()

@router.post("/assistants")
async def create_assistant(name: str, owner: str):
    logger.info(f"Creating assistant '{name}' for owner {owner}")
    
    try:
        # Validate input
        if not name or not owner:
            logger.warning(f"Invalid input: name={name}, owner={owner}")
            raise HTTPException(status_code=400, detail="Invalid input")
        
        # Create assistant
        logger.debug(f"Calling database to create assistant")
        assistant_id = db.create_assistant(name, owner)
        
        logger.info(f"Successfully created assistant {assistant_id}")
        return {"id": assistant_id, "name": name}
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Failed to create assistant '{name}': {e}")
        raise HTTPException(status_code=500, detail="Internal error")
```

### Example 2: Database Operations
```python
from lamb.logging_config import get_logger
import sqlite3

logger = get_logger(__name__, component="DB")

class DatabaseManager:
    def query_users(self, organization_id: str):
        logger.debug(f"Querying users for organization {organization_id}")
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE organization_id = ?",
                (organization_id,)
            )
            results = cursor.fetchall()
            
            logger.info(f"Found {len(results)} users in organization {organization_id}")
            return results
            
        except sqlite3.Error as e:
            logger.error(f"Database query failed for org {organization_id}: {e}")
            raise
```

### Example 3: RAG Processing
```python
from lamb.logging_config import get_logger
import requests

logger = get_logger(__name__, component="RAG")

def rag_processor(messages, assistant):
    logger.info(f"RAG processing for assistant {assistant.name}")
    
    # Extract query
    query = extract_query(messages)
    logger.debug(f"Extracted query: {query[:100]}...")
    
    # Get collections
    collections = assistant.RAG_collections.split(',')
    logger.info(f"Querying {len(collections)} knowledge base collections")
    
    # Query each collection
    for collection_id in collections:
        logger.debug(f"Querying collection {collection_id}")
        try:
            response = requests.post(kb_url, json={"query": query})
            if response.status_code == 200:
                docs = response.json().get("documents", [])
                logger.info(f"Collection {collection_id}: retrieved {len(docs)} documents")
            else:
                logger.warning(f"Collection {collection_id}: failed with status {response.status_code}")
        except Exception as e:
            logger.error(f"Collection {collection_id}: query failed: {e}")
    
    return combined_context
```

### Example 4: Error Handling with Context
```python
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="API")

async def process_user_request(user_id: str, request_data: dict):
    logger.info(f"Processing request for user {user_id}")
    
    try:
        # Validate
        if not validate(request_data):
            logger.warning(f"Invalid request data for user {user_id}: {request_data.keys()}")
            return {"error": "Invalid data"}
        
        # Process
        logger.debug(f"Processing data: {request_data}")
        result = await perform_operation(request_data)
        
        logger.info(f"Successfully processed request for user {user_id}")
        return result
        
    except ValueError as e:
        logger.error(f"Validation error for user {user_id}: {e}")
        return {"error": "Validation failed"}
    except ConnectionError as e:
        logger.error(f"Connection error for user {user_id}: {e}")
        return {"error": "Service unavailable"}
    except Exception as e:
        logger.critical(f"Unexpected error for user {user_id}: {e}", exc_info=True)
        return {"error": "Internal error"}
```

---

## Troubleshooting

### Problem: Logs not appearing

**Check 1: Environment variable**
```bash
echo $GLOBAL_LOG_LEVEL  # Should be set
```

**Check 2: Component-specific override**
```bash
echo $API_LOG_LEVEL  # Might be overriding global
```

**Check 3: Test logging**
```python
from lamb.logging_config import get_logger
logger = get_logger('test', 'MAIN')
logger.info("Test message")  # Should appear
```

### Problem: Too many/few logs

**Adjust log level:**
```bash
# More logs (development)
GLOBAL_LOG_LEVEL=DEBUG

# Fewer logs (production)
GLOBAL_LOG_LEVEL=WARNING
```

**Target specific component:**
```bash
GLOBAL_LOG_LEVEL=WARNING  # Quiet by default
API_LOG_LEVEL=INFO        # But see API activity
```

### Problem: Component logs not working

**Check component name:**
```python
# Valid components: MAIN, API, DB, RAG, EVALUATOR, OWI, LTI
logger = get_logger(__name__, component="LTI")  # Correct

# Invalid:
logger = get_logger(__name__, component="DATABASE")  # Wrong!
```

### Problem: Logs not in container

**Check Docker Compose logging:**
```yaml
services:
  lamb-backend:
    logging:
      driver: "json-file"  # Required for docker logs
```

**View logs:**
```bash
docker-compose logs -f lamb-backend
docker logs lamb-backend-1
```

---

## Migration Guide

### Migrating from Legacy Logging

#### Step 1: Identify Old Patterns
```bash
# Find files with old patterns
grep -r "logging.basicConfig" backend/
grep -r "print(" backend/ | grep -v ".pyc"
```

#### Step 2: Update Imports
```python
# Before:
import logging

# After:
from lamb.logging_config import get_logger
```

#### Step 3: Update Logger Creation
```python
# Before:
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# After:
logger = get_logger(__name__, component="API")
```

#### Step 4: Replace Print Statements
```python
# Before:
print(f"Processing {count} items")
print(f"Error: {error}")

# After:
logger.info(f"Processing {count} items")
logger.error(f"Error: {error}")
```

#### Step 5: Remove Manual Configuration
```python
# Before:
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# After:
# Nothing needed! Configuration is automatic
```

#### Step 6: Test
```bash
# Run tests
pytest tests/

# Check logs appear correctly
GLOBAL_LOG_LEVEL=DEBUG python your_module.py
```

---

## Quick Reference

### Import Pattern
```python
from lamb.logging_config import get_logger
logger = get_logger(__name__, component="COMPONENT")
```

### Components
- `MAIN` - Application logic
- `API` - API endpoints
- `DB` - Database operations
- `RAG` - RAG pipeline
- `EVALUATOR` - Evaluation logic
- `OWI` - Open WebUI bridge
- `LTI` - LTI integration

### Log Levels
```python
logger.debug("Details")      # Development only
logger.info("Event")         # Normal operation
logger.warning("Issue")      # Attention needed
logger.error("Failure")      # Immediate attention
logger.critical("Crisis")    # Critical attention
```

### Environment Variables
```bash
GLOBAL_LOG_LEVEL=WARNING     # All components
API_LOG_LEVEL=DEBUG         # Override API component
LTI_LOG_LEVEL=DEBUG         # Override LTI component
```

### Checklist for New Modules
- [ ] Import `get_logger` from `lamb.logging_config`
- [ ] Create logger with appropriate component
- [ ] Use logger instead of print()
- [ ] Use appropriate log levels
- [ ] Include context in messages
- [ ] No manual logger configuration
- [ ] Test with different log levels

---

## Additional Resources

- **Architecture Documentation:** `Documentation/lamb_architecture.md` (Section 17)
- **Backend Architecture:** `Documentation/small-context/backend_architecture.md`
- **Implementation Review:** `Documentation/LOGGING_REVIEW_REPORT.md`
- **Offenders List:** `Documentation/logging_offenders.md`
- **Related Issue:** GitHub Issue #149

---

## Support

For questions or issues with logging:
1. Check this documentation
2. Review the logging review report
3. Check existing modules for examples
4. Review issue #149 for implementation details

---

**Last Updated:** December 19, 2025  
**Maintained By:** LAMB Development Team
