from fastapi import FastAPI, Request, Depends, status, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware

from starlette.responses import StreamingResponse, Response, FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict
from typing import List, Union, Generator, Iterator


from utils.pipelines.auth import bearer_security, get_current_user
from utils.pipelines.main import get_last_user_message, stream_message_template
from utils.pipelines.misc import convert_to_raw_url

from utils.lamb.util import print_form_data, print_request, print_api_key
from utils.main_helpers import completions_get_form_data, helper_get_assistant_id, helper_get_all_assistants


from lamb.main import app as lamb_app
from lamb.completions.main import run_lamb_assistant


from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from schemas import FilterForm, OpenAIChatCompletionForm
from urllib.parse import urlparse

import shutil
import aiohttp
import os
import importlib.util
import time
import json
import uuid
import sys
import subprocess
import traceback
import random

from config import API_KEY, PIPELINES_DIR
import asyncio
import re
from datetime import datetime, timedelta
from lamb.database_manager import LambDatabaseManager
from creator_interface.main import router as creator_router, start_news_cache_refresh_loop, stop_news_cache_refresh_loop
from lamb.logging_config import get_logger

# Set up centralized logging
logger = get_logger(__name__, component="MAIN")
multimodal_logger = get_logger('multimodal', component="MAIN")

# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events and schedule DB maintenance jobs."""
    # Startup
    logger.info("Starting LAMB application")
    await start_news_cache_refresh_loop()
    logger.info("News cache refresh loop started")

    # --- DB maintenance background tasks (asyncio-based, no external deps) ---
    try:
        # DB maintenance is OFF by default to avoid duplicate background jobs when using --reload in dev.
        db_scheduler_enabled = os.getenv('DB_MAINTENANCE_ENABLED', 'false').lower() == 'true'
        if db_scheduler_enabled:
            # parse checkpoint interval from DB_CHECKPOINT_CRON (supports '*/N' or plain minutes)
            def _parse_checkpoint_minutes(val: str) -> int:
                try:
                    if val.isdigit():
                        return int(val)
                    m = re.match(r'^\*/(\d+)$', (val or '').strip())
                    if m:
                        return int(m.group(1))
                except Exception:
                    pass
                return 30

            checkpoint_minutes = _parse_checkpoint_minutes(os.getenv('DB_CHECKPOINT_CRON', '*/30'))
            optimize_hour = int(os.getenv('DB_OPTIMIZE_HOUR', '3'))
            optimize_minute = int(os.getenv('DB_OPTIMIZE_MINUTE', '0'))
            vacuum_day = os.getenv('DB_VACUUM_DAY', 'sun').lower()
            vacuum_hour = int(os.getenv('DB_VACUUM_HOUR', '3'))
            vacuum_minute = int(os.getenv('DB_VACUUM_MINUTE', '30'))

            async def _checkpoint_loop():
                try:
                    while True:
                        logger.info("DB maintenance: running checkpoint_wal job")
                        try:
                            await run_in_threadpool(LambDatabaseManager().checkpoint_wal)
                        except Exception as e:
                            logger.error(f"DB checkpoint task error: {e}")
                        await asyncio.sleep(checkpoint_minutes * 60)
                except asyncio.CancelledError:
                    logger.info("DB checkpoint loop cancelled")
                    return

            async def _daily_optimize_loop():
                try:
                    while True:
                        now = datetime.now()
                        target = now.replace(hour=optimize_hour, minute=optimize_minute, second=0, microsecond=0)
                        if target <= now:
                            target += timedelta(days=1)
                        delay = (target - now).total_seconds()
                        await asyncio.sleep(delay)
                        logger.info("DB maintenance: running daily optimize (ANALYZE + PRAGMA optimize, skip VACUUM)")
                        try:
                            await run_in_threadpool(LambDatabaseManager().optimize_database, False)
                        except Exception as e:
                            logger.error(f"DB daily optimize task error: {e}")
                except asyncio.CancelledError:
                    logger.info("DB daily optimize loop cancelled")
                    return

            async def _weekly_vacuum_loop():
                try:
                    dow_map = {'mon':0,'tue':1,'wed':2,'thu':3,'fri':4,'sat':5,'sun':6}
                    target_dow = dow_map.get(vacuum_day[:3], 6)
                    while True:
                        now = datetime.now()
                        days_ahead = (target_dow - now.weekday() + 7) % 7
                        if days_ahead == 0:
                            target = now.replace(hour=vacuum_hour, minute=vacuum_minute, second=0, microsecond=0)
                            if target <= now:
                                days_ahead = 7
                                target += timedelta(days=7)
                        else:
                            target = (now + timedelta(days=days_ahead)).replace(hour=vacuum_hour, minute=vacuum_minute, second=0, microsecond=0)

                        delay = (target - now).total_seconds()
                        await asyncio.sleep(delay)
                        logger.info("DB maintenance: running weekly VACUUM (ANALYZE + VACUUM + PRAGMA optimize)")
                        try:
                            await run_in_threadpool(LambDatabaseManager().optimize_database, True)
                        except Exception as e:
                            logger.error(f"DB weekly vacuum task error: {e}")
                except asyncio.CancelledError:
                    logger.info("DB weekly vacuum loop cancelled")
                    return

            # start background tasks and keep references for shutdown
            tasks = [
                asyncio.create_task(_checkpoint_loop(), name='db_checkpoint_loop'),
                asyncio.create_task(_daily_optimize_loop(), name='db_daily_optimize_loop'),
                asyncio.create_task(_weekly_vacuum_loop(), name='db_weekly_vacuum_loop'),
            ]
            app.state.db_maintenance_tasks = tasks
            logger.info(f"DB maintenance tasks started (checkpoint every {checkpoint_minutes} min; daily-optimize: {optimize_hour}:{optimize_minute}; weekly-vacuum: {vacuum_day} {vacuum_hour}:{vacuum_minute})")
        else:
            logger.info("DB maintenance disabled by env var DB_MAINTENANCE_ENABLED")
    except Exception as e:
        logger.error(f"Failed to start DB maintenance tasks: {e}")
    # --- end background-tasks setup ---

    yield

    # Shutdown
    logger.info("Shutting down LAMB application")

    # Stop DB maintenance scheduler / cancel asyncio background tasks if running
    try:
        # Legacy APScheduler instance (if present)
        scheduler = getattr(app.state, 'db_maintenance_scheduler', None)
        if scheduler:
            logger.info("Shutting down DB maintenance scheduler (legacy)")
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                logger.exception("Error stopping legacy DB scheduler")

        # Cancel asyncio background tasks created by our lifespan
        tasks = getattr(app.state, 'db_maintenance_tasks', None)
        if tasks:
            logger.info("Cancelling DB maintenance background tasks")
            for t in tasks:
                try:
                    t.cancel()
                except Exception:
                    logger.exception("Failed to cancel DB maintenance task")

            # Give tasks a short moment to finish cancellation
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception:
                logger.debug("Exception while awaiting DB maintenance tasks cancellation")

    except Exception as e:
        logger.error(f"Error shutting down DB scheduler/tasks: {e}")

    await stop_news_cache_refresh_loop()
    logger.info("News cache refresh loop stopped")

app = FastAPI(
    title="LAMB",
    description="Learning Assistant Manger and Builder (LAMB) https://lamb-project.org",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.mount("/lamb", lamb_app)
app.include_router(creator_router, prefix="/creator", tags=["Creator"])


# --- Serve the new SvelteKit Frontend ---
# NOTE: This block is moved to the end of the file to ensure it runs AFTER all API routes.
# frontend_build_dir = "../frontend/build" # Relative to this file (backend/main.py)
# ... (rest of the original SPA block code is conceptually moved) ...
# --- End of original SPA block placeholder ---


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="LAMB API",
        version="0.1.0",
        description="Learning Assistants Manager and Builder (LAMB) https://lamb-project.org",
        routes=app.routes,
    )
    
    # Add lamb routes to the OpenAPI schema
    lamb_paths = {}
    for route in lamb_app.routes:
        if hasattr(route, 'path'):  # Check if it's a route with a path
            path = f"/lamb{route.path}"
            lamb_paths[path] = openapi_schema["paths"].get(route.path, {})
            
            # Only process if the route has methods
            if hasattr(route, 'methods'):
                for method in route.methods:
                    method_lower = method.lower()
                    lamb_paths[path][method_lower] = {
                        "summary": route.name if hasattr(route, 'name') else "",
                        "description": route.description if hasattr(route, 'description') else "",
                        "responses": getattr(route, 'responses', {}),
                        "tags": ["lamb"],
                    }
    
    openapi_schema["paths"].update(lamb_paths)
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Minimal CORS: allow everything (no credentials). Keep it tiny.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # Note: allow_credentials intentionally omitted (defaults to False) so '*' is valid.
)


# Add GZIP compression for better performance
# Removed because of buffering issues with streaming responses
# app.add_middleware(GZipMiddleware, minimum_size=1000)




def _get_assistant_capabilities(assistant: dict) -> dict:
    """
    Extract capabilities from assistant metadata

    Args:
        assistant: Assistant dictionary with api_callback field

    Returns:
        Capabilities dictionary with defaults
    """
    capabilities = {
        "vision": False,  # Default to False for backward compatibility
        "image_generation": False  # Support for image generation models
    }

    # Parse metadata from api_callback
    if assistant.get('api_callback'):
        try:
            metadata = json.loads(assistant['api_callback'])
            if metadata.get('capabilities'):
                capabilities.update(metadata['capabilities'])
        except json.JSONDecodeError:
            # Invalid JSON, keep defaults
            pass
        except Exception as e:
            # Any other error, keep defaults
            logger.warning(f"Error parsing assistant capabilities: {e}")

    return capabilities


@app.get("/v1/models")
@app.get("/models")
async def get_models(request: Request):
    """
    Get Available Models (Pipelines).

    Returns a list of available LAMB pipelines formatted similarly to the OpenAI models endpoint.
    This allows compatibility with tools expecting an OpenAI-like API structure.
    Requires API key authentication via the Authorization header.

    **Example curl:**
    ```bash
    curl -X GET "http://localhost:8000/v1/models" -H "Authorization: Bearer YOUR_API_KEY"
    ```

    **Example Response:**
    ```json
    {
      "object": "list",
      "data": [
        {
          "id": "model_id",
          "object": "model",
          "created": 1677609600,
          "owned_by": "lamb_v4"
        },
        {
          "id": "model_id",
          "object": "model",
          "created": 1677609600,
          "owned_by": "lamb_v4"
        }
      ]
    }
    ```
    """
  
    # Only return published assistants (not deleted, not unpublished)
    assistants = helper_get_all_assistants(filter_deleted=True, filter_unpublished=True)
    
    # Prepare response body
    response_body = {
        "object": "list",
        "data": [
            {
                "id": "lamb_assistant."+str(assistant["id"]),
                "object": "model",
                "created": int(time.time()),
                "owned_by": "lamb_v4",
                "parent": None,
                "capabilities": _get_assistant_capabilities(assistant)
            }
            for assistant in assistants
        ]
    }
    
    # Generate Request ID and set headers
    request_id = f"req_{uuid.uuid4()}"
    # CORSMiddleware will set the correct Access-Control-Allow-Origin header.
    # We only need to expose additional headers (already configured globally) and
    # include request-specific IDs here.
    headers = {
        "X-Request-Id": request_id,
        "OpenAI-Version": "2024-02-01"
    }

    # Return JSONResponse with body and headers
    return JSONResponse(content=response_body, headers=headers)

 


@app.get("/v1")
# @app.get("/") # Remove this conflicting root route
# async def get_status(): ... # Remove or move this function if it conflicts with SPA serving

# It's generally better to have a dedicated /status or /health endpoint
@app.get("/status")
async def get_api_status():
    """
    Get API Status.

    Returns a simple status message indicating the API is running.

    **Example curl:**
    ```bash
    curl -X GET "http://localhost:8000/status"
    ```

    **Example Response:**
    ```json
    {
      "status": true
    }
    ```
    """
    return {"status": True}




async def download_file(url: str, dest_folder: str):
    filename = os.path.basename(urlparse(url).path)
    if not filename.endswith(".py"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must point to a Python file",
        )

    file_path = os.path.join(dest_folder, filename)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to download file",
                )
            with open(file_path, "wb") as f:
                f.write(await response.read())

    return file_path


## This one is very important
## we need to keep this 
@app.post("/v1/pipelines/reload")
@app.post("/pipelines/reload")
async def reload_pipelines(user: str = Depends(get_current_user)):
    """
    Reload Pipelines.
 
    Triggers a reload of all pipelines from the `PIPELINES_DIR`. This involves shutting down existing pipelines
    and loading them again, picking up any changes in the pipeline files or `valves.json`.
    Requires API key authentication.

    **Example curl:**
    ```bash
    curl -X POST "http://localhost:8000/v1/pipelines/reload" -H "Authorization: Bearer YOUR_API_KEY"
    ```

    **Example Response:**
    ```json
    {
      "message": "Pipelines reloaded successfully."
    }
    ```
    """
    if user == API_KEY:
        await reload()
        return {"message": "Pipelines reloaded successfully."}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )




## LAMB: REMOVED FILTERS FROM API FOR NOW
#@app.post("/v1/{pipeline_id}/filter/inlet")
#@app.post("/{pipeline_id}/filter/inlet")
async def filter_inlet(pipeline_id: str, form_data: FilterForm):
    if pipeline_id not in app.state.PIPELINES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter {pipeline_id} not found",
        )

    try:
        pipeline = app.state.PIPELINES[form_data.body["model"]]
        if pipeline["type"] == "manifold":
            pipeline_id = pipeline_id.split(".")[0]
    except:
        pass

    pipeline = PIPELINE_MODULES[pipeline_id]

    try:
        if hasattr(pipeline, "inlet"):
            body = await pipeline.inlet(form_data.body, form_data.user)
            return body
        else:
            return form_data.body
    except Exception as e:
        logger.error(f"Error in pipeline inlet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{str(e)}",
        )


## LAMB: REMOVED FILTERS FROM API FOR NOW
#@app.post("/v1/{pipeline_id}/filter/outlet")
#@app.post("/{pipeline_id}/filter/outlet")
async def filter_outlet(pipeline_id: str, form_data: FilterForm):
    if pipeline_id not in app.state.PIPELINES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter {pipeline_id} not found",
        )

    try:
        pipeline = app.state.PIPELINES[form_data.body["model"]]
        if pipeline["type"] == "manifold":
            pipeline_id = pipeline_id.split(".")[0]
    except:
        pass

    pipeline = PIPELINE_MODULES[pipeline_id]

    try:
        if hasattr(pipeline, "outlet"):
            body = await pipeline.outlet(form_data.body, form_data.user)
            return body
        else:
            return form_data.body
    except Exception as e:
        logger.error(f"Error in pipeline outlet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{str(e)}",
        )




@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def generate_openai_chat_completion(request: Request):
    """
    Generate Chat Completion (OpenAI Compatible) with multimodal support.

    Supports both JSON and multipart form data for image uploads.
    """
    """
    Generate Chat Completion (OpenAI Compatible).

    Processes a chat request using a specified LAMB pipeline, mimicking the OpenAI chat completions endpoint.
    It accepts either a `messages` array or a `prompt` string. If `stream` is true, it returns Server-Sent Events.
    Requires API key authentication via the Authorization header if the backend is configured with one.

    **Example curl (Non-streaming):**
    ```bash
    curl -X POST "http://localhost:8000/v1/chat/completions" \\
         -H "Content-Type: application/json" \\
         -H "Authorization: Bearer YOUR_API_KEY" \\
         -d '{
           "model": "pipeline_1",
           "messages": [
             {"role": "user", "content": "Hello!"}
           ],
           "stream": false
         }'
    ```

    **Example curl (Streaming):**
    ```bash
    curl -X POST "http://localhost:8000/v1/chat/completions" \\
         -H "Content-Type: application/json" \\
         -H "Authorization: Bearer YOUR_API_KEY" \\
         -d '{
           "model": "pipeline_1",
           "messages": [
             {"role": "user", "content": "Tell me a short story."}
           ],
           "stream": true
         }' --no-buffer
    ```

    **Example Response (Non-streaming):**
    ```json
    {
      "id": "pipeline_1-...",
      "object": "chat.completion",
      "created": 1677609600,
      "model": "pipeline_1",
      "choices": [
        {
          "index": 0,
          "message": {
            "role": "assistant",
            "content": "Hello there! How can I help you today?"
          },
          "logprobs": null,
          "finish_reason": "stop"
        }
      ]
    }
    ```

    **Example Response (Streaming):**
    ```
    data: {"id":"pipeline_1-...","object":"chat.completion.chunk","created":1677609600,"model":"pipeline_1","choices":[{"index":0,"delta":{"role":"assistant"},"logprobs":null,"finish_reason":null}]}

    data: {"id":"pipeline_1-...","object":"chat.completion.chunk","created":1677609600,"model":"pipeline_1","choices":[{"index":0,"delta":{"content":"Once"},"logprobs":null,"finish_reason":null}]}

    data: {"id":"pipeline_1-...","object":"chat.completion.chunk","created":1677609600,"model":"pipeline_1","choices":[{"index":0,"delta":{"content":" upon"},"logprobs":null,"finish_reason":null}]}

    data: {"id":"pipeline_1-...","object":"chat.completion.chunk","created":1677609600,"model":"pipeline_1","choices":[{"index":0,"delta":{"content":" a time"},"logprobs":null,"finish_reason":null}]}

    data: {"id":"pipeline_1-...","object":"chat.completion.chunk","created":1677609600,"model":"pipeline_1","choices":[{"index":0,"delta":{},"logprobs":null,"finish_reason":"stop"}]}

    data: [DONE]

    ```
    """

    try:
        api_key = request.headers.get("Authorization")
        if api_key and api_key.startswith("Bearer "):
            api_key = api_key.split("Bearer ")[1].strip()
            logger.debug(f"API Key received: {api_key[:4]}...{api_key[-4:]}")
            if   api_key != API_KEY:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No API key provided in request headers",
            )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )

    # Log request details for debugging multimodal issues
    content_type = request.headers.get("content-type", "")
    multimodal_logger.debug("=== NEW CHAT COMPLETIONS REQUEST ===")
    multimodal_logger.debug(f"Method: {request.method}")
    multimodal_logger.debug(f"URL: {request.url}")
    multimodal_logger.debug(f"Content-Type: {content_type}")
    multimodal_logger.debug(f"Content-Length: {request.headers.get('content-length', 'N/A')}")
    multimodal_logger.debug(f"User-Agent: {request.headers.get('user-agent', 'N/A')}")
    multimodal_logger.debug(f"Authorization: Bearer {request.headers.get('authorization', '').replace('Bearer ', '')[:10]}...")
    multimodal_logger.debug(f"All Headers: {dict(request.headers)}")

    # Handle both JSON and multipart form data
    if "multipart/form-data" in content_type:
        multimodal_logger.info("=== MULTIPART REQUEST DETECTED ===")
        multimodal_logger.debug(f"Boundary: {content_type.split('boundary=')[1] if 'boundary=' in content_type else 'N/A'}")

        form = await request.form()
        multimodal_logger.info(f"Form fields count: {len(form)}")
        multimodal_logger.debug(f"Form field names: {list(form.keys())}")

        # Log details of each form field
        for field_name, field_value in form.items():
            if hasattr(field_value, 'filename') and field_value.filename:
                file_size = len(await field_value.read()) if hasattr(field_value, 'read') else 'N/A'
                await field_value.seek(0)  # Reset for later reading
                multimodal_logger.info(f"FILE field '{field_name}': filename={field_value.filename}, size={file_size}")
            else:
                field_content = str(field_value)
                multimodal_logger.debug(f"TEXT field '{field_name}': length={len(field_content)}, preview={field_content[:200]}{'...' if len(field_content) > 200 else ''}")

        # Extract JSON data from form
        json_data = form.get("data") or form.get("messages")
        if json_data:
            if hasattr(json_data, 'read'):  # File-like object
                json_str = (await json_data.read()).decode()
            else:  # String
                json_str = str(json_data)
            multimodal_logger.info(f"JSON data from form field: {json_str}")
            form_data = completions_get_form_data(json_str)
        else:
            # Try to reconstruct from individual fields
            model = form.get("model")
            messages_json = form.get("messages")
            stream = form.get("stream", False)

            multimodal_logger.debug(f"Individual fields: model={model}, messages={messages_json is not None}, stream={stream}")

            if messages_json:
                if hasattr(messages_json, 'read'):
                    messages_str = (await messages_json.read()).decode()
                else:
                    messages_str = str(messages_json)
                messages = json.loads(messages_str)
                multimodal_logger.debug(f"Parsed messages: {messages}")
            else:
                messages = []

            # Handle file uploads - convert to base64 data URLs
            files = []
            for field_name, field_value in form.items():
                if hasattr(field_value, 'filename') and field_value.filename:
                    multimodal_logger.info(f"Processing uploaded file: {field_value.filename}")
                    file_content = await field_value.read()
                    import base64
                    base64_data = base64.b64encode(file_content).decode()

                    # Determine MIME type
                    if field_value.filename.lower().endswith(('.jpg', '.jpeg')):
                        mime_type = "image/jpeg"
                    elif field_value.filename.lower().endswith('.png'):
                        mime_type = "image/png"
                    elif field_value.filename.lower().endswith('.gif'):
                        mime_type = "image/gif"
                    elif field_value.filename.lower().endswith('.webp'):
                        mime_type = "image/webp"
                    else:
                        mime_type = "application/octet-stream"

                    data_url = f"data:{mime_type};base64,{base64_data}"
                    multimodal_logger.debug(f"Converted to data URL: {data_url[:100]}...")

                    # Add as image content to the last user message
                    if messages and messages[-1].get('role') == 'user':
                        content = messages[-1].get('content', '')
                        if isinstance(content, str):
                            # Convert to multimodal format
                            messages[-1]['content'] = [
                                {'type': 'text', 'text': content},
                                {'type': 'image_url', 'image_url': {'url': data_url}}
                            ]
                            multimodal_logger.info("Converted text message to multimodal format")
                        elif isinstance(content, list):
                            # Add to existing multimodal content
                            messages[-1]['content'].append({
                                'type': 'image_url',
                                'image_url': {'url': data_url}
                            })
                            multimodal_logger.info("Added image to existing multimodal message")

            form_data_dict = {
                'model': model,
                'messages': messages,
                'stream': stream
            }
            multimodal_logger.debug(f"Final form_data_dict: {json.dumps(form_data_dict, indent=2)}")
            form_data = completions_get_form_data(json.dumps(form_data_dict))
    else:
        # Standard JSON processing
        multimodal_logger.info("=== JSON REQUEST DETECTED ===")
        body = await request.body()
        body_str = body.decode()
        multimodal_logger.info(f"Raw body length: {len(body_str)} bytes")
        multimodal_logger.debug(f"Raw body content: {body_str}")
        form_data = completions_get_form_data(body_str)
    
    # Extract and validate fields
    model = form_data.get('model')
    messages = form_data.get('messages', [])
    stream = form_data.get('stream', False)

    multimodal_logger.info("Final parsed data:")
    multimodal_logger.info(f"Model: {model}")
    multimodal_logger.info(f"Stream: {stream}")
    multimodal_logger.info(f"Messages count: {len(messages)}")
    for i, msg in enumerate(messages):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        content_type = type(content).__name__
        if isinstance(content, list):
            item_types = [item.get('type', 'unknown') for item in content[:3]]
            content_preview = f"[{len(content)} items: {', '.join(item_types)}{'...' if len(content) > 3 else ''}]"
        else:
            content_preview = f"'{str(content)[:100]}{'...' if len(str(content)) > 100 else ''}'"
        multimodal_logger.info(f"Message {i}: role={role}, content_type={content_type}, content={content_preview}")

    # Create a form_data object that mimics the Pydantic model
    # Handle both text and multimodal message formats
    class DummyMessage:
        def __init__(self, role, content):
            self.role = role
            self.content = content  # Can be string (text) or list (multimodal)
        def model_dump(self):
            return {"role": self.role, "content": self.content}

    class DummyFormData:
        def __init__(self, model, messages, stream):
            self.model = model
            # Preserve original message structure (multimodal messages have list content)
            self.messages = [DummyMessage(m["role"], m["content"]) for m in messages]
            self.stream = stream
        def model_dump(self):
            return {
                "model": self.model,
                "messages": [m.model_dump() for m in self.messages],
                "stream": self.stream
            }

    form_data = DummyFormData(model, messages, stream)

    try:
        assistant_id = helper_get_assistant_id(form_data.model)
        logger.info(f"Processing assistant: {assistant_id}")

        # Define common headers
        request_id = f"req_{uuid.uuid4()}"
        processing_ms = str(random.randint(150, 450))
        common_headers = {
            "X-Request-Id": request_id,
            "X-RateLimit-Limit-Requests": "1000",
            "X-RateLimit-Remaining-Requests": "999",
            "X-RateLimit-Reset-Requests": "60s",
            "OpenAI-Organization": "lamb-project.org",
            "OpenAI-Processing-MS": processing_ms,
            "OpenAI-Version": "2024-02-01",
            "Access-Control-Expose-Headers": (
                "X-Request-Id, X-RateLimit-Limit-Requests, "
                "X-RateLimit-Remaining-Requests, X-RateLimit-Reset-Requests, "
                "OpenAI-Organization, OpenAI-Processing-MS, OpenAI-Version"
            ),
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }

        # Directly call and await run_lamb_assistant
        multimodal_logger.info(f"Calling run_lamb_assistant with assistant_id={assistant_id}")
        request_data = form_data.model_dump()
        multimodal_logger.debug(f"Request data being sent: {json.dumps(request_data, indent=2)[:1000]}...")

        response = await run_lamb_assistant(
            request=request_data,
            assistant=assistant_id,
            headers=common_headers # Pass headers to the assistant runner
        )

        multimodal_logger.info(f"Assistant returned response, type: {type(response)}")
        if hasattr(response, 'body'):
            multimodal_logger.debug(f"Response has body, length: {len(response.body) if response.body else 0}")
        elif isinstance(response, dict):
            multimodal_logger.debug(f"Response is dict with keys: {list(response.keys())}")
        return response

    except Exception as e:
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        logger.error(f"Error occurred in chat completions: {error_detail}")
        # Ensure the error response is proper JSON
        return Response(
            content=json.dumps({"error": error_detail}),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, # Or 500 if it's an internal server error
            media_type="application/json"
        )

# --- Serve the new SvelteKit Frontend (MOVED HERE) ---
frontend_build_dir = "../frontend/build" # Relative to this file (backend/main.py)
abs_frontend_build_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), frontend_build_dir))
frontend_index_html = os.path.join(abs_frontend_build_dir, 'index.html')

if os.path.isdir(abs_frontend_build_dir):
    logger.info(f"Frontend build directory found: {abs_frontend_build_dir}")

    # 1. Mount specific directories generated by SvelteKit build (e.g., app, img)
    # Adjust '/app' and 'app' based on your actual build output structure
    svelte_app_dir = os.path.join(abs_frontend_build_dir, "app")
    if os.path.isdir(svelte_app_dir):
        logger.info(f"Mounting SvelteKit assets from: {svelte_app_dir} at /app")
        app.mount("/app", StaticFiles(directory=svelte_app_dir), name="svelte_assets")
    else:
        logger.warning(f"SvelteKit app directory not found: {svelte_app_dir}")

    svelte_img_dir = os.path.join(abs_frontend_build_dir, "img")
    if os.path.isdir(svelte_img_dir):
        logger.info(f"Mounting images from: {svelte_img_dir} at /img")
        app.mount("/img", StaticFiles(directory=svelte_img_dir), name="svelte_images")
    else:
        logger.info(f"Image directory not found, skipping mount: {svelte_img_dir}")

    # RESTORE specific routes for root files
    favicon_path = os.path.join(abs_frontend_build_dir, "favicon.png")
    if os.path.isfile(favicon_path):
        @app.get("/favicon.png", include_in_schema=False)
        async def get_favicon():
            return FileResponse(favicon_path)
        logger.info(f"Serving favicon.png from: {favicon_path}")
    else:
        logger.warning(f"favicon.png not found: {favicon_path}")

    config_js_path = os.path.join(abs_frontend_build_dir, "config.js")
    if os.path.isfile(config_js_path):
        @app.get("/config.js", include_in_schema=False)
        async def get_config_js():
            # Ensure correct MIME type for JavaScript
            return FileResponse(config_js_path, media_type="application/javascript")
        logger.info(f"Serving config.js from: {config_js_path}")
    else:
        logger.warning(f"config.js not found: {config_js_path}")

    # 3. SPA Catch-all Route (Defined last to avoid overriding API routes)
    if os.path.isfile(frontend_index_html):
        logger.info(f"SPA index.html found: {frontend_index_html}. Enabling catch-all route.")
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(request: Request, full_path: str):
            # Skip API routes - let FastAPI handle these
            # Check against all known API prefixes
            api_prefixes = (
                'v1/', 'models', 'status', 'pipelines/', 'chat/', # General API routes
                'creator/',                                      # Creator interface routes
                'lamb/',                                         # LAMB core routes
                'docs', 'openapi.json', 'redoc'                   # FastAPI docs routes
            )
            # Also check for specific static files we serve from root
            static_files = ('favicon.png', 'config.js')

            if full_path.startswith(api_prefixes) or full_path in static_files:
                # Let FastAPI handle this path; if no specific route matches, it will 404.
                logger.debug(f"SPA Catch-all: Path '{full_path}' is an API route or static file, letting FastAPI handle.")
                # If FastAPI finds no matching route, it will handle the 404.
                # We need to explicitly return a 404 here if the intention is *not* to serve index.html
                # for unmatched API-like or static file paths.
                return Response(content=f"Resource not found at '{full_path}'", status_code=404)


            # Check if the path looks like a file extension commonly used for assets served by static mounts
            # e.g. /app/xxx.js, /img/yyy.png
            if '.' in full_path.split('/')[-1] and not full_path.endswith(".html"):
                 # Check if it's likely served by '/app' or '/img' mounts
                 if full_path.startswith(('/app/', '/img/')):
                      # Let the StaticFiles mount handle this (FastAPI does this automatically if the route isn't matched)
                      logger.debug(f"SPA Catch-all: Path '{full_path}' looks like a mounted asset, letting StaticFiles handle.")
                      # Return 404 here because if we reached this point, StaticFiles didn't find it.
                      return Response(content=f"Static asset not found at '{full_path}'", status_code=404)
                 else:
                      # It looks like a file but isn't under a known static mount or API prefix
                      logger.debug(f"SPA Catch-all: Path '{full_path}' looks like an unhandled file, returning 404.")
                      return Response(content=f"File not found at '{full_path}'", status_code=404)
            else:
                # If the path doesn't look like a static file asset (or is .html) and wasn't an API/static path,
                # assume it's an SPA route and serve the main index.html file.
                logger.debug(f"SPA Catch-all triggered for path: {full_path}. Serving index.html")
                return FileResponse(frontend_index_html)
    else:
        logger.error(f"index.html not found in frontend build directory: {frontend_index_html}")

else:
    logger.warning(f"Frontend build directory not found, SPA serving disabled: {abs_frontend_build_dir}")
    # Optional: Add a simple fallback if the whole build dir is missing
    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_build_missing(full_path: str):
         return Response(content="Frontend build directory not found. Build the frontend application.", status_code=404)

# --- End of MOVED Frontend Serve Block ---