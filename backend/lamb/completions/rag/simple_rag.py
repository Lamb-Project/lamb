import json
import os
import requests
from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="RAG")


def rag_processor(
    messages: List[Dict[str, Any]],
    assistant: Assistant = None,
    request: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Synchronous RAG processor that returns context from the knowledge base server
    using the last user message as a query.
    """
    logger.info("Using simple_rag processor with assistant: %s",
                assistant.name if assistant else "None")

    # Log the messages passed to the processor
    logger.debug("=== MESSAGES ===")
    try:
        logger.debug(f"Messages count: {len(messages)}")
        logger.debug(f"Messages content: {json.dumps(messages, indent=2)}")
    except Exception as e:
        logger.debug(f"Error logging messages: {str(e)}")
        logger.debug(f"Messages type: {type(messages)}")
        for i, msg in enumerate(messages):
            logger.debug(f"Message {i+1}: {msg}")
    logger.debug("=== END MESSAGES ===")

    # Create a JSON-serializable dictionary from the assistant
    assistant_dict = {}
    if assistant:
        # Use a simple approach with a set of known fields
        for key in ['id', 'name', 'description', 'system_prompt', 'prompt_template', 'RAG_collections', 'RAG_Top_k', 'published', 'published_at']:
            if hasattr(assistant, key):
                try:
                    value = getattr(assistant, key)
                    # Check if the value is JSON serializable
                    json.dumps({key: value})
                    assistant_dict[key] = value
                except (TypeError, OverflowError, Exception) as e:
                    logger.debug(f"Cannot serialize {key}: {str(e)}")
                    assistant_dict[key] = str(value)

    # Log the assistant dictionary
    logger.debug(
        f"Assistant Dictionary: {json.dumps(assistant_dict, indent=2)}")
    # Extract the last user message
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break

    logger.debug(f"Last user message: {last_user_message}")

    # Check if we have what we need to make a query
    if not assistant or not hasattr(assistant, 'RAG_collections') or not assistant.RAG_collections:
        error_message = "No RAG collections specified in the assistant configuration"
        logger.error(f"RAG processing failed: {error_message}")
        return {
            "context": error_message,
            "sources": [],
            "assistant_data": assistant_dict
        }

    if not last_user_message:
        error_message = "No user message found to use for the query"
        logger.error(f"RAG processing failed: {error_message}")
        return {
            "context": error_message,
            "sources": [],
            "assistant_data": assistant_dict
        }

    # Parse the collection IDs from RAG_collections
    collections = assistant.RAG_collections.split(',')
    if not collections:
        error_message = "RAG_collections is empty or improperly formatted"
        logger.error(f"RAG processing failed: {error_message}")
        return {
            "context": error_message,
            "sources": [],
            "assistant_data": assistant_dict
        }

    # Clean up collection IDs
    collections = [cid.strip() for cid in collections if cid.strip()]
    logger.info(f"Found {len(collections)} collections: {collections}")

    # Get the top_k value or use a default
    top_k = getattr(assistant, 'RAG_Top_k', 3)

    # Setup for KB server API requests - use organization-specific configuration
    KB_SERVER_URL = None
    KB_API_KEY = None
    org_name = "Unknown"
    config_source = "env_vars"

    try:
        # Get organization-specific KB configuration
        config_resolver = OrganizationConfigResolver(assistant.owner)
        org_name = config_resolver.organization.get('name', 'Unknown')
        kb_config = config_resolver.get_knowledge_base_config()

        if kb_config:
            KB_SERVER_URL = kb_config.get("server_url")
            KB_API_KEY = kb_config.get("api_token")
            config_source = "organization"
            logger.info(
                f"Using organization: '{org_name}' (owner: {assistant.owner})")
            logger.info(
                f"Using organization KB config for {assistant.owner} (org: {org_name})")
        else:
            logger.warning(
                f"No config found for organization '{org_name}', falling back to environment variables")
            logger.warning(
                f"No KB config found for {assistant.owner} (org: {org_name}), falling back to env vars")
    except Exception as e:
        logger.error(
            f"Error getting organization config for {assistant.owner}: {e}")
        logger.error(
            f"Error getting org KB config for {assistant.owner}: {e}, falling back to env vars")

    # Fallback to environment variables
    if not KB_SERVER_URL:
        import config
        KB_SERVER_URL = os.getenv('LAMB_KB_SERVER')
        if not KB_SERVER_URL:
            raise ValueError("LAMB_KB_SERVER environment variable is required")
        KB_API_KEY = os.getenv(
            'LAMB_KB_SERVER_TOKEN') or config.LAMB_BEARER_TOKEN
        logger.info(
            f"Using environment variable configuration (fallback for {assistant.owner})")
        logger.info("Using environment variable KB configuration")

    logger.info(
        f"Server: {KB_SERVER_URL} | Config: {config_source} | Organization: {org_name} | Collections: {len(collections)}")

    headers = {
        "Authorization": f"Bearer {KB_API_KEY}",
        "Content-Type": "application/json"
    }

    # Prepare the payload (same for all collections)
    payload = {
        "query_text": last_user_message,
        "top_k": top_k,
        "threshold": 0.0,
        "plugin_params": {}
    }

    # Dictionary to store all responses
    all_responses = {}
    any_success = False

    try:
        # Query each collection
        for collection_id in collections:
            logger.debug(f"Querying collection: {collection_id}")

            url = f"{KB_SERVER_URL}/collections/{collection_id}/query"

            logger.debug(f"URL: {url}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            try:
                # Make the request to the KB server
                response = requests.post(url, headers=headers, json=payload)

                logger.debug(f"Status Code: {response.status_code}")

                if response.status_code == 200:
                    # Parse the JSON response
                    raw_response = response.json()
                    # Log the response summary
                    logger.debug(
                        f"Response Summary: {len(raw_response.get('documents', []))} documents returned")
                    logger.debug(
                        f"Raw Response: {json.dumps(raw_response, indent=2)}")

                    # Store the response
                    all_responses[collection_id] = {
                        "status": "success",
                        "data": raw_response
                    }
                    any_success = True
                else:
                    error_text = response.text
                    logger.error(f"KB server error: {error_text}")
                    all_responses[collection_id] = {
                        "status": "error",
                        "error": f"Status code: {response.status_code}, Message: {error_text}"
                    }
            except Exception as collection_error:
                error_msg = f"Error querying collection {collection_id}: {str(collection_error)}"
                logger.error(error_msg)
                all_responses[collection_id] = {
                    "status": "error",
                    "error": error_msg
                }

            logger.debug("Query completed")

        # Log a summary of all responses
        logger.debug("Summary of all queries")
        sources = []
        contexts = []

        for cid, result in all_responses.items():
            status = result["status"]
            if status == "success":
                documents = result["data"].get("documents", [])
                doc_count = len(documents)
                logger.info(
                    f"Collection {cid}: {status} - {doc_count} documents")

                # Extract file_urls and create source URLs
                # Supports both legacy (file_url) and new (original_file_url, markdown_file_url) metadata
                for doc in documents:
                    if "metadata" in doc:
                        metadata = doc["metadata"]

                        # Determine the best source URL (prefer remote sources like YouTube with timestamps)
                        source_url = None
                        original_url = None
                        markdown_url = None
                        images_folder = None
                        remote_source_url = None

                        # Remote source URL (YouTube videos with timestamps, etc.)
                        # This takes priority as it contains the exact timestamp
                        if "source_url" in metadata:
                            remote_source_url = metadata["source_url"]

                        # New metadata fields from markitdown_plus_ingest plugin
                        if "original_file_url" in metadata:
                            original_url = f"{KB_SERVER_URL}{metadata['original_file_url']}"
                        if "markdown_file_url" in metadata:
                            markdown_url = f"{KB_SERVER_URL}{metadata['markdown_file_url']}"
                        if "images_folder_url" in metadata:
                            images_folder = f"{KB_SERVER_URL}{metadata['images_folder_url']}"

                        # Legacy file_url field
                        if "file_url" in metadata:
                            source_url = f"{KB_SERVER_URL}{metadata['file_url']}"

                        # Priority: remote_source_url (YouTube) > original_file_url > file_url
                        main_url = remote_source_url or original_url or source_url

                        if main_url:
                            source_entry = {
                                "title": metadata.get("filename", metadata.get("original_filename", "Unknown")),
                                "url": main_url,
                                "similarity": doc.get("similarity", 0)
                            }
                            # Include additional URLs from new plugins
                            if original_url:
                                source_entry["original_url"] = original_url
                            if markdown_url:
                                source_entry["markdown_url"] = markdown_url
                            if images_folder:
                                source_entry["images_folder"] = images_folder
                            # Include chunk metadata if available
                            if "chunk_index" in metadata:
                                source_entry["chunk_index"] = metadata["chunk_index"]
                            if "page" in metadata:
                                source_entry["page"] = metadata["page"]

                            sources.append(source_entry)

                    # Add the document content to contexts
                    if "data" in doc:
                        contexts.append(doc["data"])
            else:
                logger.warning(
                    f"Collection {cid}: {status} - {result.get('error', 'Unknown error')}")

        logger.info(f"Extracted {len(sources)} source URLs")

        # Combine contexts into a single string
        combined_context = "\n\n".join(contexts) if contexts else ""

        # Return all responses with sources
        return {
            "context": combined_context,
            "sources": sources,
            "assistant_data": assistant_dict,
            "raw_responses": all_responses
        }

    except Exception as e:
        error_message = f"Error in overall RAG process: {str(e)}"
        logger.error(error_message)
        print(f"Error: {error_message}")
        return {
            "context": error_message,
            "sources": [],
            "assistant_data": assistant_dict,
            "raw_responses": all_responses if all_responses else None
        }
