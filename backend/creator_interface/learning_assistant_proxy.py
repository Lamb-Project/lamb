"""
Learning Assistant Proxy Service

This module provides a secure proxy service for frontend chat interfaces to access
learning assistants without exposing API keys. It uses proper user authentication
and access control while maintaining OpenAI API compatibility.

Security Features:
- User token authentication (no exposed API keys)
- Assistant access control based on ownership/organization
- Full streaming and non-streaming support
- Audit trail for all assistant interactions
"""

from fastapi import APIRouter, Request, HTTPException, Depends, Path, Query
from fastapi.responses import StreamingResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from lamb.auth_context import AuthContext, get_auth_context
from lamb.completions.main import run_lamb_assistant
from lamb.database_manager import LambDatabaseManager
from lamb.services.lamb_chats_service import LambChatsService
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator

# Set up logging
logger = logging.getLogger(__name__)

# Initialize router and security
router = APIRouter(tags=["Learning Assistant Proxy"])
security = HTTPBearer()
db_manager = LambDatabaseManager()
chats_service = LambChatsService()


def verify_assistant_access_via_auth_context(auth: AuthContext, assistant_id: int) -> bool:
    """
    Verify user has access to use the specified assistant (chat) via AuthContext.
    
    Access is granted if AuthContext.can_access_assistant returns anything other than "none".
    
    Args:
        auth: AuthContext for the current request
        assistant_id: ID of the assistant to access
        
    Returns:
        bool: True if user has access, False otherwise
    """
    access = auth.can_access_assistant(assistant_id)
    if access == "none":
        logger.warning(f"User {auth.user.get('email')} denied access to assistant {assistant_id}")
        return False
    logger.debug(f"User {auth.user.get('email')} has '{access}' access to assistant {assistant_id}")
    return True


async def wrap_streaming_response_with_chat_save(
    response_generator: AsyncGenerator,
    chat_id: str,
    chats_service: LambChatsService
) -> AsyncGenerator:
    """
    Wrap a streaming response generator to capture the full content and save to chat.
    Yields chunks as they come, then saves the complete response at the end.
    """
    full_content = []
    
    try:
        async for chunk in response_generator:
            yield chunk
            
            # Try to extract content from SSE chunk
            if isinstance(chunk, bytes):
                chunk_str = chunk.decode('utf-8')
            else:
                chunk_str = chunk
            
            # Parse SSE data lines
            for line in chunk_str.split('\n'):
                if line.startswith('data: ') and line != 'data: [DONE]':
                    try:
                        data = json.loads(line[6:])
                        delta = data.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            full_content.append(content)
                    except (json.JSONDecodeError, IndexError, KeyError):
                        pass
        
        # After streaming completes, save the full response
        if full_content and chat_id:
            complete_response = ''.join(full_content)
            try:
                chats_service.add_assistant_response(chat_id, complete_response)
                logger.debug(f"Saved streaming response to chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to save streaming response to chat {chat_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in streaming wrapper: {e}")
        raise


@router.post(
    "/assistant/{assistant_id}/chat/completions",
    summary="Chat with Learning Assistant",
    description="""
    Secure proxy endpoint for chat completions with learning assistants.
    
    This endpoint provides OpenAI-compatible chat completions while maintaining
    proper security through user authentication and access control.
    
    Features:
    - User token authentication (no API key exposure)
    - Assistant access control based on ownership/organization
    - Full streaming and non-streaming support
    - OpenAI-compatible request/response format
    - **Chat persistence**: Include `chat_id` to continue an existing chat,
      or omit to create a new one. Response includes `chat_id` for continuation.
    
    Example Request:
    ```bash
    curl -X POST 'http://localhost:9099/creator/assistant/1/chat/completions' \\
    -H 'Authorization: Bearer <user_token>' \\
    -H 'Content-Type: application/json' \\
    -d '{
      "messages": [
        {"role": "user", "content": "Hello, how can you help me?"}
      ],
      "stream": false
    }'
    ```
    
    Example with Chat Persistence:
    ```bash
    curl -X POST 'http://localhost:9099/creator/assistant/1/chat/completions' \\
    -H 'Authorization: Bearer <user_token>' \\
    -H 'Content-Type: application/json' \\
    -d '{
      "messages": [
        {"role": "user", "content": "Tell me a story"}
      ],
      "chat_id": "existing-chat-uuid",
      "stream": true
    }' --no-buffer
    ```
    """,
    dependencies=[Depends(security)]
)
async def proxy_assistant_chat(
    assistant_id: int = Path(..., description="ID of the assistant to chat with"),
    request: Request = None,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Proxy endpoint for chat completions with user authentication and access control.
    
    This endpoint eliminates the need for exposed API keys by using proper user
    authentication while maintaining full OpenAI API compatibility.
    
    Chat Persistence:
    - Include `chat_id` in request body to continue an existing chat
    - Omit `chat_id` to create a new chat
    - Response includes `chat_id` for the frontend to use in subsequent requests
    """
    try:
        creator_user = auth.user
        user_id = creator_user.get('id')
        logger.info(f"User {creator_user['email']} requesting access to assistant {assistant_id}")
        
        # 2. Verify assistant access via AuthContext
        if not verify_assistant_access_via_auth_context(auth, assistant_id):
            logger.warning(f"User {creator_user['email']} denied access to assistant {assistant_id}")
            raise HTTPException(
                status_code=403,
                detail="Access denied. You don't have permission to use this assistant."
            )
        
        # 3. Parse request body
        try:
            body = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse request body: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON in request body"
            )
        
        # 4. Validate required fields
        if "messages" not in body:
            raise HTTPException(
                status_code=400,
                detail="Missing 'messages' field in request body"
            )
        
        # 5. Extract chat persistence parameters
        chat_id = body.pop("chat_id", None)  # Remove from body before passing to LLM
        persist_chat = body.pop("persist_chat", True)  # Default to persisting
        
        # 6. Get the latest user message for persistence
        messages = body.get("messages", [])
        latest_user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                latest_user_message = msg.get("content", "")
                break
        
        # 7. Save user message to chat (create new chat if needed)
        if persist_chat and latest_user_message:
            try:
                result = chats_service.add_user_message_and_create_if_needed(
                    user_id=user_id,
                    assistant_id=assistant_id,
                    content=latest_user_message,
                    chat_id=chat_id
                )
                chat_id = result["chat_id"]
                logger.debug(f"Saved user message to chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to save user message: {e}")
                # Continue with completion even if chat persistence fails
                chat_id = None
        
        # 8. Log the request for audit trail
        stream_mode = body.get("stream", False)
        logger.info(f"Processing {'streaming' if stream_mode else 'non-streaming'} "
                   f"completion for user {creator_user['email']} with assistant {assistant_id}")
        
        # 9. Call internal completion system
        response = await run_lamb_assistant(
            request=body,
            assistant=assistant_id,
            headers=None  # Internal call, no need for special headers
        )
        
        logger.info(f"Successfully processed completion for user {creator_user['email']} "
                   f"with assistant {assistant_id}")
        
        # 10. Handle response based on streaming mode
        if stream_mode and isinstance(response, StreamingResponse):
            # Wrap streaming response to capture and save content
            if persist_chat and chat_id:
                wrapped_generator = wrap_streaming_response_with_chat_save(
                    response.body_iterator,
                    chat_id,
                    chats_service
                )
                # Return new StreamingResponse with chat_id in headers
                return StreamingResponse(
                    wrapped_generator,
                    media_type="text/event-stream",
                    headers={"X-Chat-Id": chat_id} if chat_id else {}
                )
            return response
        else:
            # Non-streaming response - save assistant message directly
            if persist_chat and chat_id:
                try:
                    # Extract content from response
                    if isinstance(response, Response):
                        response_body = json.loads(response.body.decode('utf-8'))
                    else:
                        response_body = response
                    
                    assistant_content = response_body.get('choices', [{}])[0].get('message', {}).get('content', '')
                    if assistant_content:
                        chats_service.add_assistant_response(chat_id, assistant_content)
                        logger.debug(f"Saved assistant response to chat {chat_id}")
                    
                    # Add chat_id to response
                    if isinstance(response_body, dict):
                        response_body['chat_id'] = chat_id
                        return Response(
                            content=json.dumps(response_body),
                            media_type="application/json"
                        )
                except Exception as e:
                    logger.error(f"Failed to save assistant response: {e}")
            
            return response
        
    except HTTPException:
        # Re-raise HTTP exceptions (authentication, authorization, validation errors)
        raise
    
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error in proxy_assistant_chat: {str(e)}", exc_info=True)
        
        # Check if this was a streaming request for appropriate error response
        try:
            body = await request.json()
            stream_mode = body.get("stream", False)
        except:
            stream_mode = False
        
        error_detail = {
            "error": {
                "message": "Internal server error occurred while processing your request",
                "type": "internal_server_error",
                "param": None,
                "code": None
            }
        }
        
        if stream_mode:
            # Return streaming error response
            error_sse = f"data: {json.dumps(error_detail['error'])}\\n\\n"
            return StreamingResponse(
                iter([error_sse.encode()]),
                media_type="text/event-stream",
                status_code=500
            )
        else:
            # Return JSON error response
            raise HTTPException(
                status_code=500,
                detail=error_detail["error"]["message"]
            )


@router.get(
    "/assistant/{assistant_id}/info",
    summary="Get Assistant Information",
    description="""
    Get basic information about a learning assistant if user has access.
    
    This endpoint allows users to verify they have access to an assistant
    and get basic information about it.
    """,
    dependencies=[Depends(security)]
)
async def get_assistant_info(
    assistant_id: int = Path(..., description="ID of the assistant"),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get assistant information with access control.
    """
    try:
        creator_user = auth.user
        
        # Verify assistant access via AuthContext
        if not verify_assistant_access_via_auth_context(auth, assistant_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied. You don't have permission to view this assistant."
            )
        
        # 3. Get assistant details
        assistant = db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")
        
        # 4. Return basic info (don't expose sensitive details)
        return {
            "id": assistant.id,
            "name": assistant.name,
            "description": assistant.description,
            "owner": assistant.owner,
            "created_at": str(assistant.created_at) if hasattr(assistant, 'created_at') else None,
            "updated_at": str(assistant.updated_at) if hasattr(assistant, 'updated_at') else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assistant info: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/models",
    summary="Get Available Models (Assistants)",
    description="""
    Get list of learning assistants available to the authenticated user.
    
    Returns assistants formatted as OpenAI-compatible models that the user has access to:
    - Assistants owned by the user
    - Assistants from the user's organization
    
    This endpoint respects organization boundaries and only returns assistants
    the user has permission to use.
    
    Example Request:
    ```bash
    curl -X GET 'http://localhost:9099/creator/models' \\
    -H 'Authorization: Bearer <user_token>'
    ```
    
    Example Response:
    ```json
    {
      "object": "list",
      "data": [
        {
          "id": "lamb_assistant.1",
          "object": "model",
          "created": 1677609600,
          "owned_by": "organization_name"
        }
      ]
    }
    ```
    """,
    dependencies=[Depends(security)]
)
async def get_available_models(
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get all assistants the authenticated user has access to, formatted as OpenAI models.
    """
    try:
        import time
        
        creator_user = auth.user
        user_email = creator_user.get('email')
        user_org = auth.organization
        
        logger.info(f"User {user_email} requesting available models (org: {user_org.get('name', 'None')})")
        
        # 2. Get all assistants from database
        all_assistants = db_manager.get_list_of_assitants_id_and_name()
        
        # 3. Filter assistants based on access control via AuthContext
        accessible_assistants = []
        for assistant_dict in all_assistants:
            assistant_id = assistant_dict.get('id')
            
            # Skip deleted assistants
            if assistant_dict.get('owner') == 'deleted_assistant@owi.com':
                continue
            
            # Check access via AuthContext
            access = auth.can_access_assistant(assistant_id)
            if access != "none":
                accessible_assistants.append(assistant_dict)
                logger.debug(f"User {user_email} has '{access}' access to assistant {assistant_id}")
        
        # 4. Format as OpenAI-compatible models
        models_data = []
        for assistant in accessible_assistants:
            models_data.append({
                "id": f"lamb_assistant.{assistant['id']}",
                "object": "model",
                "created": int(time.time()),
                "owned_by": user_org.get('name', 'lamb_v4')
            })
        
        response_body = {
            "object": "list",
            "data": models_data
        }
        
        logger.info(f"Returning {len(models_data)} accessible models for user {user_email}")
        return response_body
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting available models: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching available models"
        )
