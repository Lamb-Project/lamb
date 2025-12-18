import os
from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
import json
import logging

# Set up logger
logger = logging.getLogger('lamb.completions.rag.single_file_rag')
logger.setLevel(logging.WARNING)

def rag_processor(
    messages: List[Dict[str, Any]],
    assistant: Assistant = None,
    request: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    A RAG processor that returns the content of a single file as context.
    The file path should be specified in the assistant's metadata field under 'file_path'.
    The file path is relative to the project's static/public folder.
    """
    logger.debug(f"Starting single_file_rag processor with assistant: {assistant.id if assistant else 'None'}")
    
    if not assistant:
        logger.warning("No assistant provided")
        return {
            "context": "",
            "sources": []
        }

    try:
        # Parse the metadata to get the file path
        logger.debug(f"Full metadata content: {assistant.metadata}")
        
        # Handle empty metadata
        if not assistant.metadata or assistant.metadata.strip() == '':
            logger.warning(f"Empty metadata for assistant {assistant.id if assistant else 'unknown'}")
            config = {}
        else:
            config = json.loads(assistant.metadata)
            
        logger.debug(f"Parsed metadata config: {config}")
        file_path = config.get('file_path')
        logger.debug(f"Extracted file_path from metadata: {file_path}")
        
        if not file_path:
            logger.warning("No file_path found in metadata")
            return {
                "context": "",
                "sources": []
            }

        # Construct absolute path from project's static/public folder
        base_path = os.path.join('static', 'public')
        full_path = os.path.join(base_path, file_path)
        logger.debug(f"Base path: {base_path}")
        logger.debug(f"Full path: {full_path}")

        # Ensure the path doesn't escape the static/public directory
        if '..' in file_path or not os.path.abspath(full_path).startswith(os.path.abspath(base_path)):
            logger.error(f"Security check failed - path attempts to escape base directory: {full_path}")
            return {
                "context": "Error: Invalid file path",
                "sources": []
            }

        # Check if file exists
        if not os.path.exists(full_path):
            logger.error(f"File not found: {full_path}")
            return {
                "context": f"Error: File not found: {file_path}",
                "sources": []
            }

        # Log file stats
        file_stats = os.stat(full_path)
        logger.debug(f"File stats - size: {file_stats.st_size} bytes, last modified: {file_stats.st_mtime}")

        # Read the file content if it exists
        logger.debug(f"Reading file content from: {full_path}")
        with open(full_path, 'r', encoding='utf-8') as file:
            content = file.read()
            logger.debug(f"Successfully read {len(content)} characters from file")
                
        return {
            "context": content,
            "sources": [{
                "source": file_path,
                "content": content,
                "score": 1.0
            }]
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse metadata JSON: {e}")
        return {
            "context": f"Error processing file: Invalid metadata format",
            "sources": []
        }
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        return {
            "context": f"Error processing file: {str(e)}",
            "sources": []
        } 