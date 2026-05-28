import os
from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
import json
import logging
import httpx

logger = logging.getLogger('lamb.completions.rag.single_file_rag')
logger.setLevel(logging.WARNING)


def rag_processor(
    messages: List[Dict[str, Any]],
    assistant: Assistant = None,
    request: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    empty_result = {"context": "", "sources": []}

    if assistant is None:
        logger.warning("No assistant provided")
        return empty_result

    try:
        metadata = json.loads(assistant.metadata) if assistant.metadata else {}
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid metadata JSON")
        return empty_result

    library_id = metadata.get("library_id")
    item_id = metadata.get("item_id")
    file_path = metadata.get("file_path")

    if library_id and item_id:
        return _fetch_from_library_manager(library_id, item_id)
    elif file_path:
        return _read_from_static_file(file_path)
    else:
        logger.warning("No library_id+item_id or file_path in metadata")
        return empty_result


def _fetch_from_library_manager(library_id: str, item_id: str) -> Dict[str, Any]:
    empty_result = {"context": "", "sources": []}

    lm_url = os.environ.get("LAMB_LIBRARY_SERVER", "").rstrip("/")
    lm_token = os.environ.get("LAMB_LIBRARY_TOKEN", "")

    if not lm_url or not lm_token:
        logger.warning("LAMB_LIBRARY_SERVER or LAMB_LIBRARY_TOKEN not configured")
        return empty_result

    url = f"{lm_url}/libraries/{library_id}/items/{item_id}/content"
    headers = {"Authorization": f"Bearer {lm_token}"}

    try:
        response = httpx.get(url, params={"format": "markdown"}, headers=headers, timeout=30.0)
        if response.status_code == 200:
            content = response.text
            return {
                "context": content,
                "sources": [{
                    "title": "Library Document",
                    "url": f"/docs/{library_id}/{item_id}",
                    "similarity": 1.0,
                }],
            }
        else:
            logger.warning(
                f"Library Manager returned {response.status_code} for "
                f"library={library_id} item={item_id}"
            )
            return empty_result
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch from Library Manager: {e}")
        return empty_result


def _read_from_static_file(file_path: str) -> Dict[str, Any]:
    base_path = os.path.join('static', 'public')
    full_path = os.path.join(base_path, file_path)

    if '..' in file_path or not os.path.abspath(full_path).startswith(os.path.abspath(base_path)):
        error_msg = f"Error: Invalid file path: {file_path}"
        logger.warning(f"Path traversal attempt detected: {file_path}")
        return {"context": error_msg, "sources": []}

    if not os.path.exists(full_path):
        error_msg = f"Error: File not found: {file_path}"
        logger.warning(f"File not found: {full_path}")
        return {"context": error_msg, "sources": []}

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {
            "context": content,
            "sources": [{
                "title": os.path.basename(file_path),
                "url": f"/static/public/{file_path}",
                "similarity": 1.0,
            }],
        }
    except Exception as e:
        error_msg = f"Error reading file {file_path}: {str(e)}"
        logger.warning(f"Error reading file {full_path}: {e}")
        return {"context": error_msg, "sources": []}
