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
import logging
import time
import json
import uuid
import sys
import subprocess
import traceback
import random

from config import API_KEY, PIPELINES_DIR
from creator_interface.main import router as creator_router

logging.basicConfig(level=logging.WARNING)

app = FastAPI(title="LAMB", description="Learning Assistant Manger and Builder (LAMB) https://lamb-project.org", version="0.1.0", docs_url="/docs", openapi_url="/openapi.json")

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
  
    assistants = helper_get_all_assistants(filter_deleted=True)
    
    # Filter out deleted assistants
    
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
            }
            for assistant in assistants
        ]
    }
    logging.info("Models: "+str(response_body))

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
        print(e)
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
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{str(e)}",
        )




@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def generate_openai_chat_completion(request: Request):
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
            print(f"API Key received: {api_key[:4]}...{api_key[-4:]}")
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
        print(f"Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )

    body = await request.body()
    body_str = body.decode()
    form_data=completions_get_form_data(body_str)
    
    # Extract and validate fields
    model = form_data.get('model')
    messages = form_data.get('messages', [])
    stream = form_data.get('stream', False)
    

    # Create a form_data object that mimics the Pydantic model
    class DummyMessage:
        def __init__(self, role, content):
            self.role = role
            self.content = content
        def model_dump(self):
            return {"role": self.role, "content": self.content}

    class DummyFormData:
        def __init__(self, model, messages, stream):
            self.model = model
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
        print(f"Processing assistant: {assistant_id}")

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
        # Pass the request body (form_data.model_dump()), assistant_id, and headers
        response = await run_lamb_assistant(
            request=form_data.model_dump(),
            assistant=assistant_id,
            headers=common_headers # Pass headers to the assistant runner
        )
        return response

    except Exception as e:
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print("\nError occurred:")
        print(error_detail)
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
    print(f"Frontend build directory found: {abs_frontend_build_dir}")

    # 1. Mount specific directories generated by SvelteKit build (e.g., app, img)
    # Adjust '/app' and 'app' based on your actual build output structure
    svelte_app_dir = os.path.join(abs_frontend_build_dir, "app")
    if os.path.isdir(svelte_app_dir):
        print(f"Mounting SvelteKit assets from: {svelte_app_dir} at /app")
        app.mount("/app", StaticFiles(directory=svelte_app_dir), name="svelte_assets")
    else:
        print(f"Warning: SvelteKit app directory not found: {svelte_app_dir}")

    svelte_img_dir = os.path.join(abs_frontend_build_dir, "img")
    if os.path.isdir(svelte_img_dir):
        print(f"Mounting images from: {svelte_img_dir} at /img")
        app.mount("/img", StaticFiles(directory=svelte_img_dir), name="svelte_images")
    else:
        print(f"Info: Image directory not found, skipping mount: {svelte_img_dir}")

    # RESTORE specific routes for root files
    favicon_path = os.path.join(abs_frontend_build_dir, "favicon.png")
    if os.path.isfile(favicon_path):
        @app.get("/favicon.png", include_in_schema=False)
        async def get_favicon():
            return FileResponse(favicon_path)
        print(f"Serving favicon.png from: {favicon_path}")
    else:
        print(f"Warning: favicon.png not found: {favicon_path}")

    config_js_path = os.path.join(abs_frontend_build_dir, "config.js")
    if os.path.isfile(config_js_path):
        @app.get("/config.js", include_in_schema=False)
        async def get_config_js():
            # Ensure correct MIME type for JavaScript
            return FileResponse(config_js_path, media_type="application/javascript")
        print(f"Serving config.js from: {config_js_path}")
    else:
        print(f"Warning: config.js not found: {config_js_path}")

    # 3. SPA Catch-all Route (Defined last to avoid overriding API routes)
    if os.path.isfile(frontend_index_html):
        print(f"SPA index.html found: {frontend_index_html}. Enabling catch-all route.")
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
                print(f"SPA Catch-all: Path '{full_path}' is an API route or static file, letting FastAPI handle.")
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
                      print(f"SPA Catch-all: Path '{full_path}' looks like a mounted asset, letting StaticFiles handle.")
                      # Return 404 here because if we reached this point, StaticFiles didn't find it.
                      return Response(content=f"Static asset not found at '{full_path}'", status_code=404)
                 else:
                      # It looks like a file but isn't under a known static mount or API prefix
                      print(f"SPA Catch-all: Path '{full_path}' looks like an unhandled file, returning 404.")
                      return Response(content=f"File not found at '{full_path}'", status_code=404)
            else:
                # If the path doesn't look like a static file asset (or is .html) and wasn't an API/static path,
                # assume it's an SPA route and serve the main index.html file.
                print(f"SPA Catch-all triggered for path: {full_path}. Serving index.html")
                return FileResponse(frontend_index_html)
    else:
        print(f"Error: index.html not found in frontend build directory: {frontend_index_html}")

else:
    print(f"Frontend build directory not found, SPA serving disabled: {abs_frontend_build_dir}")
    # Optional: Add a simple fallback if the whole build dir is missing
    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_build_missing(full_path: str):
         return Response(content="Frontend build directory not found. Build the frontend application.", status_code=404)

# --- End of MOVED Frontend Serve Block ---