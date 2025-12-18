import logging
import json
import os
import requests
from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
from lamb.completions.org_config_resolver import OrganizationConfigResolver

logger = logging.getLogger(__name__)

def rag_processor(
    messages: List[Dict[str, Any]],
    assistant: Assistant = None,
    request: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Synchronous RAG processor that returns context from the knowledge base server
    using the last user message as a query.
    """
    logger.info("Using simple_rag processor with assistant: %s", assistant.name if assistant else "None")
    
    # Print the messages passed to the processor
    print("\n===== MESSAGES =====\n")
    try:
        print(f"Messages count: {len(messages)}")
        print(json.dumps(messages, indent=2))
    except Exception as e:
        print(f"Error printing messages: {str(e)}")
        print(f"Messages type: {type(messages)}")
        for i, msg in enumerate(messages):
            print(f"Message {i+1}: {msg}")
    print("\n=====\n")
    
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
    
    # Print the assistant dictionary
    print(f"\nAssistant Dictionary: {json.dumps(assistant_dict, indent=2)}\n")
    # Extract the last user message
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
    
    print(f"Last user message: {last_user_message}")
    
    # Check if we have what we need to make a query
    if not assistant or not hasattr(assistant, 'RAG_collections') or not assistant.RAG_collections:
        error_message = "No RAG collections specified in the assistant configuration"
        print(f"Error: {error_message}")
        return {
            "context": error_message,
            "sources": [],
            "assistant_data": assistant_dict
        }
    
    if not last_user_message:
        error_message = "No user message found to use for the query"
        print(f"Error: {error_message}")
        return {
            "context": error_message,
            "sources": [],
            "assistant_data": assistant_dict
        }
    
    # Parse the collection IDs from RAG_collections
    collections = assistant.RAG_collections.split(',')
    if not collections:
        error_message = "RAG_collections is empty or improperly formatted"
        print(f"Error: {error_message}")
        return {
            "context": error_message,
            "sources": [],
            "assistant_data": assistant_dict
        }
    
    # Clean up collection IDs
    collections = [cid.strip() for cid in collections if cid.strip()]
    print(f"Found {len(collections)} collections: {collections}")
    
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
            print(f"🏢 [RAG/KB] Using organization: '{org_name}' (owner: {assistant.owner})")
            logger.info(f"Using organization KB config for {assistant.owner} (org: {org_name})")
        else:
            print(f"⚠️  [RAG/KB] No config found for organization '{org_name}', falling back to environment variables")
            logger.warning(f"No KB config found for {assistant.owner} (org: {org_name}), falling back to env vars")
    except Exception as e:
        print(f"❌ [RAG/KB] Error getting organization config for {assistant.owner}: {e}")
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
            print(f"\n===== QUERYING COLLECTION: {collection_id} =====")
            
            url = f"{KB_SERVER_URL}/collections/{collection_id}/query"
            
            print(f"URL: {url}")
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
                for doc in documents:
                    if "metadata" in doc and "file_url" in doc["metadata"]:
                        file_url = doc["metadata"]["file_url"]
                        # Concatenate KB_SERVER_URL with file_url to create SOURCE URL
                        source_url = f"{KB_SERVER_URL}{file_url}"
                        # Add to sources list
                        sources.append({
                            "title": doc["metadata"].get("filename", "Unknown"),
                            "url": source_url,
                            "similarity": doc.get("similarity", 0)
                        })
                    
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