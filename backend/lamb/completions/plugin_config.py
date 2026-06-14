import json
import logging
from typing import Dict, Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def parse_plugin_config(assistant_details) -> Dict[str, str]:
    """
    Parse the metadata field from the assistant record.
    Expects a JSON string with keys: prompt_processor, connector, llm, rag_processor.
    """
    try:
        # Handle empty string case by defaulting to an empty JSON object
        if not assistant_details.metadata or assistant_details.metadata.strip() == '':
            logger.warning(f"Empty metadata for assistant {assistant_details.id}, using default values")
            callback = {}
        else:
            callback = json.loads(assistant_details.metadata)
    except Exception as e:
        logger.error(f"Failed to parse metadata for assistant {assistant_details.id}: {e}")
        raise HTTPException(status_code=400, detail=f"Assistant metadata cannot be parsed: {e}")

    # Set default values if keys are missing
    defaults = {
        "prompt_processor": "default",
        "connector": "openai",
        "llm": "gpt-4",
        "rag_processor": "",
        "document_rag": ""
    }
    
    # Apply defaults for missing keys
    for key in defaults:
        if key not in callback:
            callback[key] = defaults[key]
            logger.info(f"Using default {key}={defaults[key]} for assistant {assistant_details.id}")

    return callback


def process_completion_request(request: Dict[str, Any], assistant_details: Any, plugin_config: Dict[str, str], rag_context: Any, pps: Dict[str, Any], document_context=None) -> Any:
    """
    Process the prompt using the specified prompt processor and return prepared messages.
    """
    logger.info("Processing completion request")
    messages = pps[plugin_config["prompt_processor"]](request=request, assistant=assistant_details, rag_context=rag_context, document_context=document_context)
    logger.debug(f"Processed messages: {messages}")
    return messages
