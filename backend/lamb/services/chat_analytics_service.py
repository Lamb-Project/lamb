"""
Chat Analytics Service Layer
Provides analytics and insights into OWI chat conversations for learning assistants.

This service queries the Open WebUI database to:
- List chats for a specific assistant
- Get chat details with messages
- Calculate usage statistics

Privacy:
- Organization configuration determines if user data is anonymized (default: yes)
- Chat content is always accessible to assistant owners

Created: December 27, 2025
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import json
from lamb.owi_bridge.owi_database import OwiDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="SERVICE")


class ChatAnalyticsService:
    """Service for analyzing OWI chat data for learning assistants"""
    
    def __init__(self):
        self.db = OwiDatabaseManager()
    
    def get_chats_for_assistant(
        self,
        assistant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        anonymize_users: bool = True
    ) -> Dict[str, Any]:
        """
        Get list of chats for a specific assistant with pagination and filters.
        
        Args:
            assistant_id: LAMB assistant ID
            start_date: Filter chats from this date
            end_date: Filter chats until this date
            user_id: Filter by specific user (OWI user_id)
            page: Page number (1-indexed)
            per_page: Items per page
            anonymize_users: If True, replace user identifiers with anonymous IDs
            
        Returns:
            Dict with chats list, total count, and pagination info
        """
        try:
            model_pattern = f'lamb_assistant.{assistant_id}'
            
            # Build WHERE clause
            where_clauses = ["json_extract(c.chat, '$.models') LIKE ?"]
            params = [f'%{model_pattern}%']
            
            if start_date:
                where_clauses.append("c.created_at >= ?")
                params.append(start_date.timestamp())
            
            if end_date:
                where_clauses.append("c.created_at <= ?")
                params.append(end_date.timestamp())
            
            if user_id:
                where_clauses.append("c.user_id = ?")
                params.append(user_id)
            
            where_sql = " AND ".join(where_clauses)
            
            # Count total
            count_query = f"""
                SELECT COUNT(*) 
                FROM chat c
                WHERE {where_sql}
            """
            count_result = self._execute_query(count_query, tuple(params), fetch_one=True)
            total = count_result[0] if count_result else 0
            
            # Get paginated results
            offset = (page - 1) * per_page
            
            query = f"""
                SELECT 
                    c.id,
                    c.user_id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    c.chat,
                    u.name as user_name,
                    u.email as user_email
                FROM chat c
                LEFT JOIN user u ON c.user_id = u.id
                WHERE {where_sql}
                ORDER BY c.created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([per_page, offset])
            
            results = self._execute_query(query, tuple(params))
            
            # Process results
            chats = []
            user_anonymizer = {}
            anon_counter = [0]  # Use list to allow mutation in nested function
            
            def get_anon_id(user_id: str) -> str:
                if user_id not in user_anonymizer:
                    anon_counter[0] += 1
                    user_anonymizer[user_id] = f"User_{anon_counter[0]:03d}"
                return user_anonymizer[user_id]
            
            for row in (results or []):
                chat_id, user_id, title, created_at, updated_at, chat_json, user_name, user_email = row
                
                # Parse chat JSON to count messages
                message_count = 0
                try:
                    chat_data = json.loads(chat_json) if chat_json else {}
                    messages = chat_data.get("history", {}).get("messages", {})
                    message_count = len(messages)
                except (json.JSONDecodeError, TypeError):
                    pass
                
                # Handle timestamps (may be datetime or int)
                if isinstance(created_at, (int, float)):
                    created_at_str = datetime.fromtimestamp(created_at).isoformat()
                else:
                    created_at_str = str(created_at)
                    
                if isinstance(updated_at, (int, float)):
                    updated_at_str = datetime.fromtimestamp(updated_at).isoformat()
                else:
                    updated_at_str = str(updated_at)
                
                chat_summary = {
                    "id": chat_id,
                    "title": title or "Untitled Chat",
                    "message_count": message_count,
                    "created_at": created_at_str,
                    "updated_at": updated_at_str,
                }
                
                # Add user info (anonymized or real)
                if anonymize_users:
                    chat_summary["user_id"] = get_anon_id(user_id)
                    chat_summary["user_name"] = get_anon_id(user_id)
                    chat_summary["user_email"] = None
                else:
                    chat_summary["user_id"] = user_id
                    chat_summary["user_name"] = user_name or "Unknown"
                    chat_summary["user_email"] = user_email
                
                chats.append(chat_summary)
            
            total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "chats": chats,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages
            }
            
        except Exception as e:
            logger.error(f"Error getting chats for assistant {assistant_id}: {e}")
            return {
                "chats": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0,
                "error": str(e)
            }
    
    def get_chat_detail(
        self,
        chat_id: str,
        assistant_id: int,
        anonymize_users: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed chat conversation with all messages.
        
        Args:
            chat_id: OWI chat ID
            assistant_id: LAMB assistant ID (for verification)
            anonymize_users: If True, replace user identifiers with anonymous ID
            
        Returns:
            Dict with chat details and messages, or None if not found
        """
        try:
            model_pattern = f'lamb_assistant.{assistant_id}'
            
            query = """
                SELECT 
                    c.id,
                    c.user_id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    c.chat,
                    u.name as user_name,
                    u.email as user_email
                FROM chat c
                LEFT JOIN user u ON c.user_id = u.id
                WHERE c.id = ? AND json_extract(c.chat, '$.models') LIKE ?
            """
            
            result = self._execute_query(query, (chat_id, f'%{model_pattern}%'), fetch_one=True)
            
            if not result:
                return None
            
            chat_id, user_id, title, created_at, updated_at, chat_json, user_name, user_email = result
            
            # Parse chat JSON
            messages = []
            try:
                chat_data = json.loads(chat_json) if chat_json else {}
                raw_messages = chat_data.get("history", {}).get("messages", {})
                
                # Convert message dict to sorted list
                for msg_id, msg_data in raw_messages.items():
                    timestamp = msg_data.get("timestamp")
                    if isinstance(timestamp, (int, float)):
                        timestamp_str = datetime.fromtimestamp(timestamp).isoformat()
                    else:
                        timestamp_str = str(timestamp) if timestamp else None
                    
                    messages.append({
                        "id": msg_id,
                        "role": msg_data.get("role", "unknown"),
                        "content": msg_data.get("content", ""),
                        "timestamp": timestamp_str
                    })
                
                # Sort by timestamp
                messages.sort(key=lambda m: m.get("timestamp") or "")
                
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Error parsing chat JSON for {chat_id}: {e}")
            
            # Handle timestamps
            if isinstance(created_at, (int, float)):
                created_at_str = datetime.fromtimestamp(created_at).isoformat()
            else:
                created_at_str = str(created_at)
                
            if isinstance(updated_at, (int, float)):
                updated_at_str = datetime.fromtimestamp(updated_at).isoformat()
            else:
                updated_at_str = str(updated_at)
            
            # Build user info
            if anonymize_users:
                user_info = {
                    "id": "User_001",
                    "name": "User_001",
                    "email": None
                }
            else:
                user_info = {
                    "id": user_id,
                    "name": user_name or "Unknown",
                    "email": user_email
                }
            
            return {
                "id": chat_id,
                "title": title or "Untitled Chat",
                "user": user_info,
                "created_at": created_at_str,
                "updated_at": updated_at_str,
                "messages": messages
            }
            
        except Exception as e:
            logger.error(f"Error getting chat detail {chat_id}: {e}")
            return None
    
    def get_assistant_stats(
        self,
        assistant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get usage statistics for an assistant.
        
        Args:
            assistant_id: LAMB assistant ID
            start_date: Stats from this date
            end_date: Stats until this date
            
        Returns:
            Dict with statistics
        """
        try:
            model_pattern = f'lamb_assistant.{assistant_id}'
            
            # Build WHERE clause
            where_clauses = ["json_extract(c.chat, '$.models') LIKE ?"]
            params = [f'%{model_pattern}%']
            
            if start_date:
                where_clauses.append("c.created_at >= ?")
                params.append(start_date.timestamp())
            
            if end_date:
                where_clauses.append("c.created_at <= ?")
                params.append(end_date.timestamp())
            
            where_sql = " AND ".join(where_clauses)
            
            # Get basic stats
            stats_query = f"""
                SELECT 
                    COUNT(*) as chat_count,
                    COUNT(DISTINCT c.user_id) as unique_users
                FROM chat c
                WHERE {where_sql}
            """
            
            stats_result = self._execute_query(stats_query, tuple(params), fetch_one=True)
            
            chat_count = stats_result[0] if stats_result else 0
            unique_users = stats_result[1] if stats_result else 0
            
            # Get all chats to count messages (SQLite JSON functions are limited)
            chats_query = f"""
                SELECT c.chat
                FROM chat c
                WHERE {where_sql}
            """
            
            chats_result = self._execute_query(chats_query, tuple(params))
            
            total_messages = 0
            for row in (chats_result or []):
                try:
                    chat_data = json.loads(row[0]) if row[0] else {}
                    messages = chat_data.get("history", {}).get("messages", {})
                    total_messages += len(messages)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            avg_messages = total_messages / chat_count if chat_count > 0 else 0
            
            # Build period info
            period = {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            }
            
            return {
                "assistant_id": assistant_id,
                "period": period,
                "stats": {
                    "total_chats": chat_count,
                    "unique_users": unique_users,
                    "total_messages": total_messages,
                    "avg_messages_per_chat": round(avg_messages, 1)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting stats for assistant {assistant_id}: {e}")
            return {
                "assistant_id": assistant_id,
                "period": {"start": None, "end": None},
                "stats": {
                    "total_chats": 0,
                    "unique_users": 0,
                    "total_messages": 0,
                    "avg_messages_per_chat": 0
                },
                "error": str(e)
            }
    
    def get_assistant_timeline(
        self,
        assistant_id: int,
        period: str = "day",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get chat activity timeline for an assistant.
        
        Args:
            assistant_id: LAMB assistant ID
            period: Aggregation period - "day", "week", or "month"
            start_date: Timeline from this date
            end_date: Timeline until this date
            
        Returns:
            Dict with timeline data points
        """
        try:
            model_pattern = f'lamb_assistant.{assistant_id}'
            
            # Build WHERE clause
            where_clauses = ["json_extract(c.chat, '$.models') LIKE ?"]
            params = [f'%{model_pattern}%']
            
            if start_date:
                where_clauses.append("c.created_at >= ?")
                params.append(start_date.timestamp())
            
            if end_date:
                where_clauses.append("c.created_at <= ?")
                params.append(end_date.timestamp())
            
            where_sql = " AND ".join(where_clauses)
            
            # Determine date format based on period
            if period == "month":
                date_format = "%Y-%m"
            elif period == "week":
                date_format = "%Y-%W"  # Year and week number
            else:  # day
                date_format = "%Y-%m-%d"
            
            # Get chats with their dates
            query = f"""
                SELECT 
                    c.created_at,
                    c.chat
                FROM chat c
                WHERE {where_sql}
                ORDER BY c.created_at ASC
            """
            
            results = self._execute_query(query, tuple(params))
            
            # Aggregate by period
            timeline_data = {}
            
            for row in (results or []):
                created_at, chat_json = row
                
                # Convert timestamp to date string
                if isinstance(created_at, (int, float)):
                    dt = datetime.fromtimestamp(created_at)
                else:
                    try:
                        dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
                    except ValueError:
                        continue
                
                date_key = dt.strftime(date_format)
                
                # Count messages
                message_count = 0
                try:
                    chat_data = json.loads(chat_json) if chat_json else {}
                    messages = chat_data.get("history", {}).get("messages", {})
                    message_count = len(messages)
                except (json.JSONDecodeError, TypeError):
                    pass
                
                if date_key not in timeline_data:
                    timeline_data[date_key] = {"chat_count": 0, "message_count": 0}
                
                timeline_data[date_key]["chat_count"] += 1
                timeline_data[date_key]["message_count"] += message_count
            
            # Convert to list
            data = [
                {
                    "date": date_key,
                    "chat_count": values["chat_count"],
                    "message_count": values["message_count"]
                }
                for date_key, values in sorted(timeline_data.items())
            ]
            
            return {
                "assistant_id": assistant_id,
                "period": period,
                "data": data
            }
            
        except Exception as e:
            logger.error(f"Error getting timeline for assistant {assistant_id}: {e}")
            return {
                "assistant_id": assistant_id,
                "period": period,
                "data": [],
                "error": str(e)
            }
    
    def get_unique_models(self) -> List[str]:
        """
        Get list of unique models (assistants) that have been used in chats.
        Inspired by openwebui-db-inspect functionality.
        
        Returns:
            List of model identifiers
        """
        try:
            # SQLite JSON functions to extract models array
            query = """
                SELECT DISTINCT value as model 
                FROM chat, json_each(json_extract(chat, '$.models'))
                WHERE value LIKE 'lamb_assistant.%'
            """
            
            results = self._execute_query(query, ())
            
            return [row[0] for row in (results or [])]
            
        except Exception as e:
            logger.error(f"Error getting unique models: {e}")
            return []
    
    def _execute_query(
        self, 
        query: str, 
        params: tuple = (), 
        fetch_one: bool = False
    ) -> Optional[Any]:
        """Execute a query using the OWI database manager"""
        return self.db.execute_query(query, params, fetch_one=fetch_one)

