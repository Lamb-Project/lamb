from lamb.completions.tools.base import BaseTool, ToolDefinition, ToolResult
import logging
import json
import os
import requests
from typing import Dict, Any, List
from lamb.lamb_classes import Assistant
from lamb.completions.org_config_resolver import OrganizationConfigResolver

logger = logging.getLogger(__name__)


class SimpleRagTool(BaseTool):
    """RAG tool that queries knowledge base collections"""

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="simple_rag",
            display_name="Knowledge Base RAG",
            description="Retrieves relevant context from knowledge base collections",
            placeholder="context",  # Outputs to {context}
            category="rag",
            config_schema={
                "type": "object",
                "properties": {
                    "collections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of collection IDs to query"
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["collections"]
            }
        )

    def process(self, request: Dict[str, Any], assistant: Assistant, tool_config: Dict[str, Any]) -> ToolResult:
        """Execute RAG query against knowledge base collections"""

        try:
            # Extract configuration from tool_config
            collections = tool_config.get("collections", [])
            top_k = tool_config.get("top_k", 3)

            if not collections:
                return ToolResult(
                    placeholder="context",
                    content="Error: No collections specified",
                    sources=[],
                    error="No collections specified in tool configuration"
                )

            # Extract the last user message from request
            messages = request.get('messages', [])
            last_user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_message = msg.get("content", "")
                    break

            if not last_user_message:
                return ToolResult(
                    placeholder="context",
                    content="Error: No user message found",
                    sources=[],
                    error="No user message found to use for query"
                )

            # Clean up collection IDs
            collections = [cid.strip() for cid in collections if cid.strip()]

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
                    logger.info(f"🏢 [RAG/KB] Using organization: '{org_name}' (owner: {assistant.owner})")
                else:
                    logger.warning(f"⚠️  [RAG/KB] No config found for organization '{org_name}', falling back to environment variables")
            except Exception as e:
                logger.error(f"❌ [RAG/KB] Error getting organization config for {assistant.owner}: {e}, falling back to env vars")

            # Fallback to environment variables
            if not KB_SERVER_URL:
                import config
                KB_SERVER_URL = os.getenv('LAMB_KB_SERVER')
                if not KB_SERVER_URL:
                    raise ValueError("LAMB_KB_SERVER environment variable is required")
                KB_API_KEY = os.getenv('LAMB_KB_SERVER_TOKEN') or config.LAMB_BEARER_TOKEN
                logger.info("🔧 [RAG/KB] Using environment variable configuration")

            logger.info(f"🚀 [RAG/KB] Server: {KB_SERVER_URL} | Config: {config_source} | Organization: {org_name} | Collections: {len(collections)}")

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

            # Query each collection and aggregate results
            sources = []
            contexts = []

            for collection_id in collections:
                try:
                    url = f"{KB_SERVER_URL}/collections/{collection_id}/query"
                    response = requests.post(url, headers=headers, json=payload)

                    if response.status_code == 200:
                        raw_response = response.json()
                        documents = raw_response.get("documents", [])

                        # Extract sources and content from documents
                        for doc in documents:
                            if "metadata" in doc and "file_url" in doc["metadata"]:
                                file_url = doc["metadata"]["file_url"]
                                source_url = f"{KB_SERVER_URL}{file_url}"
                                sources.append({
                                    "title": doc["metadata"].get("filename", "Unknown"),
                                    "url": source_url,
                                    "similarity": doc.get("similarity", 0),
                                    "collection": collection_id
                                })

                            # Add document content to contexts
                            if "data" in doc:
                                contexts.append(doc["data"])

                    else:
                        logger.warning(f"Failed to query collection {collection_id}: {response.status_code} - {response.text}")

                except Exception as collection_error:
                    logger.error(f"Error querying collection {collection_id}: {str(collection_error)}")

            # Combine contexts into a single string
            combined_context = "\n\n".join(contexts) if contexts else ""

            return ToolResult(
                placeholder="context",
                content=combined_context,
                sources=sources
            )

        except Exception as e:
            logger.error(f"Error in SimpleRagTool.process: {e}", exc_info=True)
            return ToolResult(
                placeholder="context",
                content=f"Error: Failed to process RAG query - {str(e)}",
                sources=[],
                error=str(e)
            )


# Function interface for orchestrator
def tool_processor(request, assistant, tool_config):
    tool = SimpleRagTool()
    result = tool.process(request, assistant, tool_config)
    return {
        "placeholder": result.placeholder,
        "content": result.content,
        "sources": result.sources,
        "error": result.error
    }


def get_definition():
    return SimpleRagTool.get_definition()