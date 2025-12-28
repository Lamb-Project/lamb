"""
Analytics Router for Creator Interface
Provides endpoints for chat analytics and usage insights.

Endpoints:
- GET /creator/analytics/assistant/{id}/chats - List chats for an assistant
- GET /creator/analytics/assistant/{id}/chats/{chat_id} - Get chat detail
- GET /creator/analytics/assistant/{id}/stats - Get usage statistics
- GET /creator/analytics/assistant/{id}/timeline - Get activity timeline

Privacy:
- Organization configuration determines if user data is anonymized (default: yes)
- Only assistant owners can view analytics

Created: December 27, 2025
"""

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from lamb.services.chat_analytics_service import ChatAnalyticsService
from lamb.services.assistant_service import AssistantService
from lamb.database_manager import LambDatabaseManager
from lamb.owi_bridge.owi_users import OwiUserManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="API")

router = APIRouter(tags=["Analytics"])
security = HTTPBearer()

# Initialize services
analytics_service = ChatAnalyticsService()
assistant_service = AssistantService()
db_manager = LambDatabaseManager()
owi_user_manager = OwiUserManager()


# --- Pydantic Models ---

class ChatSummary(BaseModel):
    id: str
    title: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    message_count: int
    created_at: str
    updated_at: str


class ChatListResponse(BaseModel):
    chats: List[ChatSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


class ChatUser(BaseModel):
    id: str
    name: str
    email: Optional[str] = None


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: Optional[str] = None


class ChatDetailResponse(BaseModel):
    id: str
    title: str
    user: ChatUser
    created_at: str
    updated_at: str
    messages: List[ChatMessage]


class AnalyticsPeriod(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class AnalyticsStats(BaseModel):
    total_chats: int
    unique_users: int
    total_messages: int
    avg_messages_per_chat: float


class AnalyticsStatsResponse(BaseModel):
    assistant_id: int
    period: AnalyticsPeriod
    stats: AnalyticsStats


class TimelineDataPoint(BaseModel):
    date: str
    chat_count: int
    message_count: int


class AnalyticsTimelineResponse(BaseModel):
    assistant_id: int
    period: str
    data: List[TimelineDataPoint]


# --- Helper Functions ---

def get_creator_user_from_token(auth_header: str) -> Optional[Dict[str, Any]]:
    """Get creator user from authentication token"""
    try:
        if not auth_header:
            logger.error("No authorization header provided")
            return None

        user_auth = owi_user_manager.get_user_auth(auth_header)
        if not user_auth:
            logger.error("Invalid authentication token")
            return None

        user_email = user_auth.get("email", "")
        if not user_email:
            logger.error("No email found in authentication token")
            return None

        creator_user = db_manager.get_creator_user_by_email(user_email)
        if not creator_user:
            logger.error(f"No creator user found for email: {user_email}")
            return None

        # Fetch full organization data for access control
        organization_id = creator_user.get('organization_id')
        if organization_id:
            organization = db_manager.get_organization_by_id(organization_id)
            if organization:
                creator_user['organization'] = organization
            else:
                creator_user['organization'] = {}
        else:
            creator_user['organization'] = {}

        return creator_user

    except Exception as e:
        logger.error(f"Error getting creator user from token: {str(e)}")
        return None


def check_assistant_access(user: Dict[str, Any], assistant_id: int) -> bool:
    """
    Check if user has access to view analytics for an assistant.
    Only assistant owners can view analytics.
    """
    assistant = assistant_service.get_assistant_by_id(assistant_id)
    if not assistant:
        return False
    
    return assistant.owner == user.get('email')


def get_anonymize_setting(user: Dict[str, Any]) -> bool:
    """
    Get anonymization setting from organization config.
    Default: True (anonymize user data)
    """
    try:
        org = user.get('organization', {})
        config = org.get('config', {})
        
        # Check if config is a string (JSON) and parse it
        if isinstance(config, str):
            config = json.loads(config)
        
        # Look for analytics settings in org config
        analytics_config = config.get('analytics', {})
        
        # Default to anonymized (privacy first)
        return analytics_config.get('anonymize_users', True)
        
    except Exception as e:
        logger.warning(f"Error getting anonymize setting: {e}")
        return True  # Default to anonymized


# --- Endpoints ---

@router.get(
    "/assistant/{assistant_id}/chats",
    response_model=ChatListResponse,
    summary="List chats for an assistant",
    description="Get paginated list of chat conversations for a specific assistant"
)
async def list_assistant_chats(
    request: Request,
    assistant_id: int,
    start_date: Optional[str] = Query(None, description="Filter from date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter until date (ISO format)"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page")
):
    """List all chats for an assistant with optional date and user filtering"""
    
    # Authenticate user
    auth_header = request.headers.get("Authorization", "")
    user = get_creator_user_from_token(auth_header)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication")
    
    # Check access
    if not check_assistant_access(user, assistant_id):
        raise HTTPException(status_code=403, detail="You don't have access to this assistant's analytics")
    
    # Parse dates
    start_dt = None
    end_dt = None
    try:
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    
    # Get anonymization setting
    anonymize = get_anonymize_setting(user)
    
    # Get chats
    result = analytics_service.get_chats_for_assistant(
        assistant_id=assistant_id,
        start_date=start_dt,
        end_date=end_dt,
        user_id=user_id,
        page=page,
        per_page=per_page,
        anonymize_users=anonymize
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


@router.get(
    "/assistant/{assistant_id}/chats/{chat_id}",
    response_model=ChatDetailResponse,
    summary="Get chat details",
    description="Get detailed chat conversation with all messages"
)
async def get_chat_detail(
    request: Request,
    assistant_id: int,
    chat_id: str
):
    """Get detailed chat conversation including all messages"""
    
    # Authenticate user
    auth_header = request.headers.get("Authorization", "")
    user = get_creator_user_from_token(auth_header)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication")
    
    # Check access
    if not check_assistant_access(user, assistant_id):
        raise HTTPException(status_code=403, detail="You don't have access to this assistant's analytics")
    
    # Get anonymization setting
    anonymize = get_anonymize_setting(user)
    
    # Get chat detail
    result = analytics_service.get_chat_detail(
        chat_id=chat_id,
        assistant_id=assistant_id,
        anonymize_users=anonymize
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Chat not found or not associated with this assistant")
    
    return result


@router.get(
    "/assistant/{assistant_id}/stats",
    response_model=AnalyticsStatsResponse,
    summary="Get assistant statistics",
    description="Get usage statistics for an assistant"
)
async def get_assistant_stats(
    request: Request,
    assistant_id: int,
    start_date: Optional[str] = Query(None, description="Stats from date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Stats until date (ISO format)")
):
    """Get usage statistics for an assistant"""
    
    # Authenticate user
    auth_header = request.headers.get("Authorization", "")
    user = get_creator_user_from_token(auth_header)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication")
    
    # Check access
    if not check_assistant_access(user, assistant_id):
        raise HTTPException(status_code=403, detail="You don't have access to this assistant's analytics")
    
    # Parse dates
    start_dt = None
    end_dt = None
    try:
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    
    # Get stats
    result = analytics_service.get_assistant_stats(
        assistant_id=assistant_id,
        start_date=start_dt,
        end_date=end_dt
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


@router.get(
    "/assistant/{assistant_id}/timeline",
    response_model=AnalyticsTimelineResponse,
    summary="Get activity timeline",
    description="Get chat activity over time for an assistant"
)
async def get_assistant_timeline(
    request: Request,
    assistant_id: int,
    period: str = Query("day", description="Aggregation period: day, week, or month"),
    start_date: Optional[str] = Query(None, description="Timeline from date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Timeline until date (ISO format)")
):
    """Get chat activity timeline for an assistant"""
    
    # Authenticate user
    auth_header = request.headers.get("Authorization", "")
    user = get_creator_user_from_token(auth_header)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication")
    
    # Check access
    if not check_assistant_access(user, assistant_id):
        raise HTTPException(status_code=403, detail="You don't have access to this assistant's analytics")
    
    # Validate period
    if period not in ["day", "week", "month"]:
        raise HTTPException(status_code=400, detail="Period must be 'day', 'week', or 'month'")
    
    # Parse dates
    start_dt = None
    end_dt = None
    try:
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    
    # Get timeline
    result = analytics_service.get_assistant_timeline(
        assistant_id=assistant_id,
        period=period,
        start_date=start_dt,
        end_date=end_dt
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

