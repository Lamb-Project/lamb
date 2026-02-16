"""
Chats Router for Creator Interface
Provides endpoints for LAMB internal chat persistence.

This enables the "Chat with Assistant" tab to:
- Persist chat history across tab changes
- List and recall previous conversations
- Edit chat titles

Endpoints:
- POST /creator/chats - Create new chat
- GET /creator/chats - List user's chats for an assistant
- GET /creator/chats/{chat_id} - Get chat with messages
- PUT /creator/chats/{chat_id} - Update chat (title, archive)
- DELETE /creator/chats/{chat_id} - Delete chat

Created: December 29, 2025
"""

from fastapi import APIRouter, HTTPException, Request, Query, Path, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from lamb.services.lamb_chats_service import LambChatsService
from lamb.database_manager import LambDatabaseManager
from lamb.auth_context import AuthContext, get_auth_context
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="API")

router = APIRouter(tags=["Chats"])
security = HTTPBearer()

# Initialize services
chats_service = LambChatsService()
db_manager = LambDatabaseManager()


# --- Pydantic Models ---

class CreateChatRequest(BaseModel):
    """Request body for creating a new chat"""
    assistant_id: int = Field(..., description="ID of the assistant to chat with")
    title: Optional[str] = Field(None, description="Optional chat title (auto-generated if not provided)")


class CreateChatResponse(BaseModel):
    """Response for chat creation"""
    id: str
    user_id: int
    assistant_id: int
    title: str
    created_at: int
    updated_at: int


class ChatSummary(BaseModel):
    """Summary of a chat for list views"""
    id: str
    title: str
    assistant_id: int
    message_count: int
    created_at: int
    updated_at: int
    archived: int = 0


class ChatsListResponse(BaseModel):
    """Response for listing chats"""
    chats: List[ChatSummary]
    page: int
    per_page: int
    total_estimate: int


class ChatMessage(BaseModel):
    """Individual message in a chat"""
    id: str
    role: str
    content: str
    timestamp: Optional[int] = None
    parentId: Optional[str] = None
    childrenIds: List[str] = []


class ChatDetailResponse(BaseModel):
    """Full chat with messages"""
    id: str
    user_id: int
    assistant_id: int
    title: str
    created_at: int
    updated_at: int
    messages: List[ChatMessage]
    archived: int = 0


class UpdateChatRequest(BaseModel):
    """Request body for updating a chat"""
    title: Optional[str] = Field(None, description="New chat title")
    archived: Optional[int] = Field(None, description="Archive status (0 or 1)")


class UpdateChatResponse(BaseModel):
    """Response for chat update"""
    success: bool
    message: str


class DeleteChatResponse(BaseModel):
    """Response for chat deletion"""
    success: bool
    message: str


# --- Helper Functions ---

def parse_messages_from_chat(chat_data: Dict) -> List[Dict]:
    """
    Parse messages from OWI-style chat JSON structure.
    Converts the nested messages dict to a sorted list.
    """
    messages = []
    raw_messages = chat_data.get("history", {}).get("messages", {})
    
    for msg_id, msg_data in raw_messages.items():
        messages.append({
            "id": msg_id,
            "role": msg_data.get("role", "unknown"),
            "content": msg_data.get("content", ""),
            "timestamp": msg_data.get("timestamp"),
            "parentId": msg_data.get("parentId"),
            "childrenIds": msg_data.get("childrenIds", [])
        })
    
    # Sort by timestamp
    messages.sort(key=lambda m: m.get("timestamp") or 0)
    
    return messages


# --- Endpoints ---

@router.post(
    "",
    response_model=CreateChatResponse,
    summary="Create new chat",
    description="Create a new chat session for an assistant"
)
async def create_chat(
    body: CreateChatRequest,
    auth: AuthContext = Depends(get_auth_context)
):
    """Create a new chat session"""
    
    user_id = auth.user.get('id')
    
    # Create chat
    chat = chats_service.create_chat(
        user_id=user_id,
        assistant_id=body.assistant_id,
        title=body.title
    )
    
    if not chat:
        raise HTTPException(
            status_code=403, 
            detail="Failed to create chat. You may not have access to this assistant."
        )
    
    logger.info(f"Created chat {chat['id']} for user {user_id}, assistant {body.assistant_id}")
    
    return CreateChatResponse(
        id=chat["id"],
        user_id=chat["user_id"],
        assistant_id=chat["assistant_id"],
        title=chat["title"],
        created_at=chat["created_at"],
        updated_at=chat["updated_at"]
    )


@router.get(
    "",
    response_model=ChatsListResponse,
    summary="List user's chats",
    description="Get paginated list of user's chats for an assistant"
)
async def list_chats(
    assistant_id: int = Query(..., description="ID of the assistant"),
    include_archived: bool = Query(False, description="Include archived chats"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    auth: AuthContext = Depends(get_auth_context)
):
    """List user's chats for an assistant"""
    
    user_id = auth.user.get('id')
    
    # Get chats
    result = chats_service.get_user_chats(
        user_id=user_id,
        assistant_id=assistant_id,
        include_archived=include_archived,
        page=page,
        per_page=per_page
    )
    
    # Convert to response model
    chats = [
        ChatSummary(
            id=c["id"],
            title=c["title"],
            assistant_id=c["assistant_id"],
            message_count=c["message_count"],
            created_at=c["created_at"],
            updated_at=c["updated_at"],
            archived=c.get("archived", 0)
        )
        for c in result["chats"]
    ]
    
    return ChatsListResponse(
        chats=chats,
        page=result["page"],
        per_page=result["per_page"],
        total_estimate=result["total_estimate"]
    )


@router.get(
    "/{chat_id}",
    response_model=ChatDetailResponse,
    summary="Get chat details",
    description="Get a specific chat with all messages"
)
async def get_chat(
    chat_id: str = Path(..., description="ID of the chat"),
    auth: AuthContext = Depends(get_auth_context)
):
    """Get a specific chat with all messages"""
    
    user_id = auth.user.get('id')
    
    # Get chat with access validation
    chat = chats_service.get_chat(chat_id, user_id)
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found or access denied")
    
    # Parse messages from chat JSON
    messages = parse_messages_from_chat(chat.get("chat", {}))
    
    return ChatDetailResponse(
        id=chat["id"],
        user_id=chat["user_id"],
        assistant_id=chat["assistant_id"],
        title=chat["title"],
        created_at=chat["created_at"],
        updated_at=chat["updated_at"],
        messages=[ChatMessage(**m) for m in messages],
        archived=chat.get("archived", 0)
    )


@router.put(
    "/{chat_id}",
    response_model=UpdateChatResponse,
    summary="Update chat",
    description="Update chat title or archive status"
)
async def update_chat(
    chat_id: str = Path(..., description="ID of the chat"),
    body: UpdateChatRequest = None,
    auth: AuthContext = Depends(get_auth_context)
):
    """Update chat title or archive status"""
    
    user_id = auth.user.get('id')
    
    # Handle title update
    if body.title is not None:
        success = chats_service.update_chat_title(chat_id, user_id, body.title)
        if not success:
            raise HTTPException(
                status_code=404, 
                detail="Chat not found or you don't have permission to update it"
            )
    
    # Handle archive update
    if body.archived is not None:
        if body.archived == 1:
            success = chats_service.archive_chat(chat_id, user_id)
        else:
            # Unarchive - directly update via db
            chat = chats_service.get_chat(chat_id, user_id)
            if not chat or chat["user_id"] != user_id:
                raise HTTPException(status_code=404, detail="Chat not found or access denied")
            success = db_manager.update_lamb_chat(chat_id, archived=0)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Chat not found or you don't have permission to update it"
            )
    
    logger.info(f"Updated chat {chat_id} by user {user_id}")
    
    return UpdateChatResponse(success=True, message="Chat updated successfully")


@router.delete(
    "/{chat_id}",
    response_model=DeleteChatResponse,
    summary="Delete chat",
    description="Permanently delete a chat"
)
async def delete_chat(
    chat_id: str = Path(..., description="ID of the chat"),
    auth: AuthContext = Depends(get_auth_context)
):
    """Permanently delete a chat"""
    
    user_id = auth.user.get('id')
    
    # Delete chat
    success = chats_service.delete_chat(chat_id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Chat not found or you don't have permission to delete it"
        )
    
    logger.info(f"Deleted chat {chat_id} by user {user_id}")
    
    return DeleteChatResponse(success=True, message="Chat deleted successfully")
