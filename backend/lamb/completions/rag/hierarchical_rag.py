import json
import os
import requests
from typing import Dict, Any, List
from lamb.lamb_classes import Assistant
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="RAG")

async def _generate_optimal_query(messages: List[Dict[str, Any]], assistant: Assistant) -> str:
    """
    Use the small-fast-model to analyze the full conversation and generate
    an optimal query for RAG retrieval.
    
    Args:
        messages: Full conversation history
        assistant: Assistant object with owner information
        
    Returns:
        Optimized query string for RAG retrieval
    """
    try:
        from lamb.completions.small_fast_model_helper import invoke_small_fast_model, is_small_fast_model_configured
        
        # Check if small-fast-model is configured
        if not is_small_fast_model_configured(assistant.owner):
            logger.info("Small-fast-model not configured, using last user message as query")
            # Fallback: return last user message
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        # Extract text from multimodal content
                        text_parts = [item.get('text', '') for item in content if item.get('type') == 'text']
                        return ' '.join(text_parts)
                    return content
            return ""
        
        # Build a condensed conversation history (last 5 turns max to save tokens)
        conversation_summary = []
        recent_messages = messages[-10:] if len(messages) > 10 else messages
        
        for msg in recent_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            # Handle multimodal content
            if isinstance(content, list):
                text_parts = [item.get('text', '') for item in content if item.get('type') == 'text']
                content = ' '.join(text_parts)
            
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            
            conversation_summary.append(f"{role.upper()}: {content}")
        
        conversation_text = "\n".join(conversation_summary)
        
        # Create prompt for query optimization
        system_prompt = """You are a query optimization assistant for a RAG (Retrieval-Augmented Generation) system.

Your task is to analyze the conversation history and generate an optimal search query that will retrieve the most relevant documents from a knowledge base.

Guidelines:
1. Consider the full conversation context, not just the last message
2. Identify the core information need
3. Include relevant keywords and concepts
4. If the conversation references previous topics, incorporate them
5. Make the query specific and focused
6. Keep the query concise (1-3 sentences max)
7. Return ONLY the optimized query, nothing else

Example:
CONVERSATION:
USER: What is photosynthesis?
ASSISTANT: Photosynthesis is the process by which plants convert light energy into chemical energy.
USER: How does it work in detail?

OPTIMAL QUERY: detailed explanation of photosynthesis process mechanism light energy conversion chlorophyll

Now generate the optimal query for the following conversation:"""

        user_prompt = f"""CONVERSATION:
{conversation_text}

OPTIMAL QUERY:"""

        # Invoke small-fast-model
        enhancement_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.info("🔍 Generating optimal query using small-fast-model...")
        logger.debug(f"Query optimization context: {len(recent_messages)} messages")

        response = await invoke_small_fast_model(
            messages=enhancement_messages,
            assistant_owner=assistant.owner,
            stream=False
        )

        # Extract the optimized query from response
        optimized_query = ""
        if isinstance(response, dict):
            if 'choices' in response and len(response['choices']) > 0:
                optimized_query = response['choices'][0]['message']['content'].strip()
            elif 'message' in response:
                optimized_query = response['message'].get('content', '').strip()

        if optimized_query:
            logger.info(f"✅ Optimized query generated: {optimized_query[:100]}...")
            logger.debug(f"Full optimized query: {optimized_query}")
            return optimized_query
        else:
            logger.warning("Empty response from small-fast-model, falling back to last user message")
            # Fallback to last user message
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        text_parts = [item.get('text', '') for item in content if item.get('type') == 'text']
                        return ' '.join(text_parts)
                    return content
            return ""
            
    except Exception as e:
        logger.error(f"Error generating optimal query: {e}", exc_info=True)
        # Fallback: return last user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [item.get('text', '') for item in content if item.get('type') == 'text']
                    return ' '.join(text_parts)
                return content
        return ""

async def rag_processor(messages: List[Dict[str, Any]], assistant: Assistant = None, request: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Hierarchical RAG processor with parent-child chunking support.
    
    This processor combines context-aware query optimization with parent-child chunking:
    - Full conversation history awareness (like context_aware_rag)
    - Multi-turn context tracking
    - Semantic query enhancement using small-fast-model
    - Uses parent_child_query plugin to return parent chunks for better structural understanding
    - Optimal for queries like "How many steps?", "List all X", "What is in section Y?"
    """
    logger.info("Using hierarchical_rag processor with assistant: %s", assistant.name if assistant else "None")
    
    # Print the messages passed to the processor
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
    logger.debug(f"Assistant Dictionary: {json.dumps(assistant_dict, indent=2)}")

    # Generate optimal query from full conversation context
    logger.info("Analyzing conversation context for optimal query generation...")
    optimal_query = await _generate_optimal_query(messages, assistant)
    
    if not optimal_query:
        # Fallback: extract last user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [item.get('text', '') for item in content if item.get('type') == 'text']
                    optimal_query = ' '.join(text_parts)
                else:
                    optimal_query = content
                break
    
    logger.info(f"Query for RAG retrieval: {optimal_query}")

    # Check if we have what we need to make a query
    if not assistant or not hasattr(assistant, 'RAG_collections') or not assistant.RAG_collections:
        error_message = "No RAG collections specified in the assistant configuration"
        logger.error(f"RAG processing failed: {error_message}")
        return {
            "context": error_message,
            "sources": [],
            "assistant_data": assistant_dict
        }
    
    if not optimal_query:
        error_message = "No query could be generated from the conversation"
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
    
    # Hierarchical RAG always uses parent_child_query plugin for better context
    query_plugin = 'parent_child_query'
    logger.info(f"Hierarchical RAG processor using query plugin: {query_plugin}")
    
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
            logger.info(f"Using organization: '{org_name}' (owner: {assistant.owner})")
            logger.info(f"Using organization KB config for {assistant.owner} (org: {org_name})")
        else:
            logger.warning(f"No config found for organization '{org_name}', falling back to environment variables")
            logger.warning(f"No KB config found for {assistant.owner} (org: {org_name}), falling back to env vars")
    except Exception as e:
        logger.error(f"Error getting organization config for {assistant.owner}: {e}")
        logger.error(f"Error getting org KB config for {assistant.owner}: {e}, falling back to env vars")
    
    # Fallback to environment variables
    if not KB_SERVER_URL:
        import config
        KB_SERVER_URL = os.getenv('LAMB_KB_SERVER')
        if not KB_SERVER_URL:
            raise ValueError("LAMB_KB_SERVER environment variable is required")
        KB_API_KEY = os.getenv('LAMB_KB_SERVER_TOKEN') or config.LAMB_BEARER_TOKEN
        print(f"🔧 [RAG/KB] Using environment variable configuration (fallback for {assistant.owner})")
        logger.info("Using environment variable KB configuration")

    print(f"🚀 [RAG/KB] Server: {KB_SERVER_URL} | Config: {config_source} | Organization: {org_name} | Collections: {len(collections)}")
    
    headers = {
        "Authorization": f"Bearer {KB_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Prepare the payload (same for all collections) - using optimized query
    payload = {
        "query_text": optimal_query,
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
            print(f"\n===== QUERYING COLLECTION: {collection_id} =====")
            
            # Use parent_child_query plugin for hierarchical context
            url = f"{KB_SERVER_URL}/collections/{collection_id}/query?plugin_name={query_plugin}"
            
            print(f"URL: {url}")
            print(f"Query plugin: {query_plugin} (hierarchical parent-child)")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            
            try:
                # Make the request to the KB server
                response = requests.post(url, headers=headers, json=payload)
                
                print(f"Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    # Parse the JSON response
                    raw_response = response.json()
                    # Print the entire raw response
                    print(f"Response Summary: {len(raw_response.get('documents', []))} documents returned")
                    print(f"Raw Response:\n{json.dumps(raw_response, indent=2)}")
                    
                    # Store the response
                    all_responses[collection_id] = {
                        "status": "success",
                        "data": raw_response
                    }
                    any_success = True
                else:
                    error_text = response.text
                    print(f"Error: {error_text}")
                    all_responses[collection_id] = {
                        "status": "error",
                        "error": f"Status code: {response.status_code}, Message: {error_text}"
                    }
            except Exception as collection_error:
                error_msg = f"Error querying collection {collection_id}: {str(collection_error)}"
                print(f"Error: {error_msg}")
                all_responses[collection_id] = {
                    "status": "error",
                    "error": error_msg
                }
            
            print("===========================================\n")
        
        # Print a summary of all responses
        print("\n===== SUMMARY OF ALL QUERIES =====")
        sources = []
        contexts = []
        
        for cid, result in all_responses.items():
            status = result["status"]
            if status == "success":
                documents = result["data"].get("documents", [])
                doc_count = len(documents)
                print(f"Collection {cid}: {status} - {doc_count} documents")
                
                # Extract file_urls and create source URLs
                # Supports both legacy (file_url) and new (original_file_url, markdown_file_url) metadata
                for doc in documents:
                    if "metadata" in doc:
                        metadata = doc["metadata"]
                        
                        # Determine the best source URL (prefer new fields from markitdown_plus_ingest)
                        source_url = None
                        original_url = None
                        markdown_url = None
                        images_folder = None
                        
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
                        
                        # Prefer original_file_url for the main source, fall back to file_url
                        main_url = original_url or source_url
                        
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
                print(f"Collection {cid}: {status} - {result.get('error', 'Unknown error')}")
        
        print("===================================\n")
        print(f"Extracted {len(sources)} source URLs")
        
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
