"""
LAMB Internal Chats Service

Manages internal chat persistence for the Creator Interface chat functionality.
This service enables:
- Chat history list and recall
- Title editing (user-controlled or auto-generated)
- Message persistence across tab changes

The lamb_chats table mirrors OWI's chat structure for unified analytics in the Activity tab.

Created: December 29, 2025
"""

import uuid
import time
from typing import Optional, Dict, Any, List
from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="SERVICE")


class LambChatsService:
    """Service layer for LAMB internal chat operations"""

    def __init__(self):
        self.db = LambDatabaseManager()

    def create_chat(
        self,
        user_id: int,
        assistant_id: int,
        title: str = None,
        first_message: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new chat session.
        
        Args:
            user_id: Creator user ID (from Creator_users table)
            assistant_id: LAMB assistant ID
            title: Optional explicit title
            first_message: Optional first message to auto-generate title from
            
        Returns:
            Created chat record or None on error
        """
        # Validate user has access to assistant
        if not self._validate_user_assistant_access(user_id, assistant_id):
            logger.warning(f"User {user_id} denied access to create chat for assistant {assistant_id}")
            return None
        
        # Generate chat ID
        chat_id = str(uuid.uuid4())
        
        # Generate title
        if not title and first_message:
            title = self.db.generate_chat_title(first_message)
        elif not title:
            title = self.db.generate_chat_title("")
        
        chat = self.db.create_lamb_chat(
            chat_id=chat_id,
            user_id=user_id,
            assistant_id=assistant_id,
            title=title
        )
        
        if chat:
            logger.info(f"Created chat {chat_id} for user {user_id}, assistant {assistant_id}")
        
        return chat

    def get_chat(
        self,
        chat_id: str,
        user_id: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a chat by ID, optionally validating user access.
        
        Args:
            chat_id: UUID of the chat
            user_id: Optional user ID for access validation
            
        Returns:
            Chat record with messages, or None if not found/unauthorized
        """
        chat = self.db.get_lamb_chat(chat_id)
        
        if not chat:
            return None
        
        # Validate access if user_id provided
        if user_id is not None and chat["user_id"] != user_id:
            # Check if user has access to the assistant (shared assistants)
            if not self._validate_user_assistant_access(user_id, chat["assistant_id"]):
                logger.warning(f"User {user_id} denied access to chat {chat_id}")
                return None
        
        return chat

    def get_user_chats(
        self,
        user_id: int,
        assistant_id: int,
        include_archived: bool = False,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Get paginated list of user's chats for an assistant.
        
        Args:
            user_id: Creator user ID
            assistant_id: LAMB assistant ID
            include_archived: Whether to include archived chats
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            Dict with chats list and pagination info
        """
        offset = (page - 1) * per_page
        
        chats = self.db.get_lamb_chats_for_user_assistant(
            user_id=user_id,
            assistant_id=assistant_id,
            include_archived=include_archived,
            limit=per_page,
            offset=offset
        )
        
        # Get total count for pagination (simplified - counts all non-archived)
        # For proper pagination, we'd need a separate count method
        total_estimate = len(chats) + offset if len(chats) == per_page else len(chats) + offset
        
        return {
            "chats": chats,
            "page": page,
            "per_page": per_page,
            "total_estimate": total_estimate
        }

    def update_chat_title(
        self,
        chat_id: str,
        user_id: int,
        new_title: str
    ) -> bool:
        """
        Update chat title.
        
        Args:
            chat_id: UUID of the chat
            user_id: User ID (for access validation)
            new_title: New title string
            
        Returns:
            True if updated successfully
        """
        # Validate ownership
        chat = self.get_chat(chat_id, user_id)
        if not chat:
            logger.warning(f"Cannot update title: chat {chat_id} not found or access denied")
            return False
        
        # Only owner can update title
        if chat["user_id"] != user_id:
            logger.warning(f"User {user_id} cannot update title of chat {chat_id} owned by {chat['user_id']}")
            return False
        
        return self.db.update_lamb_chat(chat_id, title=new_title.strip())

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        user_id: int = None
    ) -> Optional[str]:
        """
        Add a message to an existing chat.
        
        Args:
            chat_id: UUID of the chat
            role: Message role ('user' or 'assistant')
            content: Message content
            user_id: Optional user ID for access validation
            
        Returns:
            Message ID if successful, None on error
        """
        # Validate access if user_id provided
        if user_id is not None:
            chat = self.get_chat(chat_id, user_id)
            if not chat:
                return None
        
        message_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        success = self.db.add_message_to_lamb_chat(
            chat_id=chat_id,
            message_id=message_id,
            role=role,
            content=content,
            timestamp=timestamp
        )
        
        if success:
            logger.debug(f"Added {role} message {message_id} to chat {chat_id}")
            return message_id
        
        return None

    def add_user_message_and_create_if_needed(
        self,
        user_id: int,
        assistant_id: int,
        content: str,
        chat_id: str = None
    ) -> Dict[str, Any]:
        """
        Add a user message, creating a new chat if chat_id is not provided.
        This is the main method called by the chat proxy.
        
        Args:
            user_id: Creator user ID
            assistant_id: LAMB assistant ID
            content: Message content
            chat_id: Optional existing chat ID
            
        Returns:
            Dict with chat_id and message_id
        """
        # Create new chat if needed
        if not chat_id:
            chat = self.create_chat(
                user_id=user_id,
                assistant_id=assistant_id,
                first_message=content
            )
            if not chat:
                raise ValueError("Failed to create chat")
            chat_id = chat["id"]
        
        # Add the user message
        message_id = self.add_message(
            chat_id=chat_id,
            role="user",
            content=content,
            user_id=user_id
        )
        
        if not message_id:
            raise ValueError("Failed to add message")
        
        return {
            "chat_id": chat_id,
            "message_id": message_id
        }

    def add_assistant_response(
        self,
        chat_id: str,
        content: str
    ) -> Optional[str]:
        """
        Add assistant response to a chat.
        Called after receiving LLM response.
        
        Args:
            chat_id: UUID of the chat
            content: Assistant response content
            
        Returns:
            Message ID if successful
        """
        return self.add_message(
            chat_id=chat_id,
            role="assistant",
            content=content
        )

    def archive_chat(
        self,
        chat_id: str,
        user_id: int
    ) -> bool:
        """
        Archive a chat (soft delete).
        
        Args:
            chat_id: UUID of the chat
            user_id: User ID (for ownership validation)
            
        Returns:
            True if archived successfully
        """
        chat = self.get_chat(chat_id, user_id)
        if not chat or chat["user_id"] != user_id:
            logger.warning(f"Cannot archive: chat {chat_id} not found or not owned by user {user_id}")
            return False
        
        return self.db.update_lamb_chat(chat_id, archived=1)

    def delete_chat(
        self,
        chat_id: str,
        user_id: int
    ) -> bool:
        """
        Permanently delete a chat.
        
        Args:
            chat_id: UUID of the chat
            user_id: User ID (for ownership validation)
            
        Returns:
            True if deleted successfully
        """
        chat = self.get_chat(chat_id, user_id)
        if not chat or chat["user_id"] != user_id:
            logger.warning(f"Cannot delete: chat {chat_id} not found or not owned by user {user_id}")
            return False
        
        return self.db.delete_lamb_chat(chat_id)

    def _validate_user_assistant_access(
        self,
        user_id: int,
        assistant_id: int
    ) -> bool:
        """
        Check if user has access to an assistant.
        Access is granted if:
        1. User owns the assistant
        2. Assistant is shared with user
        3. User is in same organization as assistant
        
        Args:
            user_id: Creator user ID
            assistant_id: LAMB assistant ID
            
        Returns:
            True if user has access
        """
        try:
            # Get user info
            user = self.db.get_creator_user_by_id(user_id)
            if not user:
                return False
            
            user_email = user.get('user_email')
            user_org_id = user.get('organization_id')
            
            # Get assistant
            assistant = self.db.get_assistant_by_id(assistant_id)
            if not assistant:
                return False
            
            # Check ownership
            if assistant.owner == user_email:
                return True
            
            # Check if shared
            if self.db.is_assistant_shared_with_user(assistant_id, user_id):
                return True
            
            # Check organization
            if user_org_id and user_org_id == assistant.organization_id:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating user {user_id} access to assistant {assistant_id}: {e}")
            return False

    def get_chats_for_analytics(
        self,
        assistant_id: int,
        start_date: int = None,
        end_date: int = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get chats for Activity/Analytics tab.
        Returns chats with source='lamb_internal' marker.
        
        This is called by ChatAnalyticsService to combine with OWI chats.
        
        Args:
            assistant_id: LAMB assistant ID
            start_date: Filter from timestamp
            end_date: Filter until timestamp
            limit: Maximum records
            offset: Pagination offset
            
        Returns:
            List of chat summaries
        """
        return self.db.get_lamb_chats_for_assistant_analytics(
            assistant_id=assistant_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )

