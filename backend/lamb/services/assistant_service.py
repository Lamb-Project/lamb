"""
Assistant Service Layer
Encapsulates all assistant-related business logic.

This service layer is used by:
- /creator/assistant/* endpoints (via creator_interface/assistant_router.py)
- /v1/chat/completions (via lamb/completions/main.py)
- Plugin system for RAG and prompt processing

This consolidates logic that was previously duplicated across routers.
"""

from typing import Optional, Dict, Any, List, Tuple
from lamb.database_manager import LambDatabaseManager
from lamb.lamb_classes import Assistant
from lamb.logging_config import get_logger
import json

logger = get_logger(__name__, component="SERVICE")


class AssistantService:
    """Service for assistant operations"""
    
    def __init__(self):
        self.db_manager = LambDatabaseManager()
    
    def get_assistant_by_id(self, assistant_id: int) -> Optional[Assistant]:
        """Get assistant by ID - returns Assistant object"""
        return self.db_manager.get_assistant_by_id(assistant_id)
    
    def get_assistant_by_id_with_publication(self, assistant_id: int) -> Optional[Dict[str, Any]]:
        """Get assistant with publication status - returns dict"""
        return self.db_manager.get_assistant_by_id_with_publication(assistant_id)
    
    def get_assistant_by_name(self, assistant_name: str, owner: str) -> Optional[Assistant]:
        """Get assistant by name and owner"""
        return self.db_manager.get_assistant_by_name(assistant_name, owner)
    
    def get_assistants_by_owner(self, owner: str) -> List[Dict[str, Any]]:
        """Get all assistants for a specific owner"""
        return self.db_manager.get_list_of_assistants(owner) or []
    
    def get_assistants_by_owner_paginated(
        self, 
        owner: str, 
        limit: int = 10, 
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated assistants for owner with total count"""
        return self.db_manager.get_assistants_by_owner_paginated(owner, limit, offset)
    
    def get_all_assistants_with_publication(self) -> List[Dict[str, Any]]:
        """Get all assistants with publication data"""
        return self.db_manager.get_all_assistants_with_publication() or []
    
    def get_published_assistants(self) -> List[Dict[str, Any]]:
        """Get only published assistants"""
        return self.db_manager.get_published_assistants() or []
    
    def create_assistant(self, assistant: Assistant) -> Optional[int]:
        """
        Create a new assistant
        Returns: assistant_id if successful, None otherwise
        """
        return self.db_manager.add_assistant(assistant)
    
    def update_assistant(self, assistant_id: int, assistant: Assistant) -> bool:
        """
        Update an existing assistant
        
        Args:
            assistant_id: ID of assistant to update
            assistant: Updated assistant object
            
        Returns:
            bool: True if successful, False otherwise
            
        Used By:
            - /creator/assistant/{id} (via creator_interface)
            - Direct service calls
        """
        return self.db_manager.update_assistant(assistant_id, assistant)
    
    def get_assistant_with_publication_dict(self, assistant_id: int) -> Optional[Dict[str, Any]]:
        """
        Get assistant with publication status (returns dict, not Assistant object)
        
        This is a convenience method that returns the assistant data with
        publication information merged in.
        
        Args:
            assistant_id: Assistant ID
            
        Returns:
            Optional[Dict]: Assistant data with publication fields, or None
            
        Used By:
            - /creator/assistant/{id} (needs publication status)
            - Frontend assistant display
        """
        return self.db_manager.get_assistant_by_id_with_publication(assistant_id)
    
    def soft_delete_assistant_by_id(self, assistant_id: int) -> Dict[str, str]:
        """
        Soft delete an assistant (changes owner, makes name unique)
        
        This is the HTTP-friendly version that returns a dict response.
        
        Args:
            assistant_id: Assistant to soft delete
            
        Returns:
            Dict with "message" key indicating success
            
        Raises:
            HTTPException: If assistant not found or operation fails
            
        Used By:
            - /creator/assistant/{id}/soft-delete
        """
        from fastapi import HTTPException
        import time
        import config
        
        # Get the assistant
        assistant = self.get_assistant_by_id(assistant_id)
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")
        
        # Get published info if exists
        published_info = self.get_published_assistants()
        published_record = next(
            (p for p in published_info if p['assistant_id'] == assistant_id),
            None
        ) if published_info else None
        
        # If published, remove users from group
        if published_record:
            from lamb.owi_bridge.owi_group import OwiGroupManager
            group_id = published_record['group_id']
            group_manager = OwiGroupManager()
            
            group_users = group_manager.get_group_users(group_id)
            if group_users:
                for user in group_users:
                    group_manager.remove_user_from_group(group_id, user['id'])
        
        # Make name unique and change owner
        unique_suffix = f"_deleted_{int(time.time())}"
        deleted_name = f"{assistant.name}{unique_suffix}"
        
        success = self.db_manager.update_assistant(assistant_id, Assistant(
            name=deleted_name,
            description=assistant.description or "",
            owner="deleted_assistant@owi.com",
            api_callback=assistant.api_callback or "",
            system_prompt=assistant.system_prompt or "",
            prompt_template=assistant.prompt_template or "",
            RAG_endpoint=assistant.RAG_endpoint or "",
            RAG_Top_k=assistant.RAG_Top_k or 5,
            RAG_collections=assistant.RAG_collections or "",
            pre_retrieval_endpoint=assistant.pre_retrieval_endpoint or "",
            post_retrieval_endpoint=assistant.post_retrieval_endpoint or ""
        ))
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to soft delete assistant")
        
        return {"message": "Assistant soft deleted successfully"}
    
    def delete_assistant(self, assistant_id: int, owner: str) -> bool:
        """Hard delete an assistant (permanently removes from database)"""
        return self.db_manager.delete_assistant(assistant_id, owner)
    
    def soft_delete_assistant(self, assistant_id: int) -> bool:
        """
        Soft delete an assistant by changing owner to deleted_assistant@owi.com
        Makes name unique to avoid conflicts
        """
        assistant = self.db_manager.get_assistant_by_id(assistant_id)
        if not assistant:
            return False
        
        # Make name unique
        import time
        unique_suffix = f"_deleted_{int(time.time())}"
        deleted_name = f"{assistant.name}{unique_suffix}"
        
        # Update to mark as deleted
        success = self.db_manager.update_assistant(assistant_id, Assistant(
            name=deleted_name,
            description=assistant.description or "",
            owner="deleted_assistant@owi.com",
            api_callback=assistant.api_callback or "",
            system_prompt=assistant.system_prompt or "",
            prompt_template=assistant.prompt_template or "",
            RAG_endpoint=assistant.RAG_endpoint or "",
            RAG_Top_k=assistant.RAG_Top_k or 5,
            RAG_collections=assistant.RAG_collections or "",
            pre_retrieval_endpoint=assistant.pre_retrieval_endpoint or "",
            post_retrieval_endpoint=assistant.post_retrieval_endpoint or ""
        ))
        
        return success
    
    def publish_assistant(
        self, 
        assistant_id: int, 
        assistant_name: str,
        assistant_owner: str,
        group_id: str,
        group_name: str,
        oauth_consumer_name: str
    ) -> bool:
        """Publish an assistant (mark for LTI/OWI access)"""
        return self.db_manager.publish_assistant(
            assistant_id=assistant_id,
            assistant_name=assistant_name,
            assistant_owner=assistant_owner,
            group_id=group_id,
            group_name=group_name,
            oauth_consumer_name=oauth_consumer_name
        )
    
    def update_assistant_publication(
        self,
        assistant_id: int,
        group_id: str,
        group_name: str,
        oauth_consumer_name: str
    ) -> bool:
        """Update publication info for an assistant"""
        return self.db_manager.update_assistant_publication(
            assistant_id=assistant_id,
            group_id=group_id,
            group_name=group_name,
            oauth_consumer_name=oauth_consumer_name
        )
    
    def unpublish_assistant(self, assistant_id: int, group_id: str) -> bool:
        """Unpublish an assistant"""
        return self.db_manager.unpublish_assistant(assistant_id, group_id)
    
    def validate_assistant_name(self, name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate assistant name according to rules
        Returns: (is_valid, error_message)
        """
        import re
        if not re.match("^[a-zA-Z0-9_-]*$", name):
            return False, "Assistant name can only contain letters, numbers, underscores and hyphens. No spaces or special characters allowed."
        return True, None
    
    def check_ownership(self, assistant_id: int, user_email: str) -> bool:
        """Check if user owns an assistant"""
        assistant = self.get_assistant_by_id(assistant_id)
        if not assistant:
            return False
        return assistant.owner == user_email
    
    def parse_metadata(self, assistant: Assistant) -> Dict[str, Any]:
        """
        Parse assistant metadata/api_callback JSON
        Returns: plugin configuration dict
        """
        try:
            if hasattr(assistant, 'metadata') and assistant.metadata:
                return json.loads(assistant.metadata)
            elif hasattr(assistant, 'api_callback') and assistant.api_callback:
                return json.loads(assistant.api_callback)
            return {}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse metadata for assistant {assistant.id}")
            return {}

